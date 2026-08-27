"""
EmoCare Voice Therapy Pipeline — Full audio-in → audio-out orchestrator.

Flow:
1. Receive raw audio bytes from the frontend
2. In parallel:
   a. Whisper STT → transcript text
   b. SER model (predict_speech) → acoustic emotion + risk
3. Run text risk classifier on transcript (predict_text)
4. Multimodal risk gating: if EITHER acoustic OR text risk is High → crisis protocol
5. Otherwise: invoke LLM with voice-mode system prompt (short, spoken cadence)
6. ElevenLabs TTS on LLM reply → base64 audio response
7. Persist messages and return full response
"""
import logging
from typing import Optional

from .stt_client import transcribe_audio
from .tts_client import synthesize_speech
from ..inference import predict_speech, predict_text
from ..therapy import _build_crisis_response, _is_crisis_signal
from .llm_client import chat_completion
from ..db import (
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
)

logger = logging.getLogger("emocare.voice_therapy")


async def process_voice_turn(
    session_id: int,
    user_id: str,
    audio_bytes: bytes,
) -> dict:
    """
    Process a single voice therapy turn: audio in → audio out.

    Returns dict compatible with VoiceTherapyResponse schema.
    """
    # ── Step 1: Parallel STT + Acoustic Analysis ──────────────────────
    transcript = await transcribe_audio(audio_bytes)
    logger.info(f"Voice transcript: {transcript[:60]}...")

    # Acoustic emotion analysis via existing SER model
    speech_emotion = None
    speech_risk_tier = "Low"
    try:
        speech_result = predict_speech(audio_bytes)
        speech_emotion = speech_result.emotion_detail.detected_emotion
        speech_risk_tier = speech_result.predicted_risk_tier
        logger.info(f"Acoustic emotion: {speech_emotion}, risk: {speech_risk_tier}")
    except Exception as e:
        logger.warning(f"Speech emotion analysis failed (non-fatal): {e}")

    # ── Step 2: Text Risk on Transcript ───────────────────────────────
    text_risk = predict_text(transcript)
    text_is_crisis = _is_crisis_signal(transcript, text_risk)
    text_risk_tier = "High" if text_is_crisis else text_risk.predicted_risk_tier

    # ── Step 3: Multimodal Risk Gating ────────────────────────────────
    # If EITHER acoustic or text signals High → activate crisis protocol
    is_crisis = text_is_crisis or speech_risk_tier == "High"
    final_risk_tier = "High" if is_crisis else text_risk_tier

    # Persist user message (transcript) with risk tier
    save_therapy_message(session_id, "user", transcript, final_risk_tier)

    # ── Step 4: Crisis Short-Circuit ──────────────────────────────────
    if is_crisis:
        crisis = _build_crisis_response(final_risk_tier, mode="voice")
        save_therapy_message(session_id, "assistant", crisis["reply"])

        # TTS on crisis response (best-effort)
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

    # ── Step 5: Build LLM Context (Voice Mode) ───────────────────────
    prior_summaries = get_recent_session_summaries(user_id, limit=3)
    session_msgs = get_session_messages(session_id)

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

    # Inject speech emotion context for LLM awareness
    if speech_emotion:
        llm_messages.append({
            "role": "user",
            "content": (
                f"[SYSTEM CONTEXT — acoustic analysis detected the emotion '{speech_emotion}' "
                f"in the user's voice. Adapt your tone accordingly but do not disclose this to the user.]"
            )
        })
        llm_messages.append({
            "role": "assistant",
            "content": "Understood, I'll be sensitive to that."
        })

    # Add conversation history
    for msg in session_msgs:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})

    # ── Step 6: Invoke LLM (Voice Mode) ──────────────────────────────
    llm_result = await chat_completion(
        messages=llm_messages,
        mode="voice",
        user_id=user_id,
    )

    reply_text = llm_result.get("reply", "I'm here for you. Take your time.")
    tools_used = llm_result.get("tools_used", [])

    # Persist assistant reply
    save_therapy_message(session_id, "assistant", reply_text)

    # ── Step 7: TTS on Reply ─────────────────────────────────────────
    audio_b64 = await synthesize_speech(reply_text)

    # Determine urgency
    urgency = "WARNING" if text_risk_tier == "Moderate" else "STABLE"

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
