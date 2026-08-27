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

logger = logging.getLogger("emocare.stt")

GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

OPENAI_WHISPER_MODEL = "whisper-1"
OPENAI_STT_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    Transcribe audio bytes to text.

    Tries Groq (free) first, then OpenAI, then returns a mock transcript.
    """
    # Read dynamically so any runtime env updates are immediately recognized
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    # ── 1. Groq Whisper (FREE) ────────────────────────────────────────
    if groq_key:
        result = await _transcribe_groq(audio_bytes, filename, groq_key)
        if result is not None:
            return result

    # ── 2. OpenAI Whisper (paid fallback) ─────────────────────────────
    if openai_key:
        result = await _transcribe_openai(audio_bytes, filename, openai_key)
        if result is not None:
            return result

    # ── 3. No API keys configured ────────────────────────────────────
    logger.warning(
        "No STT API key configured. Set GROQ_API_KEY (free at console.groq.com) "
        "in your .env for real speech-to-text transcription."
    )
    return _mock_transcribe()


# ═══════════════════════════════════════════════════════════════════════
# GROQ WHISPER (FREE)
# ═══════════════════════════════════════════════════════════════════════

async def _transcribe_groq(audio_bytes: bytes, filename: str, groq_key: str) -> Optional[str]:
    """Transcribe via Groq's free Whisper endpoint."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GROQ_STT_URL,
                headers={"Authorization": f"Bearer {groq_key}"},
                data={
                    "model": GROQ_WHISPER_MODEL,
                    "response_format": "text",
                    "language": "en",
                },
                files={"file": (filename, audio_bytes)},
            )

            if resp.status_code == 200:
                transcript = resp.text.strip()
                logger.info(f"Groq Whisper transcript ({len(transcript)} chars): {transcript[:80]}...")
                return transcript
            else:
                logger.error(f"Groq Whisper API returned {resp.status_code}: {resp.text[:200]}")
                return None

    except Exception as e:
        logger.error(f"Groq Whisper error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# OPENAI WHISPER (PAID FALLBACK)
# ═══════════════════════════════════════════════════════════════════════

async def _transcribe_openai(audio_bytes: bytes, filename: str, openai_key: str) -> Optional[str]:
    """Transcribe via OpenAI Whisper API (paid)."""
    # Try SDK first
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=openai_key)

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

    # Fallback: direct HTTP
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                OPENAI_STT_URL,
                headers={"Authorization": f"Bearer {openai_key}"},
                data={"model": OPENAI_WHISPER_MODEL, "response_format": "text"},
                files={"file": (filename, audio_bytes)},
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
