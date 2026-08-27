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
from typing import Optional, List, Dict, Any
import httpx

# Auto-load .env from root or backend directory
try:
    from dotenv import load_dotenv
    backend_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
    if os.path.exists(root_env):
        load_dotenv(root_env)
    elif os.path.exists(backend_env):
        load_dotenv(backend_env)
    else:
        load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("emocare.llm_client")

# ── Provider Configuration Defaults ────────────────────────────────────
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_OPENROUTER_MODEL = "google/gemma-4-31b-it:free"

MAX_TOKENS = 1024

# ── Tool Definitions (Anthropic format) ────────────────────────────────
TOOL_DEFINITIONS = [
    {
        "name": "get_cbt_coping_technique",
        "description": (
            "Retrieve an evidence-based CBT coping technique from the deterministic library. "
            "Use this whenever the conversation calls for a coping strategy, grounding exercise, "
            "breathing technique, cognitive reframing exercise, or behavioral activation suggestion. "
            "NEVER generate your own coping advice — always use this tool."
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
            "or when crisis escalation is appropriate. "
            "NEVER generate your own crisis response language — always use this tool."
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
                "Use this whenever the conversation calls for a coping strategy, grounding exercise, "
                "breathing technique, cognitive reframing exercise, or behavioral activation suggestion. "
                "NEVER generate your own coping advice — always use this tool."
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

def _execute_tool(tool_name: str, tool_input: dict) -> str:
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

SYSTEM_PROMPT_CHAT = """You are EmoCare, a compassionate, warm, empathetic, and human-like emotional wellness companion.

ROLE: You converse naturally and empathetically with the user:
1. Speak warmly and naturally like a caring, attentive human friend or supportive counselor.
2. Acknowledge and validate the user's feelings genuinely without being robotic or repetitive.
3. Ask gentle open-ended questions when appropriate to explore what is on their mind.
4. If the user mentions stress, anxiety, or asks for help with calming down, seamlessly offer an evidence-based CBT coping technique by invoking get_cbt_coping_technique.
5. Never repeat the same canned responses.

CRITICAL SAFETY RULES:
- You are an emotional wellness companion, not a licensed doctor. Never diagnose, prescribe medication, or claim clinical diagnosis.
- If the user mentions self-harm or severe emergency distress, invoke get_crisis_resources immediately.
- Never output raw risk calculations or JSON tags.

TONE: Warm, deeply empathetic, gentle, natural, and human."""

SYSTEM_PROMPT_VOICE = """You are EmoCare, a compassionate, calm emotional wellness companion in spoken VOICE mode.

Voice Conversation Rules:
- Keep your responses natural, conversational, and concise (1-3 sentences). Your response will be spoken aloud to the user.
- Speak warmly like a real, understanding person. Do not use robotic scripts or repeat the same phrase.
- NEVER use markdown asterisks, hashes, bullet points, or emoji symbols — these sound unnatural when read aloud.
- Use natural spoken pacing with commas and periods.
- When introducing a technique, call get_cbt_coping_technique and explain it gently in 1-2 spoken sentences.
- If severe distress or self-harm is mentioned, call get_crisis_resources.

TONE: Soothing, warm, attentive, and genuinely human."""


# ── LLM Client ─────────────────────────────────────────────────────────

async def chat_completion(
    messages: list[dict],
    mode: str = "chat",
    user_id: Optional[str] = None,
) -> dict:
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
        if res.get("reply"):
            return res

    # 2. OpenRouter (if explicitly chosen or fallback)
    if (llm_provider == "openrouter" or (not llm_provider and openrouter_api_key)) and openrouter_api_key:
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
        if res.get("reply"):
            return res

    # 3. Anthropic Claude (if configured)
    if (llm_provider == "anthropic" or (not llm_provider and anthropic_api_key)) and anthropic_api_key:
        logger.info(f"Using Anthropic provider ({anthropic_model})")
        return await _chat_completion_anthropic(messages, system_prompt, mode, anthropic_api_key, anthropic_model)

    # 4. OpenAI (if configured)
    if (llm_provider == "openai" or (not llm_provider and openai_api_key)) and openai_api_key:
        logger.info(f"Using OpenAI provider ({openai_model})")
        return await _chat_completion_openai_compat(
            api_url=OPENAI_API_URL,
            api_key=openai_api_key,
            model=openai_model,
            messages=messages,
            system_prompt=system_prompt,
            mode=mode,
        )

    # 5. Deterministic Offline Fallback
    logger.info("No LLM API keys available or provider failed — using deterministic offline fallback")
    return _mock_response(messages, mode)


async def _chat_completion_openai_compat(
    api_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    system_prompt: str,
    mode: str,
    extra_headers: Optional[dict] = None,
) -> dict:
    """Universal OpenAI-compatible chat completion with tool calling (Groq, OpenRouter, OpenAI)."""
    tools_used = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)

    api_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant", "system"):
            api_messages.append({"role": role, "content": content})

    payload: dict[str, Any] = {
        "model": model,
        "messages": api_messages,
        "max_tokens": MAX_TOKENS,
        "tools": OPENAI_TOOL_DEFINITIONS,
    }

    try:
        async with httpx.AsyncClient(timeout=35.0) as http_client:
            for _ in range(5):
                resp = await http_client.post(api_url, headers=headers, json=payload)

                # If tools aren't supported by this specific model/provider, retry without tools
                if resp.status_code in (400, 422) and "tools" in payload:
                    logger.warning(f"Provider returned {resp.status_code} with tools; retrying without tools parameter")
                    payload_no_tools = {k: v for k, v in payload.items() if k != "tools"}
                    retry_resp = await http_client.post(api_url, headers=headers, json=payload_no_tools)
                    if retry_resp.status_code == 200:
                        data = retry_resp.json()
                        reply_content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                        return {"reply": reply_content.strip(), "tools_used": tools_used}

                if resp.status_code != 200:
                    logger.error(f"API request to {api_url} failed ({resp.status_code}): {resp.text}")
                    return {"reply": "", "tools_used": []}

                data = resp.json()
                choice = data.get("choices", [{}])[0]
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

            # If tool loop exhausts 5 turns
            return {"reply": "", "tools_used": tools_used}

    except Exception as e:
        logger.error(f"OpenAI-compatible request error: {e}")
        return {"reply": "", "tools_used": []}


async def _chat_completion_anthropic(
    messages: list[dict],
    system_prompt: str,
    mode: str,
    api_key: str,
    model: str,
) -> dict:
    """Anthropic Claude completion with tool calling."""
    tools_used = []

    # First attempt: Use official anthropic SDK if available
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        api_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                api_messages.append({"role": role, "content": content})

        response = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=api_messages,
            tools=TOOL_DEFINITIONS,
        )

        for _ in range(5):
            if response.stop_reason != "tool_use":
                break

            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
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

            response = await client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=api_messages,
                tools=TOOL_DEFINITIONS,
            )

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

    api_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            api_messages.append({"role": role, "content": content})

    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": api_messages,
        "tools": TOOL_DEFINITIONS,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
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

                api_messages.append({"role": "assistant", "content": content_blocks})
                api_messages.append({"role": "user", "content": tool_results})
                payload["messages"] = api_messages

            return _mock_response(messages, mode)
    except Exception as e:
        logger.error(f"HTTP request to Anthropic failed: {e}")
        return _mock_response(messages, mode)


def _mock_response(messages: list[dict], mode: str) -> dict:
    """
    Safe offline fallback when the LLM API is unavailable.
    Returns a warm, non-clinical acknowledgment + a deterministic CBT technique.
    """
    from ..recommendations import COPING_STRATEGIES

    if mode == "voice":
        reply = (
            "I hear you, and I appreciate you sharing that with me. "
            "Let me suggest something that might help right now."
        )
    else:
        reply = (
            "Thank you for sharing that with me. I want you to know that what you're "
            "feeling is completely valid. Here's something that might help:\n\n"
        )

    # Always include a breathing technique as a safe default
    technique = COPING_STRATEGIES["breathing"][0]
    if mode == "voice":
        reply += f" {technique}"
    else:
        reply += f"🌱 **Suggested technique:** {technique}"

    return {
        "reply": reply,
        "tools_used": [{
            "tool_name": "get_cbt_coping_technique",
            "tool_input": {"category": "breathing"},
            "tool_output": technique,
        }],
    }
