"""
EmoCare TTS Client — Text-to-Speech via ElevenLabs API.

Converts LLM text responses to spoken audio for the voice therapy pipeline.
Uses ElevenLabs fast flash v2.5 model with a calm, warm preset voice.
Falls back to None (no audio) when no API key is configured.
"""
import os
import io
import base64
import logging
from typing import Optional

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

logger = logging.getLogger("emocare.tts")

# Use ElevenLabs Flash v2.5 for ultra-low latency & ultra-realistic speech
DEFAULT_TTS_MODEL = "eleven_flash_v2_5"


import re

def _clean_spoken_text(text: str) -> str:
    """Strip markdown formatting and special characters that sound awkward in TTS."""
    # Remove asterisks, hashtags, underscores, backticks, brackets
    cleaned = re.sub(r"[\*#_`~>\[\]]", "", text)
    # Remove multiple spaces/newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


async def synthesize_speech(text: str) -> Optional[str]:
    """
    Convert text to spoken audio via ElevenLabs API using ultra-low latency settings.

    Returns base64-encoded audio string (mp3), or None if TTS is unavailable.
    """
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL").strip() or "EXAVITQu4vr4xnSDxMaL"
    model_id = os.getenv("ELEVENLABS_MODEL", DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL

    if not elevenlabs_api_key:
        logger.info("No ELEVENLABS_API_KEY configured — TTS unavailable")
        return None

    cleaned_text = _clean_spoken_text(text)
    if not cleaned_text:
        return None

    try:
        from .http_pool import get_shared_client
        client = get_shared_client()

        # optimize_streaming_latency=4 enables maximum speed tier
        # output_format=mp3_22050_32 is optimized for voice bandwidth & ultra-fast transfer
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            "?optimize_streaming_latency=4&output_format=mp3_22050_32"
        )
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": cleaned_text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.70,        # Balanced stability for natural cadence
                "similarity_boost": 0.75,  # Natural voice tone
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            audio_bytes = resp.content
            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
            logger.info(f"TTS audio generated ({len(audio_bytes)} bytes) in ultra-low latency mode")
            return audio_b64
        else:
            logger.error(f"ElevenLabs API returned {resp.status_code}: {resp.text[:200]}")
            return None

    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        return None
