import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth_helpers import auth_headers
from backend.app import db, main, therapy
from backend.app.engine import voice_therapy


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolate_checkin_database(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "")
    monkeypatch.setattr(db, "_pg_available", False)
    monkeypatch.setattr(db, "SQLITE_DB_PATH", str(tmp_path / "checkins.db"))


def checkin_payload(local_date="2026-10-29", **overrides):
    payload = {
        "local_date": local_date,
        "mood_rating": 3,
        "stress_level": 4,
        "sleep_quality": 2,
        "energy_level": 2,
        "notes": "A difficult workday",
    }
    payload.update(overrides)
    return payload


def save_checkin(owner, local_date, mood=3, notes=""):
    return db.save_daily_checkin(
        user_id=owner,
        local_date=date.fromisoformat(local_date),
        mood_rating=mood,
        stress_level=4,
        sleep_quality=2,
        energy_level=2,
        notes=notes,
    )


def test_first_checkin_and_reauthentication_status():
    owner = f"checkin_{uuid4().hex}"
    other_user = f"checkin_{uuid4().hex}"
    params = {"local_date": "2026-10-29"}

    first = client.get(
        "/api/checkins/today", params=params, headers=auth_headers(owner)
    )
    assert first.status_code == 200
    assert first.json() == {
        "local_date": "2026-10-29",
        "completed": False,
        "check_in": None,
    }

    created = client.post(
        "/api/checkins",
        json=checkin_payload(sleep_hours=6.5, activity_level=2),
        headers=auth_headers(owner),
    )
    assert created.status_code == 200
    saved = created.json()
    assert saved["user_id"] == owner
    assert saved["local_date"] == "2026-10-29"
    assert saved["mood_rating"] == 3
    assert saved["stress_level"] == 4
    assert saved["sleep_quality"] == 2
    assert saved["energy_level"] == 2
    assert saved["sleep_hours"] == 6.5
    assert saved["notes"] == "A difficult workday"

    logged_in_again = client.get(
        "/api/checkins/today", params=params, headers=auth_headers(owner)
    )
    assert logged_in_again.status_code == 200
    assert logged_in_again.json()["completed"] is True
    assert logged_in_again.json()["check_in"]["id"] == saved["id"]

    isolated = client.get(
        "/api/checkins/today", params=params, headers=auth_headers(other_user)
    )
    assert isolated.status_code == 200
    assert isolated.json()["completed"] is False


def test_same_user_and_local_date_updates_instead_of_duplicating():
    owner = f"checkin_{uuid4().hex}"
    headers = auth_headers(owner)

    first = client.post(
        "/api/checkins", json=checkin_payload(), headers=headers
    )
    updated = client.post(
        "/api/checkins",
        json=checkin_payload(mood_rating=5, notes="  Feeling better  "),
        headers=headers,
    )

    assert first.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["id"] == first.json()["id"]
    assert updated.json()["mood_rating"] == 5
    assert updated.json()["notes"] == "Feeling better"
    history = db.get_recent_daily_checkins(owner)
    assert len(history) == 1
    assert history[0]["mood_rating"] == 5


def test_checkin_requires_auth_and_a_valid_local_date():
    owner = f"checkin_{uuid4().hex}"
    unauthenticated = client.get(
        "/api/checkins/today", params={"local_date": "2026-10-29"}
    )
    invalid_date = client.get(
        "/api/checkins/today",
        params={"local_date": "29-10-2026"},
        headers=auth_headers(owner),
    )
    invalid_rating = client.post(
        "/api/checkins",
        json=checkin_payload(mood_rating=6),
        headers=auth_headers(owner),
    )

    assert unauthenticated.status_code == 401
    assert invalid_date.status_code == 422
    assert invalid_rating.status_code == 422


def test_checkin_api_errors_return_safe_service_unavailable(monkeypatch):
    owner = f"checkin_{uuid4().hex}"
    headers = auth_headers(owner)

    def failed_lookup(*_args):
        raise RuntimeError("offline test failure")

    monkeypatch.setattr(main, "get_daily_checkin", failed_lookup)
    status = client.get(
        "/api/checkins/today",
        params={"local_date": "2026-10-29"},
        headers=headers,
    )
    assert status.status_code == 503
    assert status.json()["detail"] == "Daily check-in is temporarily unavailable"

    monkeypatch.setattr(main, "save_daily_checkin", lambda **_kwargs: None)
    saved = client.post("/api/checkins", json=checkin_payload(), headers=headers)
    assert saved.status_code == 503
    assert saved.json()["detail"] == "Unable to save daily check-in right now"


def test_chat_prompt_contains_latest_and_recent_checkins(monkeypatch):
    owner = f"checkin_{uuid4().hex}"
    other_user = f"checkin_{uuid4().hex}"
    session_id = db.create_therapy_session(owner, "chat")
    save_checkin(owner, "2026-10-28", mood=3, notes="Yesterday's note")
    save_checkin(owner, "2026-10-29", mood=2, notes="Today's note")
    save_checkin(other_user, "2026-10-29", mood=1, notes="Another user's private note")

    chat_mock = AsyncMock(return_value={
        "reply": "Work sounds overwhelming. What has been the hardest part?",
        "tools_used": [],
    })
    monkeypatch.setattr(therapy, "chat_completion", chat_mock)
    monkeypatch.setattr(
        therapy,
        "predict_text",
        lambda _text: SimpleNamespace(predicted_risk_tier="Low", confidence=0.9),
    )

    asyncio.run(therapy.process_chat_turn(
        session_id=session_id,
        user_id=owner,
        user_message="Work has been overwhelming lately.",
    ))

    context = chat_mock.await_args.kwargs["messages"][0]["content"]
    assert "DAILY WELLBEING CHECK-INS" in context
    assert "Latest: 2026-10-29: mood 2/5" in context
    assert 'Self-reported note: "Today\'s note"' in context
    assert "2026-10-28: mood 3/5" in context
    assert "Another user's private note" not in context
    assert "use them to diagnose" in context


def test_voice_prompt_contains_latest_and_recent_checkins(monkeypatch):
    owner = f"checkin_{uuid4().hex}"
    session_id = db.create_therapy_session(owner, "voice")
    save_checkin(owner, "2026-10-28", mood=3, notes="Earlier voice note")
    save_checkin(owner, "2026-10-29", mood=2, notes="Latest voice note")

    monkeypatch.setattr(
        voice_therapy,
        "transcribe_audio",
        AsyncMock(return_value="Work has been overwhelming lately."),
    )
    monkeypatch.setattr(voice_therapy, "_safe_predict_speech", lambda _audio: ("calm", "Low"))
    monkeypatch.setattr(
        voice_therapy,
        "predict_text",
        lambda _text: SimpleNamespace(predicted_risk_tier="Low"),
    )
    chat_mock = AsyncMock(return_value={
        "reply": "Work sounds overwhelming. What feels hardest today?",
        "tools_used": [],
    })
    monkeypatch.setattr(voice_therapy, "chat_completion", chat_mock)
    monkeypatch.setattr(voice_therapy, "synthesize_speech", AsyncMock(return_value="audio"))
    monkeypatch.setattr(voice_therapy, "save_therapy_message", Mock(return_value=1))

    result = asyncio.run(voice_therapy.process_voice_turn(
        session_id=session_id,
        user_id=owner,
        audio_bytes=b"offline audio",
    ))

    assert result["reply_text"] == "Work sounds overwhelming. What feels hardest today?"
    context = "\n".join(
        str(message.get("content", ""))
        for message in chat_mock.await_args.kwargs["messages"]
    )
    assert "DAILY WELLBEING CHECK-INS" in context
    assert "Latest: 2026-10-29: mood 2/5" in context
    assert "Latest voice note" in context
    assert "2026-10-28: mood 3/5" in context
    assert "Earlier voice note" in context


def test_context_failures_do_not_break_chat_or_voice(monkeypatch):
    def failed_history(*_args, **_kwargs):
        raise RuntimeError("offline test failure")

    monkeypatch.setattr(therapy, "get_recent_daily_checkins", failed_history)
    monkeypatch.setattr(
        therapy,
        "predict_text",
        lambda _text: SimpleNamespace(predicted_risk_tier="Low", confidence=0.9),
    )
    chat_mock = AsyncMock(return_value={
        "reply": "Work sounds overwhelming. What feels hardest today?",
        "tools_used": [],
    })
    monkeypatch.setattr(therapy, "chat_completion", chat_mock)

    chat_owner = f"checkin_{uuid4().hex}"
    chat_session = db.create_therapy_session(chat_owner, "chat")
    chat_result = asyncio.run(therapy.process_chat_turn(
        session_id=chat_session,
        user_id=chat_owner,
        user_message="Work has been overwhelming lately.",
    ))
    assert chat_result["reply"] == "Work sounds overwhelming. What feels hardest today?"
    chat_context = chat_mock.await_args.kwargs["messages"][0]["content"]
    assert "DAILY WELLBEING CHECK-INS" not in chat_context

    voice_owner = f"checkin_{uuid4().hex}"
    voice_session = db.create_therapy_session(voice_owner, "voice")
    monkeypatch.setattr(
        voice_therapy,
        "transcribe_audio",
        AsyncMock(return_value="Work has been overwhelming lately."),
    )
    monkeypatch.setattr(voice_therapy, "_safe_predict_speech", lambda _audio: (None, "Low"))
    monkeypatch.setattr(
        voice_therapy,
        "predict_text",
        lambda _text: SimpleNamespace(predicted_risk_tier="Low"),
    )
    voice_chat_mock = AsyncMock(return_value={
        "reply": "Work sounds overwhelming. What feels hardest today?",
        "tools_used": [],
    })
    monkeypatch.setattr(voice_therapy, "chat_completion", voice_chat_mock)
    monkeypatch.setattr(voice_therapy, "synthesize_speech", AsyncMock(return_value="audio"))
    monkeypatch.setattr(voice_therapy, "save_therapy_message", Mock(return_value=1))

    voice_result = asyncio.run(voice_therapy.process_voice_turn(
        session_id=voice_session,
        user_id=voice_owner,
        audio_bytes=b"offline audio",
    ))
    assert voice_result["reply_text"] == "Work sounds overwhelming. What feels hardest today?"
    voice_chat_mock.assert_awaited_once()
