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


async def synthesize_speech(text: str) -> Optional[str]:
    """
    Convert text to spoken audio via ElevenLabs API.

    Returns base64-encoded audio string (mp3), or None if TTS is unavailable.
    The frontend can decode this to an audio element for playback.
    """
    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL").strip() or "EXAVITQu4vr4xnSDxMaL"
    model_id = os.getenv("ELEVENLABS_MODEL", DEFAULT_TTS_MODEL).strip() or DEFAULT_TTS_MODEL

    if not elevenlabs_api_key:
        logger.info("No ELEVENLABS_API_KEY configured — TTS unavailable")
        return None

    if not text or not text.strip():
        return None

    try:
        import httpx

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.75,        # High stability for calm, consistent delivery
                "similarity_boost": 0.75,  # Natural voice matching
                "style": 0.0,             # Minimal dramatic inflection
                "use_speaker_boost": True,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                audio_bytes = resp.content
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                logger.info(f"TTS audio generated ({len(audio_bytes)} bytes)")
                return audio_b64
            else:
                logger.error(f"ElevenLabs API returned {resp.status_code}: {resp.text[:200]}")
                return None

    except ImportError:
        logger.warning("httpx not installed — TTS unavailable")
        return None
    except Exception as e:
        logger.error(f"TTS synthesis error: {e}")
        return None
