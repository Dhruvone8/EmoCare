"""
EmoCare LLM Client — Provider-agnostic conversational AI with tool calling.

Supported Providers:
1. Groq Cloud (OpenAI-compatible) — default: openai/gpt-oss-120b (ultra-fast, free, human-like)
2. OpenRouter (OpenAI-compatible) — default: google/gemma-4-31b-it:free
3. Anthropic Claude — default: claude-sonnet-4-6
4. OpenAI — default: gpt-4o-mini
5. Built-in Deterministic Offline Fallback (zero config/keys needed)

SAFETY CONTRACT:
- The LLM is NEVER allowed to freely generate coping advice, crisis language,
  clinical claims, or diagnostic statements.
- All therapeutic recommendations and crisis responses must come from
  deterministic backend tools via function/tool calling.
- The LLM may only converse empathetically and invoke tools when appropriate.
"""
import os
import json
import logging
import importlib
from typing import Optional, Any
from .therapy_session_manager import (
    clean_cliches,
    enforce_single_question,
    is_repetitive,
    generate_contextual_therapeutic_reply,
    STAGE_OPENING,
    STAGE_EXPLORING,
    STAGE_DEEPENING,
    STAGE_DIRECTION,
    STAGE_INTERVENTION,
    STAGE_CLOSING,
)

# Auto-load .env from root or backend directory safely without static import warnings
try:
    _dotenv = importlib.import_module("dotenv")
    _load_dotenv = getattr(_dotenv, "load_dotenv", None)
    if _load_dotenv:
        backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
        root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
        if os.path.exists(root_env):
            _load_dotenv(root_env)
        elif os.path.exists(backend_env):
            _load_dotenv(backend_env)
        else:
            _load_dotenv()
except Exception:
    pass

logger = logging.getLogger("emocare.llm_client")

# ── Provider Configuration Defaults ────────────────────────────────────
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"

MAX_TOKENS = 1024

# ── Tool Definitions (Anthropic format) ────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "get_cbt_coping_technique",
        "description": (
            "Retrieve an evidence-based CBT coping technique from the deterministic library. "
            "Only invoke this tool when the client explicitly asks for a structured exercise, "
            "grounding technique, or breathing exercise, or when collaboratively practicing a technique. "
            "Do NOT call this tool for normal conversation, listening, reflection, or emotional exploration."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "grounding", "breathing", "cognitive_reframe",
                        "behavioral_activation", "social_connection",
                        "journaling", "professional_help"
                    ],
                    "description": "The category of CBT technique to retrieve"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "get_crisis_resources",
        "description": (
            "Retrieve crisis helpline information and emergency resources. "
            "Use this when the user expresses severe distress, mentions self-harm, "
            "or when crisis escalation is appropriate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": ["us", "uk", "india", "all"],
                    "description": "Geographic region for relevant helplines, or 'all' for all regions"
                }
            },
            "required": ["region"]
        }
    },
    {
        "name": "get_user_session_context",
        "description": (
            "Retrieve the user's recent therapy session summaries for conversational continuity. "
            "Use this at the start of a session or when you want to reference past sessions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "The user's unique identifier"
                }
            },
            "required": ["user_id"]
        }
    }
]

# ── Tool Definitions (OpenAI / OpenRouter / Groq format) ───────────────
OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_cbt_coping_technique",
            "description": (
                "Retrieve an evidence-based CBT coping technique from the deterministic library. "
                "Only invoke this tool when the client explicitly asks for a structured exercise, "
                "grounding technique, or breathing exercise, or when collaboratively practicing a technique. "
                "Do NOT call this tool for normal conversation, listening, reflection, or emotional exploration."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "grounding", "breathing", "cognitive_reframe",
                            "behavioral_activation", "social_connection",
                            "journaling", "professional_help"
                        ],
                        "description": "The category of CBT technique to retrieve"
                    }
                },
                "required": ["category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_crisis_resources",
            "description": (
                "Retrieve crisis helpline information and emergency resources. "
                "Use this when the user expresses severe distress, mentions self-harm, "
                "or when crisis escalation is appropriate. "
                "NEVER generate your own crisis response language — always use this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "enum": ["us", "uk", "india", "all"],
                        "description": "Geographic region for relevant helplines, or 'all' for all regions"
                    }
                },
                "required": ["region"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_session_context",
            "description": (
                "Retrieve the user's recent therapy session summaries for conversational continuity. "
                "Use this at the start of a session or when you want to reference past sessions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "The user's unique identifier"
                    }
                },
                "required": ["user_id"]
            }
        }
    }
]


# ── Tool Execution (maps tool calls to real backend functions) ──────────

def _execute_tool(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Execute a tool call and return the deterministic result as a string."""
    if tool_name == "get_cbt_coping_technique":
        from ..recommendations import COPING_STRATEGIES
        category = tool_input.get("category", "breathing")
        techniques = COPING_STRATEGIES.get(category, [])
        if techniques:
            return "\n".join(techniques)
        return "No techniques found for this category."

    elif tool_name == "get_crisis_resources":
        from ..recommendations import CRISIS_RESOURCES
        region = tool_input.get("region", "all")
        if region == "us":
            return CRISIS_RESOURCES[1]  # US 988
        elif region == "uk":
            return CRISIS_RESOURCES[2]  # UK Samaritans
        elif region == "india":
            return CRISIS_RESOURCES[0]  # India iCall
        else:
            return "\n".join(CRISIS_RESOURCES)

    elif tool_name == "get_user_session_context":
        from ..db import get_recent_session_summaries
        user_id = tool_input.get("user_id", "")
        summaries = get_recent_session_summaries(user_id, limit=3)
        if not summaries:
            return "No previous session history available for this user."
        parts = []
        for s in summaries:
            parts.append(
                f"Session ({s.get('mode', 'unknown')} on {s.get('created_at', 'unknown')}):\n"
                f"  Summary: {s.get('summary_text', 'N/A')}\n"
                f"  Concerns: {', '.join(s.get('concerns', []))}\n"
                f"  Goals: {', '.join(s.get('goals', []))}\n"
                f"  Techniques used: {', '.join(s.get('techniques_used', []))}"
            )
        return "\n---\n".join(parts)

    return f"Unknown tool: {tool_name}"


# ── System Prompts ─────────────────────────────────────────────────────

SYSTEM_PROMPT_CHAT = """You are EmoCare, an AI emotional support and wellness companion facilitating a realistic, structured, therapist-guided session. You draw upon evidence-based approaches including Cognitive Behavioral Therapy (CBT), Person-Centered Therapy, and Mindfulness.

IDENTITY & ETHICAL BOUNDARIES (STRICT):
1. You are an AI wellness companion, NOT a licensed therapist, clinical psychologist, or medical doctor.
2. NEVER claim or imply that you are a licensed therapist, human clinician, or that a human is monitoring the session. If asked about credentials or identity, transparently state that you are an AI emotional wellness companion.

CONVERSATION PHILOSOPHY & THERAPEUTIC PROGRESSION:
1. NEVER behave like an ordinary question-answering assistant, customer support bot, or motivational poster.
2. Facilitate a natural therapy session that progresses flexibly across 6 stages:
   - Stage A (Opening Check-in): Warm, brief greeting. Ask what they would like to work through today. Do not rush to assess or give advice.
   - Stage B (Explore Concern): Acknowledge the specific event using the user's words. Reflect expressed feelings accurately without assuming unstated emotions.
   - Stage C (Deepen Understanding): Explore recurring thoughts, fears, or tentative patterns. Invite the user to correct your understanding.
   - Stage D (Identify Direction): Collaboratively ask what would be most helpful (e.g. continuing to talk, exploring meaning, reframing the thought, or planning a practical step).
   - Stage E (Therapeutic Intervention): Introduce relevant CBT reframing, grounding exercises, behavioral activation, or structured problem-solving in small, manageable steps. Ask how the suggestion lands.
   - Stage F (Integrate & Close): Summarize key insights, identify a small realistic next step, and invite closing reflections.

STRICT COMMUNICATION RULES:
1. AT MOST ONE QUESTION PER TURN: Ask exactly ONE focused, open-ended question at a time. Never interrogate the user with multiple questions in a single reply.
2. ZERO ROBOTIC CLICHÉS: NEVER start or pepper responses with canned phrases like "Thank you for sharing", "I'm here for you", "That sounds difficult", "It makes sense that you feel that way", or "I hear how heavy that is".
3. CONTEXTUAL LISTENING: Anchor reflections directly in the specific facts, names, events, and words the user shares.
4. ADAPT TO USER AGENCY IMMEDIATELY:
   - If user asks to vent ("just need to vent", "no advice"): listen attentively, validate without unsolicited advice or questioning.
   - If user asks for advice, tasks, or exercises ("what should I do?", "give me an exercise"): provide clear, actionable steps immediately.
   - If user asks to stop questioning ("stop asking questions"): immediately cease questions and offer calm supportive presence.
   - If user wants to change topic: immediately follow their lead without resistance.
   - If user corrects you: acknowledge and accept their correction non-defensively.
5. AMBIGUOUS, CASUAL, OR UNCLEAR MESSAGES:
   - If the user sends a greeting (e.g. "hi"), greet them naturally and ask what is on their mind. Do NOT assume a problem.
   - If the user sends a single letter or fragment (e.g. "h"), politely ask what they meant. Do NOT invent an emotional crisis.
   - If the user sends unclear or nonsensical input (e.g. "hsnjqjw u jkzx"), ask for clarification. Do NOT fabricate emotions or history.
   - If the user sends casual or affectionate banter (e.g. "I love you bbg"), respond warmly and ask what's on their mind without forcing a previous therapy topic.

TOOL USAGE:
- You have access to deterministic CBT tools (e.g., get_cbt_coping_technique) and crisis resources. Invoke them when structured exercises or crisis resources are appropriate.

CRISIS & SAFETY:
- If the user expresses active intent to self-harm or suicidal ideation, invoke get_crisis_resources immediately and prioritize their immediate safety."""

SYSTEM_PROMPT_VOICE = """You are EmoCare, an insightful, warm, and proactive AI therapeutic companion providing real-time voice-based therapy. You draw upon evidence-based psychological frameworks including Cognitive Behavioral Therapy (CBT), Acceptance and Commitment Therapy (ACT), and Mindfulness.

IDENTITY & ETHICAL BOUNDARIES (STRICT):
1. You are an AI companion, NOT a licensed therapist, clinical psychologist, or medical doctor.
2. NEVER claim or imply that you are a licensed therapist or human doctor. If asked about your identity or credentials, transparently state that you are an AI emotional wellness companion.

ACTIVE THERAPIST ROLE & THE THREE-PART RESPONSE FLOW:
Do NOT act like a passive listener or a sounding board that merely repeats the user's feelings. Your job is to act like an active, skilled therapist who helps the user cope, reframe, and take constructive steps.
In each spoken response, deliver the Three-Part Therapeutic Flow (typically 2 to 4 spoken sentences, ~45 to 80 words):

1. GENUINE VALIDATION (1 sentence):
   Warmly and specifically acknowledge what the user shared. Avoid generic clichés like "I hear how heavy that is". Mirror the specific emotional weight or reality they mentioned.

2. ACTIVE COPING SUGGESTION & THERAPEUTIC GUIDANCE (1–2 sentences):
   Provide a concrete coping strategy, cognitive reframing, grounding technique, or actionable perspective tailored directly to their situation:
   - For overwhelm/burnout: suggest breaking tasks into a 5-minute micro-step, cognitive prioritization, or taking a structured breath.
   - For anxiety/panic: offer a physiological sigh, 5-4-3-2-1 sensory grounding, or separating controllable factors from uncontrollables.
   - For self-doubt/imposter thoughts: gently point out cognitive distortions (catastrophizing, all-or-nothing thinking) and suggest looking for counter-evidence.
   - For sadness or fatigue: suggest gentle behavioral activation, self-compassion, or emotional release.

3. PURPOSEFUL THERAPEUTIC FOLLOW-UP QUESTION (MANDATORY, 1 sentence):
   Always conclude your turn with a purposeful, engaging follow-up question that invites the user to reflect deeper, explore their feelings, or try out the coping technique (unless they asked you not to ask questions):
   - "How does that suggestion feel to you?"
   - "What feels like the heaviest part of this for you right now?"
   - "Would you like to try taking that slow reset breath together right now?"
   - "What is one small thing within your control that could give you relief today?"

CONVERSATIONAL ADAPTATION:
- Every turn must combine empathetic connection + actionable coping suggestion + a purposeful follow-up question. Never ask empty questions without offering therapeutic guidance or coping tools first.
- If the user explicitly asks you to stop asking questions or indicates they just want to vent without answering, immediately respect their preference: provide comforting presence and actionable coping thoughts without asking trailing questions.
- If the user asks for exercises or advice, guide them through the steps immediately.

SPOKEN VOICE CADENCE:
- Spoken through ElevenLabs TTS: Keep responses natural, warm, and conversational (2 to 4 spoken sentences, ~45 to 80 words).
- Speak naturally as if conversing in person.
- ABSOLUTELY NO MARKDOWN: Never use asterisks (** or *), numbered lists, bullet points, headers, or emojis. Write plain spoken sentences with natural commas and periods.

CRISIS & SAFETY:
- If the user expresses active intent to self-harm or suicidal ideation, prioritize their immediate safety and gently guide them to professional crisis helplines (988, iCall)."""


# ── LLM Client ─────────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict[str, Any]],
    mode: str = "chat",
    user_id: Optional[str] = None,
    session_state: Optional[dict] = None,
    current_stage: Optional[str] = None,
) -> dict[str, Any]:
    """
    Send a multi-turn conversation to the configured LLM provider and handle tool calling.
    Supports Groq, OpenRouter, Anthropic Claude, OpenAI, or local offline fallback.

    Returns:
        {
            "reply": str,          # The final text reply
            "tools_used": list,    # List of {tool_name, tool_input, tool_output}
        }
    """
    system_prompt = SYSTEM_PROMPT_VOICE if mode == "voice" else SYSTEM_PROMPT_CHAT

    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL).strip() or DEFAULT_GROQ_MODEL

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    openrouter_model = os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL).strip() or DEFAULT_OPENROUTER_MODEL

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()

    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    res: Optional[dict[str, Any]] = None

    # 1. Groq (Default recommended provider — fast, free, human-like)
    if (llm_provider == "groq" or (not llm_provider and groq_api_key)) and groq_api_key:
        logger.info(f"Using Groq LLM provider ({groq_model})")
        res = await _chat_completion_openai_compat(
            api_url=GROQ_API_URL,
            api_key=groq_api_key,
            model=groq_model,
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
        )

    # 2. OpenRouter (if explicitly chosen or fallback)
    if (not res or not res.get("reply")) and (llm_provider == "openrouter" or (not llm_provider and openrouter_api_key)) and openrouter_api_key:
        logger.info(f"Using OpenRouter provider ({openrouter_model})")
        res = await _chat_completion_openai_compat(
            api_url=OPENROUTER_API_URL,
            api_key=openrouter_api_key,
            model=openrouter_model,
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
            extra_headers={
                "HTTP-Referer": "http://localhost:3000",
                "X-Title": "EmoCare",
            }
        )

    # 3. Anthropic Claude (if configured)
    if (not res or not res.get("reply")) and (llm_provider == "anthropic" or (not llm_provider and anthropic_api_key)) and anthropic_api_key:
        logger.info(f"Using Anthropic provider ({anthropic_model})")
        res = await _chat_completion_anthropic(messages, system_prompt, mode, anthropic_api_key, anthropic_model)

    # 4. OpenAI (if configured)
    if (not res or not res.get("reply")) and (llm_provider == "openai" or (not llm_provider and openai_api_key)) and openai_api_key:
        logger.info(f"Using OpenAI provider ({openai_model})")
        res = await _chat_completion_openai_compat(
            api_url=OPENAI_API_URL,
            api_key=openai_api_key,
            model=openai_model,
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
        )

    # 5. Deterministic Offline Fallback
    if not res or not res.get("reply"):
        logger.info("No LLM API keys available or provider failed — using deterministic offline fallback")
        res = _mock_response(messages, mode, session_state=session_state, current_stage=current_stage)

    reply = (res.get("reply") or "").strip()
    reply = clean_cliches(reply)
    if mode == "chat":
        reply = enforce_single_question(reply)

    # Anti-repetition check against recent assistant turns in messages
    recent_assistant_texts = [
        m.get("content", "") for m in messages
        if m.get("role") == "assistant" and not m.get("content", "").startswith("[SYSTEM")
    ]
    if not reply or is_repetitive(reply, recent_assistant_texts):
        logger.info("Generated reply was empty or repetitive, using stage-aware contextual fallback")
        fallback_res = _mock_response(messages, mode, session_state=session_state, current_stage=current_stage)
        reply = fallback_res["reply"]

    res["reply"] = reply
    return res


async def _chat_completion_openai_compat(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    system_prompt: str,
    mode: str,
    extra_headers: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Universal OpenAI-compatible chat completion with tool calling (Groq, OpenRouter, OpenAI)."""
    tools_used: list[dict[str, Any]] = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    api_messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system"):
            clean_msg: dict[str, Any] = {"role": role, "content": content}
            if "tool_calls" in msg:
                clean_msg["tool_calls"] = msg["tool_calls"]
            api_messages.append(clean_msg)
        elif role == "tool":
            api_messages.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "name": msg.get("name", ""),
                "content": content,
            })

    # In voice mode, 280 tokens provides complete, natural spoken turns with grounding steps
    token_limit = 280 if mode == "voice" else MAX_TOKENS

    payload: dict[str, Any] = {
        "model": model,
        "messages": api_messages,
        "max_tokens": token_limit,
        "tools": OPENAI_TOOL_DEFINITIONS,
    }

    try:
        from .http_pool import get_shared_client
        http_client = get_shared_client()
        for _ in range(4):
            resp = await http_client.post(api_url, headers=headers, json=payload)

            # If tools aren't supported by this specific model/provider, retry without tools on first turn
            if resp.status_code in (400, 422) and "tools" in payload and not tools_used:
                logger.warning(f"Provider returned {resp.status_code} with tools; retrying without tools parameter")
                payload_no_tools = {k: v for k, v in payload.items() if k != "tools"}
                retry_resp = await http_client.post(api_url, headers=headers, json=payload_no_tools)
                if retry_resp.status_code == 200:
                    data = retry_resp.json()
                    choices = data.get("choices") or []
                    reply_content = choices[0].get("message", {}).get("content", "") if choices else ""
                    return {"reply": (reply_content or "").strip(), "tools_used": tools_used}
                else:
                    logger.error(f"Provider retry without tools failed ({retry_resp.status_code}): {retry_resp.text}")
                    return {"reply": "", "tools_used": tools_used}

            if resp.status_code != 200:
                logger.error(f"API request to {api_url} failed ({resp.status_code}): {resp.text}")
                return {"reply": "", "tools_used": tools_used}

            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                logger.error(f"API response missing choices from {api_url}: {data}")
                return {"reply": "", "tools_used": tools_used}

            choice = choices[0]
            message_obj = choice.get("message", {})
            tool_calls = message_obj.get("tool_calls")

            if not tool_calls:
                reply_text = message_obj.get("content", "") or ""
                return {
                    "reply": reply_text.strip(),
                    "tools_used": tools_used,
                }

            # Tool use requested by model
            api_messages.append(message_obj)
            for tc in tool_calls:
                func_info = tc.get("function", {})
                func_name = func_info.get("name", "")
                raw_args = func_info.get("arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                tool_output = _execute_tool(func_name, args)
                tools_used.append({
                    "tool_name": func_name,
                    "tool_input": args,
                    "tool_output": tool_output,
                })
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": func_name,
                    "content": tool_output,
                })

            payload["messages"] = api_messages

        return {"reply": "", "tools_used": tools_used}

    except Exception as e:
        logger.error(f"OpenAI-compatible request error: {e}")
        return {"reply": "", "tools_used": []}


async def _chat_completion_anthropic(
    messages: list[dict[str, Any]],
    system_prompt: str,
    mode: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    """Anthropic Claude completion with tool calling."""
    tools_used: list[dict[str, Any]] = []

    # First attempt: Use official anthropic SDK dynamically if available
    try:
        anthropic_mod = importlib.import_module("anthropic")
        client = anthropic_mod.AsyncAnthropic(api_key=api_key)

        api_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                api_messages.append({"role": role, "content": content})

        sdk_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "messages": api_messages,
        }
        if mode != "voice":
            sdk_kwargs["tools"] = TOOL_DEFINITIONS

        response = await client.messages.create(**sdk_kwargs)

        for _ in range(5):
            if response.stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
            tool_results = []

            for tool_block in tool_use_blocks:
                tool_output = _execute_tool(tool_block.name, tool_block.input)
                tools_used.append({
                    "tool_name": tool_block.name,
                    "tool_input": tool_block.input,
                    "tool_output": tool_output,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": tool_output,
                })

            api_messages.append({"role": "assistant", "content": response.content})
            api_messages.append({"role": "user", "content": tool_results})

            loop_kwargs = {**sdk_kwargs, "messages": api_messages}
            response = await client.messages.create(**loop_kwargs)

        reply_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply_text += block.text

        return {
            "reply": reply_text.strip(),
            "tools_used": tools_used,
        }

    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Anthropic SDK error: {e}. Attempting direct HTTP fallback.")

    # Direct HTTP fallback for Anthropic API
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    api_messages_http: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            api_messages_http.append({"role": role, "content": content})

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": api_messages_http,
        "tools": TOOL_DEFINITIONS,
    }

    try:
        from .http_pool import get_shared_client
        http_client = get_shared_client()
        for _ in range(5):
            resp = await http_client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"Anthropic API returned status {resp.status_code}: {resp.text}")
                return _mock_response(messages, mode)

            data = resp.json()
            stop_reason = data.get("stop_reason")
            content_blocks = data.get("content", [])

            if stop_reason != "tool_use":
                reply_text = "".join([b.get("text", "") for b in content_blocks if b.get("type") == "text"])
                return {
                    "reply": reply_text.strip(),
                    "tools_used": tools_used,
                }

            tool_results = []
            for b in content_blocks:
                if b.get("type") == "tool_use":
                    t_name = b.get("name", "")
                    t_input = b.get("input", {})
                    t_id = b.get("id", "")
                    t_out = _execute_tool(t_name, t_input)
                    tools_used.append({
                        "tool_name": t_name,
                        "tool_input": t_input,
                        "tool_output": t_out,
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": t_id,
                        "content": t_out,
                    })

            api_messages_http.append({"role": "assistant", "content": content_blocks})
            api_messages_http.append({"role": "user", "content": tool_results})
            payload["messages"] = api_messages_http

        return _mock_response(messages, mode)
    except Exception as e:
        logger.error(f"HTTP request to Anthropic failed: {e}")
        return _mock_response(messages, mode)


def _mock_response(
    messages: list[dict[str, Any]],
    mode: str,
    session_state: Optional[dict] = None,
    current_stage: Optional[str] = None,
) -> dict[str, Any]:
    """
    Empathetic, stage-aware, evidence-informed fallback when external LLM API is unreachable.
    Follows all clinical communication guidelines:
    - Never claims to be a licensed therapist.
    - Honors user preference (e.g. stops questioning if asked, supports venting).
    - Progresses dynamically through therapy stages without canned clichés.
    """
    last_user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user" and not m.get("content", "").startswith("[SYSTEM"):
            last_user_text = m.get("content", "")
            break

    lower = last_user_text.lower()
    # 1. Identity query
    if any(k in lower for k in ["licensed", "doctor", "human", "real therapist", "who are you", "what are you"]):
        reply = "I am EmoCare, an AI emotional wellness companion, not a licensed therapist or medical doctor. I am here to offer supportive listening, reflection, and evidence-based coping tools."
        return {"reply": reply, "tools_used": []}

    state = session_state or {}
    stage = current_stage or state.get("current_stage", "exploring")
    reply = generate_contextual_therapeutic_reply(
        user_message=last_user_text,
        current_stage=stage,
        session_state=state,
        recent_history=messages,
    )
    return {
        "reply": reply,
        "tools_used": [],
    }
