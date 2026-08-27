"""
EmoCare Therapy Orchestrator — Chat & Voice therapy pipeline.

SAFETY ARCHITECTURE:
1. Every user message is classified by the EXISTING text risk model BEFORE the LLM sees it.
2. If risk_tier == "High" or urgency == "CRITICAL": bypass the LLM entirely and
   return the EXISTING deterministic crisis protocol response.
3. Otherwise: load session memory, invoke LLM with tool-calling access to the
   deterministic CBT catalog and crisis resources.

The LLM NEVER gets to decide whether to escalate — the classifier does.
"""
import json
import logging

from .engine.llm_client import chat_completion
from .inference import predict_text
from .recommendations import CRISIS_RESOURCES, COPING_STRATEGIES
from .db import (
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
    save_session_summary,
)

logger = logging.getLogger("emocare.therapy")


# ── Crisis Protocol Response (deterministic, pre-approved) ─────────────

def _build_crisis_response(risk_tier: str, mode: str = "chat") -> dict:
    """
    Build the deterministic crisis escalation response.
    This bypasses the LLM entirely — the exact text comes from the
    existing rule-based crisis protocol.
    """
    crisis_text = "\n".join(CRISIS_RESOURCES)
    grounding_text = COPING_STRATEGIES["grounding"][0]

    if mode == "voice":
        # Voice mode: no markdown, spoken-friendly
        reply = (
            "I want you to know that I care about you and what you're going through matters. "
            "Right now, the most important thing is to connect with someone who can help. "
            "Please reach out to a crisis helpline. "
            "In the US, dial or text 988. "
            "In India, call iCall at 9152987821. "
            "In the UK, call Samaritans at 116 123. "
            "If you're in immediate danger, please call emergency services."
        )
    else:
        reply = (
            "I hear you, and I want you to know that what you're going through matters deeply. "
            "Right now, I want to make sure you have immediate support.\n\n"
            "**🚨 Please reach out to a crisis helpline:**\n\n"
        )
        for resource in CRISIS_RESOURCES:
            reply += f"- {resource}\n"
        reply += (
            f"\n🌱 **While you reach out, try this grounding anchor:**\n{grounding_text}\n\n"
            "You are not alone. These trained professionals are available 24/7."
        )

    return {
        "reply": reply,
        "risk_tier": risk_tier,
        "urgency_level": "CRITICAL",
        "crisis_activated": True,
        "tools_used": [{
            "tool_name": "get_crisis_resources",
            "tool_input": {"region": "all"},
            "tool_output": crisis_text,
        }],
    }


import re

# ── Clinical Crisis Detection Patterns (PHQ-9 Item 9 & self-harm markers)
CRISIS_PATTERNS = [
    re.compile(r"\b(suicid|kill(ing)?\s+myself|end\s+my\s+life|want\s+to\s+die|better\s+off\s+dead|harm(ing)?\s+myself|hurt(ing)?\s+myself)\b", re.IGNORECASE),
]


def _is_crisis_signal(text: str, text_risk) -> bool:
    """Detect if text crosses the High/Critical clinical crisis threshold."""
    # 1. Classified as High tier
    if text_risk.predicted_risk_tier == "High":
        return True
    # 2. Elevated High-risk probability (>= 0.35 matching late fusion engine threshold)
    if getattr(text_risk.probabilities, "High", 0.0) >= 0.35:
        return True
    # 3. Explicit clinical crisis keyword / ideation match
    for pattern in CRISIS_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── Main Chat Therapy Turn ─────────────────────────────────────────────

async def process_chat_turn(
    session_id: int,
    user_id: str,
    user_message: str,
    mode: str = "chat",
) -> dict:
    """
    Process a single conversational turn in chat or voice therapy.

    Steps:
    1. Run text risk classifier on user message (BEFORE LLM)
    2. If High/Critical → short-circuit to crisis protocol
    3. Otherwise → build conversation context, invoke LLM with tools
    4. Persist both user and assistant messages

    Returns dict compatible with ChatMessageResponse schema.
    """
    # ── Step 1: Pre-LLM Risk Classification ────────────────────────────
    text_risk = predict_text(user_message)
    is_crisis = _is_crisis_signal(user_message, text_risk)
    risk_tier = "High" if is_crisis else text_risk.predicted_risk_tier
    confidence = text_risk.confidence

    logger.info(
        f"Chat turn risk: tier={risk_tier}, crisis={is_crisis}, confidence={confidence:.3f}, "
        f"session={session_id}, user={user_id}"
    )

    # Persist user message with risk tier
    save_therapy_message(session_id, "user", user_message, risk_tier)

    # ── Step 2: Safety Gate — High/Critical → bypass LLM ───────────────
    if is_crisis:
        crisis_response = _build_crisis_response(risk_tier, mode)
        # Persist crisis response
        save_therapy_message(session_id, "assistant", crisis_response["reply"])
        return {
            "session_id": session_id,
            **crisis_response,
        }

    # ── Step 3: Build LLM Context ──────────────────────────────────────
    # Load recent session summaries for continuity
    prior_summaries = get_recent_session_summaries(user_id, limit=3)

    # Build message history from this session
    session_msgs = get_session_messages(session_id)

    # Construct LLM messages
    llm_messages = []

    # Add session memory context if available
    if prior_summaries:
        memory_context = "Previous session context for this user:\n"
        for s in prior_summaries:
            memory_context += (
                f"- {s.get('mode', 'unknown')} session: {s.get('summary_text', 'N/A')} "
                f"(concerns: {', '.join(s.get('concerns', []))})\n"
            )
        llm_messages.append({
            "role": "user",
            "content": f"[SYSTEM CONTEXT — do not repeat this to the user]\n{memory_context}"
        })
        llm_messages.append({
            "role": "assistant",
            "content": "I'll keep this context in mind for our conversation."
        })

    # Add conversation history
    for msg in session_msgs:
        llm_messages.append({
            "role": msg["role"],
            "content": msg["content"],
        })

    # ── Step 4: Invoke LLM with Tool Access ────────────────────────────
    llm_result = await chat_completion(
        messages=llm_messages,
        mode=mode,
        user_id=user_id,
    )

    reply = llm_result.get("reply", "I'm here for you. Could you tell me more about how you're feeling?")
    tools_used = llm_result.get("tools_used", [])

    # Persist assistant reply
    save_therapy_message(session_id, "assistant", reply)

    # Determine urgency level from risk tier
    if risk_tier == "Moderate":
        urgency = "WARNING"
    else:
        urgency = "STABLE"

    return {
        "session_id": session_id,
        "reply": reply,
        "risk_tier": risk_tier,
        "urgency_level": urgency,
        "crisis_activated": False,
        "tools_used": tools_used,
    }


# ── Session Summarization ──────────────────────────────────────────────

async def generate_session_summary(
    session_id: int,
    user_id: str,
) -> dict:
    """
    Generate a structured session summary using the LLM.
    Extracts: concerns raised, goals discussed, techniques used, and progress.

    The summary is stored in session_summaries for future session memory.
    """
    messages = get_session_messages(session_id)

    if not messages:
        return {
            "session_id": session_id,
            "summary_text": "No conversation to summarize.",
            "concerns": [],
            "goals": [],
            "techniques_used": [],
        }

    # Build conversation transcript for summarization
    transcript = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}" for msg in messages
    ])

    summary_prompt = [
        {
            "role": "user",
            "content": (
                "Please analyze the following therapy session conversation and provide a structured summary.\n\n"
                f"CONVERSATION:\n{transcript}\n\n"
                "Respond with ONLY a JSON object (no markdown, no code blocks) in this exact format:\n"
                '{"summary_text": "Brief 2-3 sentence summary of the session",'
                ' "concerns": ["list", "of", "concerns", "raised"],'
                ' "goals": ["list", "of", "goals", "discussed"],'
                ' "techniques_used": ["list", "of", "CBT techniques", "applied"]}'
            )
        }
    ]

    llm_result = await chat_completion(messages=summary_prompt, mode="chat", user_id=user_id)
    raw_reply = llm_result.get("reply", "")

    # Parse structured summary
    try:
        # Try to extract JSON from the reply
        summary_data = json.loads(raw_reply)
    except json.JSONDecodeError:
        # Fallback: create a basic summary
        summary_data = {
            "summary_text": raw_reply[:500] if raw_reply else "Session completed.",
            "concerns": [],
            "goals": [],
            "techniques_used": [],
        }

    # Persist to database
    save_session_summary(
        session_id=session_id,
        user_id=user_id,
        summary_text=summary_data.get("summary_text", "Session completed."),
        concerns=summary_data.get("concerns", []),
        goals=summary_data.get("goals", []),
        techniques_used=summary_data.get("techniques_used", []),
    )

    return {
        "session_id": session_id,
        "summary_text": summary_data.get("summary_text", "Session completed."),
        "concerns": summary_data.get("concerns", []),
        "goals": summary_data.get("goals", []),
        "techniques_used": summary_data.get("techniques_used", []),
    }
