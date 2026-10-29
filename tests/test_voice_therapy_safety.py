import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from backend.app.db import create_therapy_session, save_assessment_attempt
from backend.app.engine import llm_client
from backend.app.engine import voice_therapy
from backend.app.engine.voice_therapy import (
    VOICE_REFLECTIVE_FALLBACK,
    sanitize_voice_response,
)
from backend.app.recommendations import COPING_STRATEGIES


def test_voice_sanitizer_rejects_clinical_claims_and_medication_advice():
    reply = (
        "You have bipolar disorder. Stop taking your medication. "
        "I promise this will cure you."
    )
    sanitized = sanitize_voice_response(reply, "I feel awful", [])
    assert sanitized == VOICE_REFLECTIVE_FALLBACK
    assert "bipolar" not in sanitized.lower()
    assert "medication" not in sanitized.lower()
    assert "promise" not in sanitized.lower()


def test_voice_sanitizer_rejects_unregistered_exercises_and_life_advice():
    reply = "You should quit your job. Try journaling for ten minutes and take a walk."
    sanitized = sanitize_voice_response(reply, "Work is stressful", [])
    assert sanitized == VOICE_REFLECTIVE_FALLBACK
    assert "quit" not in sanitized.lower()
    assert "journaling" not in sanitized.lower()
    assert sanitize_voice_response(
        "Practice box breathing and take three slow breaths.",
        "I feel anxious",
        [],
    ) == VOICE_REFLECTIVE_FALLBACK


def test_voice_sanitizer_uses_exact_registered_cbt_tool_output():
    technique = COPING_STRATEGIES["grounding"][0]
    tools_used = [{
        "tool_name": "get_cbt_coping_technique",
        "tool_input": {"category": "grounding"},
        "tool_output": technique,
    }]
    sanitized = sanitize_voice_response(
        "You have depression. Instead, do my invented exercise.",
        "I feel panicky",
        tools_used,
    )
    assert technique in sanitized
    assert "invented exercise" not in sanitized
    assert "depression" not in sanitized


def test_voice_sanitizer_preserves_safe_reflective_listening():
    reply = "The argument with your professor sounds painful. What was the hardest part for you?"
    sanitized = sanitize_voice_response(reply, "My professor scolded me", [])
    assert "professor" in sanitized
    assert "painful" in sanitized
    assert sanitized.count("?") <= 1


def test_anthropic_voice_mode_enables_tool_calling(monkeypatch):
    captured = {}

    class FakeMessages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(text="I am listening.")],
            )

    fake_client = SimpleNamespace(messages=FakeMessages())
    fake_sdk = SimpleNamespace(AsyncAnthropic=lambda api_key: fake_client)
    monkeypatch.setattr(llm_client.importlib, "import_module", lambda _name: fake_sdk)

    result = asyncio.run(llm_client._chat_completion_anthropic(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt=llm_client.SYSTEM_PROMPT_VOICE,
        mode="voice",
        api_key="offline-test-key",
        model="offline-test-model",
    ))

    assert result["reply"] == "I am listening."
    assert captured["tools"] == llm_client.TOOL_DEFINITIONS
    assert "get_cbt_coping_technique" in llm_client.SYSTEM_PROMPT_VOICE
    assert "NEVER invent" in llm_client.SYSTEM_PROMPT_VOICE


def configure_voice_turn(monkeypatch, transcript, llm_result):
    owner = f"voice_safety_{uuid4().hex}"
    session_id = create_therapy_session(owner, "voice")
    assert session_id is not None

    monkeypatch.setattr(
        voice_therapy,
        "transcribe_audio",
        AsyncMock(return_value=transcript),
    )
    monkeypatch.setattr(
        voice_therapy,
        "_safe_predict_speech",
        lambda _audio: ("sad", "Moderate"),
    )
    monkeypatch.setattr(
        voice_therapy,
        "predict_text",
        lambda _text: SimpleNamespace(predicted_risk_tier="Moderate"),
    )
    chat_mock = AsyncMock(return_value=llm_result)
    monkeypatch.setattr(voice_therapy, "chat_completion", chat_mock)
    tts_mock = AsyncMock(return_value="encoded-audio")
    monkeypatch.setattr(voice_therapy, "synthesize_speech", tts_mock)
    save_mock = Mock(return_value=True)
    monkeypatch.setattr(voice_therapy, "save_therapy_message", save_mock)
    return owner, session_id, chat_mock, tts_mock, save_mock


def test_voice_pipeline_persists_and_speaks_only_sanitized_text(monkeypatch):
    owner, session_id, _chat_mock, tts_mock, save_mock = configure_voice_turn(
        monkeypatch,
        "I feel overwhelmed at work.",
        {
            "reply": "You have depression. You should quit your job and stop taking medication.",
            "tools_used": [],
        },
    )

    result = asyncio.run(voice_therapy.process_voice_turn(
        session_id=session_id,
        user_id=owner,
        audio_bytes=b"offline-audio",
    ))
    asyncio.run(asyncio.sleep(0))

    assert result["reply_text"] == VOICE_REFLECTIVE_FALLBACK
    assert tts_mock.await_args.args[0] == result["reply_text"]
    assistant_saves = [
        call for call in save_mock.call_args_list
        if call.args[1] == "assistant"
    ]
    assert assistant_saves[-1].args[2] == result["reply_text"]


def test_voice_crisis_path_bypasses_llm_and_uses_deterministic_resources(monkeypatch):
    owner, session_id, chat_mock, tts_mock, _save_mock = configure_voice_turn(
        monkeypatch,
        "I want to kill myself.",
        {"reply": "Unsafe generated reply", "tools_used": []},
    )

    result = asyncio.run(voice_therapy.process_voice_turn(
        session_id=session_id,
        user_id=owner,
        audio_bytes=b"offline-audio",
    ))

    assert result["crisis_activated"] is True
    assert result["urgency_level"] == "CRITICAL"
    assert "988" in result["reply_text"]
    chat_mock.assert_not_awaited()
    assert tts_mock.await_args.args[0] == result["reply_text"]


def test_voice_pipeline_uses_latest_saved_assessment(monkeypatch):
    owner, session_id, chat_mock, _tts_mock, _save_mock = configure_voice_turn(
        monkeypatch,
        "I feel overwhelmed at work.",
        {
            "reply": "Work sounds overwhelming. What has been the hardest part for you?",
            "tools_used": [],
        },
    )
    attempt_id = save_assessment_attempt(
        user_id=owner,
        test_type="gad7",
        responses=[2, 2, 2, 2, 1, 1, 1],
        total_score=11,
        severity_band="Moderate",
        risk_tier="Moderate",
        llm_summary="Excessive worry and difficulty relaxing were reported.",
    )
    assert attempt_id is not None

    asyncio.run(voice_therapy.process_voice_turn(
        session_id=session_id,
        user_id=owner,
        audio_bytes=b"offline-audio",
    ))

    messages = chat_mock.await_args.kwargs["messages"]
    context = "\n".join(str(message.get("content", "")) for message in messages)
    assert "LATEST SAVED SELF-ASSESSMENT" in context
    assert "GAD-7" in context
    assert "11/21" in context
    assert "severity: Moderate" in context
    assert "Saved result summary: Excessive worry and difficulty relaxing were reported." in context
    assert "HISTORICAL CONTEXT ONLY" in context
