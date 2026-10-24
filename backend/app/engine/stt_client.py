"""
EmoCare STT Client — Speech-to-Text transcription.

Provider priority:
1. Groq Whisper  (free — whisper-large-v3-turbo)
2. OpenAI Whisper (paid — whisper-1)
3. Deterministic offline fallback

Set GROQ_API_KEY (free at console.groq.com) for real transcription at zero cost.
"""
import os
import io
import logging
import importlib
from typing import Optional

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

logger = logging.getLogger("emocare.stt")

GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

OPENAI_WHISPER_MODEL = "whisper-1"
OPENAI_STT_URL = "https://api.openai.com/v1/audio/transcriptions"


def _detect_content_type(filename: str, audio_bytes: bytes) -> tuple[str, str]:
    """
    Return normalized (filename, content_type) based on magic bytes or file extension.
    Ensures STT endpoints receive valid audio MIME types rather than video/webm.
    """
    if audio_bytes.startswith(b"RIFF"):
        name = filename if filename.lower().endswith(".wav") else "recording.wav"
        return (name, "audio/wav")
    if audio_bytes.startswith(b"\x1aE\xdf\xa3"):
        name = filename if filename.lower().endswith(".webm") else "recording.webm"
        return (name, "audio/webm")
    if audio_bytes.startswith(b"OggS"):
        name = filename if filename.lower().endswith(".ogg") else "recording.ogg"
        return (name, "audio/ogg")
    if audio_bytes.startswith(b"ID3") or (len(audio_bytes) >= 2 and audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
        name = filename if filename.lower().endswith(".mp3") else "recording.mp3"
        return (name, "audio/mpeg")
    if len(audio_bytes) > 8 and audio_bytes[4:8] == b"ftyp":
        name = filename if filename.lower().endswith((".m4a", ".mp4")) else "recording.m4a"
        return (name, "audio/mp4")

    # Fallback to extension matching
    ext = os.path.splitext(filename)[1].lower()
    ext_types = {
        ".wav": "audio/wav",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".mp4": "audio/mp4",
    }
    return (filename, ext_types.get(ext, "application/octet-stream"))


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio bytes to text.

    Tries Groq (free) first, then OpenAI, then returns a mock transcript.
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not groq_key:
        try:
            _dotenv = importlib.import_module("dotenv")
            _load_dotenv = getattr(_dotenv, "load_dotenv", None)
            if _load_dotenv:
                for candidate in [
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")),
                    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
                    os.path.abspath(".env"),
                ]:
                    if os.path.exists(candidate):
                        _load_dotenv(candidate, override=True)
                        break
                groq_key = os.getenv("GROQ_API_KEY", "").strip()
                openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        except Exception:
            pass

    # Guard against empty or tiny audio snippets (< 1.2 KB)
    if not audio_bytes or len(audio_bytes) < 1200:
        logger.warning(f"Audio payload too small ({len(audio_bytes) if audio_bytes else 0} bytes); treating as silence")
        return ""

    # Normalize filename and MIME type
    norm_filename, content_type = _detect_content_type(filename, audio_bytes)

    # ── 1. Groq Whisper (FREE) ────────────────────────────────────────
    if groq_key:
        result = await _transcribe_groq(audio_bytes, norm_filename, content_type, groq_key)
        if result is not None:
            return result
        logger.warning("Groq Whisper API call failed; attempting fallback")

    # ── 2. OpenAI Whisper (paid fallback) ─────────────────────────────
    if openai_key:
        result = await _transcribe_openai(audio_bytes, norm_filename, content_type, openai_key)
        if result is not None:
            return result
        logger.warning("OpenAI Whisper API call failed")

    if groq_key or openai_key:
        return "I heard your voice, but I had trouble catching that clearly. Could you please say that again?"

    # ── 3. No API keys configured ────────────────────────────────────
    logger.warning(
        "No STT API key configured. Set GROQ_API_KEY (free at console.groq.com) "
        "in your .env for real speech-to-text transcription."
    )
    return _mock_transcribe()


# ═══════════════════════════════════════════════════════════════════════
# GROQ WHISPER (FREE)
# ═══════════════════════════════════════════════════════════════════════

async def _transcribe_groq(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    groq_key: str,
) -> Optional[str]:
    """Transcribe via Groq's free Whisper endpoint with network retry support."""
    from .http_pool import get_shared_client, close_shared_client
    import asyncio

    for attempt in range(2):
        try:
            client = get_shared_client()
            resp = await client.post(
                GROQ_STT_URL,
                headers={"Authorization": f"Bearer {groq_key}"},
                data={
                    "model": GROQ_WHISPER_MODEL,
                    "response_format": "text",
                    "language": "en",
                },
                files={"file": (filename, audio_bytes, content_type)},
            )

            if resp.status_code == 200:
                transcript = resp.text.strip()
                logger.info(f"Groq Whisper transcript ({len(transcript)} chars): {transcript[:80]}...")
                return transcript
            elif resp.status_code in (400, 401, 403, 404, 422):
                logger.error(f"Groq Whisper API returned {resp.status_code}: {resp.text[:200]}")
                return None
            else:
                logger.warning(f"Groq Whisper API returned {resp.status_code} on attempt {attempt + 1}: {resp.text[:200]}")
                if attempt == 0:
                    await close_shared_client()
                    await asyncio.sleep(0.3)

        except Exception as e:
            logger.warning(f"Groq Whisper attempt {attempt + 1} failed: {e}")
            if attempt == 0:
                await close_shared_client()
                await asyncio.sleep(0.3)

    return None


# ═══════════════════════════════════════════════════════════════════════
# OPENAI WHISPER (PAID FALLBACK)
# ═══════════════════════════════════════════════════════════════════════

async def _transcribe_openai(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    openai_key: str,
) -> Optional[str]:
    """Transcribe via OpenAI Whisper API (paid)."""
    # Try SDK dynamically if installed
    try:
        openai_mod = importlib.import_module("openai")
        client = openai_mod.AsyncOpenAI(api_key=openai_key)

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        response = await client.audio.transcriptions.create(
            model=OPENAI_WHISPER_MODEL,
            file=audio_file,
            response_format="text",
        )
        transcript = response.strip() if isinstance(response, str) else str(response).strip()
        logger.info(f"OpenAI Whisper transcript ({len(transcript)} chars): {transcript[:80]}...")
        return transcript

    except ImportError:
        pass
    except Exception as e:
        logger.error(f"OpenAI Whisper SDK error: {e}")

    # Fallback: pooled HTTP client
    try:
        from .http_pool import get_shared_client
        client = get_shared_client()
        resp = await client.post(
            OPENAI_STT_URL,
            headers={"Authorization": f"Bearer {openai_key}"},
            data={"model": OPENAI_WHISPER_MODEL, "response_format": "text"},
            files={"file": (filename, audio_bytes, content_type)},
        )
        if resp.status_code == 200:
            transcript = resp.text.strip()
            logger.info(f"OpenAI Whisper httpx transcript ({len(transcript)} chars)")
            return transcript
        else:
            logger.error(f"OpenAI Whisper API returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.error(f"OpenAI Whisper httpx error: {e}")

    return None


# ═══════════════════════════════════════════════════════════════════════
# OFFLINE MOCK FALLBACK
# ═══════════════════════════════════════════════════════════════════════

def _mock_transcribe() -> str:
    """Offline fallback — returns a safe placeholder transcript."""
    return (
        "[Voice input received — real transcription requires a free GROQ_API_KEY. "
        "Get one at console.groq.com and add it to your .env file.]"
    )
