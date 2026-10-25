"""
EmoCare Voice Therapy Pipeline — Ultra-fast parallel audio-in → audio-out orchestrator.

Latency Optimizations:
1. True parallel execution: Whisper STT, acoustic emotion analysis, and database session memory
   all execute concurrently at turn start.
2. Acoustic SER runs on a background worker thread with prosodic pyin calculation disabled.
3. Database writes (message persistence) are fire-and-forget background tasks.
4. Persistent connection pool reuses TCP/TLS sessions for STT, LLM, and TTS.
5. Voice-mode LLM tokens are capped at 120 tokens with a concise spoken cadence prompt.
6. ElevenLabs TTS uses flash v2.5 with optimize_streaming_latency=4 and voice-optimized 22kHz format.
"""
import asyncio
import logging
from typing import Optional

from .stt_client import transcribe_audio
from .tts_client import synthesize_speech
from ..inference import predict_speech, predict_text
from ..model_loader import models
from ..therapy import _build_crisis_response, _is_crisis_signal
from .llm_client import chat_completion
from ..db import (
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
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
    prior_summaries, session_msgs = await asyncio.gather(
        prior_summaries_task, session_msgs_task
    )

    llm_messages = []

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
                "Act like a skilled, compassionate therapist: "
                "1) Briefly acknowledge and validate their emotion with genuine warmth. "
                "2) Actively provide a practical coping suggestion, cognitive reframing, or actionable strategy to manage the situation. "
                "3) Ask an insightful, collaborative follow-up question to help them reflect deeper or try out the suggestion. "
                "Keep the spoken response natural, warm, conversational (2-4 spoken sentences), and free of markdown or asterisks.]"
            )
        })
        llm_messages.append({
            "role": "assistant",
            "content": "Understood. I will validate warmly, offer an actionable coping suggestion, and ask an insightful follow-up question."
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

    reply_text = llm_result.get("reply") or "I hear what you are experiencing, and I am right here with you. How can I best support you right now?"
    tools_used = llm_result.get("tools_used", [])

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
