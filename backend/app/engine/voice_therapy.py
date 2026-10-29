"""
EmoCare Voice Therapy Pipeline — Ultra-fast parallel audio-in → audio-out orchestrator.

Latency Optimizations:
1. True parallel execution: Whisper STT, acoustic emotion analysis, session memory, and the
   latest saved assessment all execute concurrently at turn start.
2. Acoustic SER runs on a background worker thread with prosodic pyin calculation disabled.
3. Database writes (message persistence) are fire-and-forget background tasks.
4. Persistent connection pool reuses TCP/TLS sessions for STT, LLM, and TTS.
5. Voice-mode LLM tokens are capped at 280 tokens with a reflective, tool-gated prompt.
6. Generated replies are sanitized before the same final text is persisted and sent to ElevenLabs TTS.
"""
import asyncio
import logging
import re
from typing import Optional

from .stt_client import transcribe_audio
from .tts_client import synthesize_speech
from ..inference import predict_speech, predict_text
from ..model_loader import models
from ..therapy import _build_assessment_context, _build_crisis_response, _is_crisis_signal
from .llm_client import chat_completion
from .therapy_session_manager import (
    STAGE_EXPLORING,
    classify_message_intent,
    validate_and_sanitize_response,
)
from ..db import (
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
    get_user_assessment_history,
)

logger = logging.getLogger("emocare.voice_therapy")


def _safe_predict_speech(audio_bytes: bytes) -> tuple[Optional[str], str]:
    """
    Run acoustic emotion classification on a worker thread.
    include_prosodic=False skips pyin pitch tracking for sub-second execution.
    """
    if not models.speech_clf:
        return None, "Low"
    try:
        res = predict_speech(audio_bytes, include_prosodic=False)
        emotion = res.emotion_detail.detected_emotion
        risk = res.predicted_risk_tier
        logger.info(f"Acoustic emotion: {emotion}, risk: {risk}")
        return emotion, risk
    except Exception as e:
        logger.warning(f"Speech emotion analysis failed (non-fatal): {e}")
        return None, "Low"


VOICE_REFLECTIVE_FALLBACK = (
    "I'm listening carefully to what you're sharing. "
    "What feels most important for you to talk through right now?"
)

VOICE_UNSAFE_RESPONSE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bdiagnos\w*\b",
        r"\b(?:depress(?:ed|ion|ive)|bipolar|schizophrenia|anxiety\s+disorder|ptsd|adhd|ocd)\b",
        r"\b(?:medication|medicine|antidepressant\w*|dosage|prescrib\w*|\d+\s*mg)\b",
        r"\b(?:promise|guarantee\w*|cure[sd]?)\b",
        r"\b(?:you\s+should|you\s+need\s+to|you\s+must)\b",
        r"\b(?:quit\s+your|stop\s+taking|start\s+taking)\b",
        r"\btry\s+(?:journaling|writing|meditating|breathing|grounding|this|that|a|an)\b",
        r"\b(?:do|try)\s+(?:this|that|these)\s+(?:exercise|technique|steps?)\b",
        r"\btake\s+a\s+(?:walk|break|bath|shower|nap)\b",
        r"\bwrite\s+(?:down|about)\b",
        r"\b(?:call|text|contact)\s+(?:a|your)\s+(?:friend|family|counselor|therapist)\b",
        r"\byou\s+(?:can|could|may|might)\s+(?:try|take|practice|stop|start|quit|avoid|use|write|call|text|contact|consult|seek|schedule|consider|breathe)\b",
        r"(?:^|[.!?]\s+|\n\s*)(?:try|take|practice|stop|start|quit|avoid|use|do|write|call|text|contact|consult|seek|schedule|reach\s+out|consider|make|focus|place|name|identify|breathe|ground|remember)\b",
        r"\b(?:this|it)\s+will\s+(?:fix|heal|cure|resolve)\b",
    )
]


def sanitize_voice_response(
    reply: str,
    user_message: str,
    tools_used: list[dict],
    recent_history: Optional[list[dict]] = None,
) -> str:
    """Allow reflective listening or exact approved tool output, never improvised advice."""
    approved_outputs = []
    has_crisis_resources = False
    for tool in tools_used:
        if not isinstance(tool, dict):
            continue
        tool_name = tool.get("tool_name")
        output = str(tool.get("tool_output", "")).strip()
        if (
            tool_name in {"get_cbt_coping_technique", "get_crisis_resources"}
            and output
            and not output.startswith("No techniques found")
        ):
            approved_outputs.append(output)
            has_crisis_resources = has_crisis_resources or tool_name == "get_crisis_resources"

    if approved_outputs:
        prefix = (
            "Your safety matters. Please use these support resources."
            if has_crisis_resources
            else "I'm listening carefully to what you're sharing. "
                 "We can use this structured technique together."
        )
        return f"{prefix}\n" + "\n".join(approved_outputs)

    intent = classify_message_intent(user_message)
    sanitized = validate_and_sanitize_response(
        reply=reply,
        user_message=user_message,
        intent=intent,
        current_stage=STAGE_EXPLORING,
        recent_history=recent_history or [],
    )
    sanitized = re.sub(r"[*_`#]+", "", sanitized).strip()
    if not sanitized or any(
        pattern.search(sanitized) for pattern in VOICE_UNSAFE_RESPONSE_PATTERNS
    ):
        logger.warning("Unsafe or ungrounded voice response replaced with reflective listening")
        return VOICE_REFLECTIVE_FALLBACK
    return sanitized


async def process_voice_turn(
    session_id: int,
    user_id: str,
    audio_bytes: bytes,
    filename: str = "audio.webm",
) -> dict:
    """
    Process a single voice therapy turn with maximum parallelism: audio in → audio out.

    Returns dict compatible with VoiceTherapyResponse schema.
    """
    # ── Step 1: Fire Parallel STT, Acoustic Analysis, and Context Prefetch ──
    stt_task = asyncio.create_task(transcribe_audio(audio_bytes, filename=filename))
    speech_task = asyncio.create_task(asyncio.to_thread(_safe_predict_speech, audio_bytes))
    prior_summaries_task = asyncio.create_task(
        asyncio.to_thread(get_recent_session_summaries, user_id, 3)
    )
    session_msgs_task = asyncio.create_task(
        asyncio.to_thread(get_session_messages, session_id)
    )
    assessment_history_task = asyncio.create_task(
        asyncio.to_thread(get_user_assessment_history, user_id, 1)
    )

    # Await transcription and acoustic emotion concurrently
    transcript, (speech_emotion, speech_risk_tier) = await asyncio.gather(
        stt_task, speech_task
    )
    logger.info(f"Voice transcript: {transcript[:60]}...")

    clean_transcript = transcript.strip()
    if not clean_transcript or clean_transcript in (".", "...", "Thank you.", "Thank you for watching!", "[BLANK_AUDIO]"):
        gentle_reply = "I'm listening whenever you're ready to share. Take your time."
        audio_b64 = await synthesize_speech(gentle_reply)
        return {
            "session_id": session_id,
            "transcript": "(gentle pause)",
            "reply_text": gentle_reply,
            "reply_audio_base64": audio_b64,
            "risk_tier": "Low",
            "urgency_level": "STABLE",
            "crisis_activated": False,
            "speech_emotion": speech_emotion or "calm",
            "tools_used": [],
        }

    if clean_transcript == "I heard your voice, but I had trouble catching that clearly. Could you please say that again?":
        gentle_reply = "I heard your voice, but had a little trouble catching that clearly. Could you please say that once more?"
        audio_b64 = await synthesize_speech(gentle_reply)
        return {
            "session_id": session_id,
            "transcript": "(unclear audio)",
            "reply_text": gentle_reply,
            "reply_audio_base64": audio_b64,
            "risk_tier": "Low",
            "urgency_level": "STABLE",
            "crisis_activated": False,
            "speech_emotion": speech_emotion or "calm",
            "tools_used": [],
        }

    # ── Step 2: Instant Text Risk Check on Transcript ─────────────────
    text_risk = predict_text(transcript)
    text_is_crisis = _is_crisis_signal(transcript, text_risk)
    text_risk_tier = text_risk.predicted_risk_tier

    # ── Step 3: Multimodal Risk Gating ────────────────────────────────
    # Life-safety crisis protocol is activated strictly for explicit self-harm / suicidal crisis
    is_crisis = text_is_crisis

    if is_crisis or text_risk_tier == "High" or speech_risk_tier == "High":
        final_risk_tier = "High"
    elif text_risk_tier == "Moderate" or speech_risk_tier == "Moderate":
        final_risk_tier = "Moderate"
    else:
        final_risk_tier = "Low"

    # Persist user message asynchronously without blocking the reply pipeline
    asyncio.create_task(
        asyncio.to_thread(save_therapy_message, session_id, "user", transcript, final_risk_tier)
    )

    # ── Step 4: Crisis Short-Circuit ──────────────────────────────────
    if is_crisis:
        crisis = _build_crisis_response(final_risk_tier, mode="voice")
        asyncio.create_task(
            asyncio.to_thread(save_therapy_message, session_id, "assistant", crisis["reply"])
        )

        audio_b64 = await synthesize_speech(crisis["reply"])

        return {
            "session_id": session_id,
            "transcript": transcript,
            "reply_text": crisis["reply"],
            "reply_audio_base64": audio_b64,
            "risk_tier": final_risk_tier,
            "urgency_level": "CRITICAL",
            "crisis_activated": True,
            "speech_emotion": speech_emotion,
            "tools_used": crisis["tools_used"],
        }

    # ── Step 5: Build LLM Context from Prefetched DB Results ──────────
    prior_summaries, session_msgs, assessment_history = await asyncio.gather(
        prior_summaries_task, session_msgs_task, assessment_history_task
    )

    llm_messages = []
    assessment_context = _build_assessment_context(
        assessment_history[0] if assessment_history else None
    )
    if assessment_context:
        llm_messages.append({
            "role": "user",
            "content": f"[SYSTEM CONTEXT — do not repeat this to the user]\n{assessment_context}"
        })
        llm_messages.append({
            "role": "assistant",
            "content": "I'll use this historical assessment only when it is relevant."
        })

    # Inject session memory
    if prior_summaries:
        memory = "Previous session context:\n"
        for s in prior_summaries:
            memory += (
                f"- {s.get('mode', '?')} session: {s.get('summary_text', 'N/A')} "
                f"(concerns: {', '.join(s.get('concerns', []))})\n"
            )
        llm_messages.append({
            "role": "user",
            "content": f"[SYSTEM CONTEXT — do not repeat this to the user]\n{memory}"
        })
        llm_messages.append({
            "role": "assistant",
            "content": "I'll keep this context in mind."
        })

    # Inject speech emotion and distress context for therapeutic awareness
    context_notes = []
    if speech_emotion:
        context_notes.append(f"Acoustic analysis detected '{speech_emotion}' in the user's vocal tone.")
    if final_risk_tier in ("High", "Moderate"):
        context_notes.append(f"The user is experiencing {final_risk_tier.lower()} emotional distress.")

    if context_notes:
        note_str = " ".join(context_notes)
        llm_messages.append({
            "role": "user",
            "content": (
                f"[SYSTEM CONTEXT — {note_str} "
                "Use active reflective listening only. Do not diagnose, prescribe, promise outcomes, "
                "or invent therapeutic advice. If a structured exercise is appropriate, invoke "
                "get_cbt_coping_technique instead of writing it yourself. Otherwise, acknowledge "
                "the user's specific experience and ask at most one collaborative follow-up question. "
                "Use plain spoken sentences without markdown.]"
            )
        })
        llm_messages.append({
            "role": "assistant",
            "content": "Understood. I will use reflective listening and approved CBT tools only."
        })

    # Add conversation history
    for msg in session_msgs:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})

    # Add current user message if not already present
    if not session_msgs or session_msgs[-1].get("content") != transcript:
        llm_messages.append({"role": "user", "content": transcript})

    # ── Step 6: Invoke LLM (Voice Mode — ultra-fast generation) ───────
    llm_result = await chat_completion(
        messages=llm_messages,
        mode="voice",
        user_id=user_id,
    )

    tools_used = llm_result.get("tools_used", [])
    reply_text = sanitize_voice_response(
        reply=llm_result.get("reply") or "",
        user_message=transcript,
        tools_used=tools_used,
        recent_history=session_msgs,
    )

    # Persist assistant reply in background
    asyncio.create_task(
        asyncio.to_thread(save_therapy_message, session_id, "assistant", reply_text)
    )

    # ── Step 7: Ultra-fast TTS on Reply ──────────────────────────────
    audio_b64 = await synthesize_speech(reply_text)

    # Determine urgency
    urgency = "WARNING" if final_risk_tier in ("High", "Moderate") else "STABLE"

    return {
        "session_id": session_id,
        "transcript": transcript,
        "reply_text": reply_text,
        "reply_audio_base64": audio_b64,
        "risk_tier": final_risk_tier,
        "urgency_level": urgency,
        "crisis_activated": False,
        "speech_emotion": speech_emotion,
        "tools_used": tools_used,
    }


async def generate_voice_greeting(
    session_id: int,
    user_id: str,
    time_of_day: Optional[str] = None,
) -> dict:
    """
    Generate proactive opening therapist greeting when Voice Therapy starts.
    Greets the user warmly with a time-appropriate greeting and an inviting question.
    """
    if not time_of_day or time_of_day.lower() not in ("morning", "afternoon", "evening"):
        from datetime import datetime
        hour = datetime.now().hour
        if 5 <= hour < 12:
            tod = "morning"
        elif 12 <= hour < 17:
            tod = "afternoon"
        else:
            tod = "evening"
    else:
        tod = time_of_day.lower()

    # Check for recent session memory
    prior_summaries = await asyncio.to_thread(get_recent_session_summaries, user_id, 1)

    if prior_summaries and prior_summaries[0].get("summary_text"):
        greeting_text = (
            f"Hello, good {tod}! Welcome back to your voice session. "
            "I'm EmoCare, and I'm right here with you. "
            "How are you feeling today, and what's on your mind?"
        )
    else:
        greeting_text = (
            f"Hello, good {tod}! Welcome to your voice therapy session. "
            "I'm EmoCare, your personal wellness companion. "
            "How are you feeling today, and what's on your mind?"
        )

    # Persist greeting to DB so it forms part of session memory
    await asyncio.to_thread(
        save_therapy_message, session_id, "assistant", greeting_text
    )

    # Synthesize opening speech
    audio_b64 = await synthesize_speech(greeting_text)

    return {
        "session_id": session_id,
        "greeting_text": greeting_text,
        "audio_base64": audio_b64,
    }
