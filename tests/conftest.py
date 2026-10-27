"""
Shared pytest fixtures for EmoCare test suite.

Ensures:
- All tests run 100% offline (no live Groq/OpenAI/ElevenLabs API calls)
- DATABASE_URL is forced empty so tests use in-process SQLite
- API keys are cleared to guarantee deterministic offline LLM fallback
"""
import os
import pytest


# ── Force offline mode for all tests ──
# Clear all LLM/TTS API keys before any test imports happen
_API_KEY_ENVVARS = [
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "ELEVENLABS_API_KEY",
    "DATABASE_URL",
]


@pytest.fixture(autouse=True)
def enforce_offline_mode(monkeypatch):
    """Ensure no live API calls are made during tests.

    - Clears all LLM provider API keys so chat_completion always
      uses the deterministic offline fallback.
    - Forces DATABASE_URL="" so tests use local SQLite only.
    """
    for key in _API_KEY_ENVVARS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("SUPABASE_URL", "https://test-project.supabase.co")
    monkeypatch.setenv(
        "SUPABASE_JWT_SECRET",
        "test-supabase-secret-with-at-least-32-bytes",
    )
    monkeypatch.setenv(
        "GUEST_SESSION_SECRET",
        "test-guest-secret-with-at-least-32-bytes",
    )
    yield
