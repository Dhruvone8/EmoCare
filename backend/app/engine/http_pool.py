"""
EmoCare HTTP Client Pool — Shared persistent connection pool for external AI services.

Reuses open TCP/TLS connections to api.groq.com and api.elevenlabs.io,
eliminating repeat connection handshakes (~300-600ms per call).
"""
import logging
from typing import Optional
import httpx

logger = logging.getLogger("emocare.http_pool")

_client: Optional[httpx.AsyncClient] = None


def get_shared_client() -> httpx.AsyncClient:
    """Get or create the singleton AsyncClient with keep-alive connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=5.0),
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=40,
                keepalive_expiry=60.0,
            ),
        )
    return _client


async def close_shared_client() -> None:
    """Close the shared client cleanly during shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


async def warmup_connections() -> None:
    """
    Pre-warm connections and DNS to Groq and ElevenLabs in background on startup.
    This ensures the very first voice request does not experience a cold-start handshake.
    """
    import os
    client = get_shared_client()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()

    try:
        # Pre-connect to Groq
        headers = {"Authorization": f"Bearer {groq_key}"} if groq_key else {}
        await client.get("https://api.groq.com/openai/v1/models", headers=headers, timeout=3.0)
    except Exception as e:
        logger.debug(f"Groq warmup ping: {e}")

    try:
        # Pre-connect to ElevenLabs
        headers = {"xi-api-key": eleven_key} if eleven_key else {}
        await client.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=3.0)
    except Exception as e:
        logger.debug(f"ElevenLabs warmup ping: {e}")

    logger.info("External AI connection pool pre-warmed.")
