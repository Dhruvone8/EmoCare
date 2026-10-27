from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth_helpers import (
    TEST_SUPABASE_SECRET,
    auth_headers,
    make_guest_token,
    make_supabase_token,
)
from backend.app.db import create_therapy_session, get_therapy_session
from backend.app.main import app

client = TestClient(app)


def user_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def assessment_payload(owner_id: str) -> dict:
    return {
        "user_id": owner_id,
        "test_type": "phq9",
        "responses": [0] * 9,
    }


@pytest.mark.parametrize(
    "method,endpoint,kwargs",
    [
        ("POST", "/api/assessment/submit", {"json": assessment_payload("user_b")}),
        ("GET", "/api/assessment/history/user_b", {}),
        ("POST", "/api/therapy/session/start", {"json": {"user_id": "user_b", "mode": "chat"}}),
        ("POST", "/api/therapy/session/end", {"json": {"session_id": 1, "user_id": "user_b"}}),
        ("GET", "/api/therapy/sessions/user_b", {}),
        ("GET", "/api/therapy/session/1/messages", {}),
        ("POST", "/api/chat/message", {"json": {"session_id": 1, "user_id": "user_b", "message": "hello"}}),
        (
            "POST",
            "/api/voice-therapy/interact",
            {
                "data": {"session_id": "1", "user_id": "user_b"},
                "files": {"audio": ("voice.wav", b"audio", "audio/wav")},
            },
        ),
        ("POST", "/api/voice-therapy/greeting", {"json": {"session_id": 1, "user_id": "user_b"}}),
    ],
)
def test_clinical_routes_require_authentication(method, endpoint, kwargs):
    response = client.request(method, endpoint, **kwargs)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_tampered_and_wrongly_signed_tokens_are_rejected():
    owner = user_id("owner")
    expired = make_supabase_token(owner, expires_delta=timedelta(minutes=-10))
    tampered = make_supabase_token(owner)[:-2] + "xx"
    wrong_key = make_supabase_token(owner, secret="wrong-secret-with-at-least-32-bytes")
    expired_guest = make_guest_token(
        f"guest_{uuid4().hex}",
        expires_delta=timedelta(minutes=-10),
    )

    for token in (expired, tampered, wrong_key, expired_guest):
        response = client.get(
            f"/api/assessment/history/{owner}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


def test_assessment_routes_reject_idor_and_allow_owner():
    owner = user_id("owner")
    other = user_id("other")

    submit_as_other = client.post(
        "/api/assessment/submit",
        json=assessment_payload(other),
        headers=auth_headers(owner),
    )
    assert submit_as_other.status_code == 403

    history_as_other = client.get(
        f"/api/assessment/history/{other}",
        headers=auth_headers(owner),
    )
    assert history_as_other.status_code == 403

    submit_as_owner = client.post(
        "/api/assessment/submit",
        json=assessment_payload(owner),
        headers=auth_headers(owner),
    )
    assert submit_as_owner.status_code == 200
    assert submit_as_owner.json()["user_id"] == owner

    history_as_owner = client.get(
        f"/api/assessment/history/{owner}",
        headers=auth_headers(owner),
    )
    assert history_as_owner.status_code == 200
    assert history_as_owner.json()["count"] >= 1


def test_session_start_and_list_reject_idor():
    owner = user_id("owner")
    other = user_id("other")

    start_response = client.post(
        "/api/therapy/session/start",
        json={"user_id": other, "mode": "chat"},
        headers=auth_headers(owner),
    )
    assert start_response.status_code == 403

    list_response = client.get(
        f"/api/therapy/sessions/{other}",
        headers=auth_headers(owner),
    )
    assert list_response.status_code == 403


def test_session_routes_reject_cross_user_reads_and_writes():
    owner = user_id("owner")
    other = user_id("other")
    session_id = create_therapy_session(other, "chat")
    assert session_id is not None

    response = client.get(
        f"/api/therapy/session/{session_id}/messages",
        headers=auth_headers(owner),
    )
    assert response.status_code == 403

    response = client.post(
        "/api/therapy/session/end",
        json={"session_id": session_id, "user_id": other},
        headers=auth_headers(owner),
    )
    assert response.status_code == 403
    assert get_therapy_session(session_id)["ended_at"] is None

    response = client.post(
        "/api/chat/message",
        json={"session_id": session_id, "user_id": other, "message": "hello"},
        headers=auth_headers(owner),
    )
    assert response.status_code == 403

    response = client.post(
        "/api/voice-therapy/greeting",
        json={"session_id": session_id, "user_id": other},
        headers=auth_headers(owner),
    )
    assert response.status_code == 403

    response = client.post(
        "/api/voice-therapy/interact",
        data={"session_id": str(session_id), "user_id": other},
        files={"audio": ("voice.wav", b"audio", "audio/wav")},
        headers=auth_headers(owner),
    )
    assert response.status_code == 403


def test_missing_session_returns_404_for_authenticated_user():
    owner = user_id("owner")
    response = client.get(
        "/api/therapy/session/999999999/messages",
        headers=auth_headers(owner),
    )
    assert response.status_code == 404


def test_guest_tokens_are_server_generated_and_owner_scoped():
    first_guest = client.post("/api/auth/guest")
    second_guest = client.post("/api/auth/guest")
    assert first_guest.status_code == 200
    assert second_guest.status_code == 200

    first = first_guest.json()
    second = second_guest.json()
    assert first["user_id"].startswith("guest_")
    assert first["user_id"] != second["user_id"]

    start_response = client.post(
        "/api/therapy/session/start",
        json={"user_id": first["user_id"], "mode": "chat"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    cross_guest_response = client.get(
        f"/api/therapy/session/{session_id}/messages",
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert cross_guest_response.status_code == 403


def test_authorized_owner_clinical_flow(monkeypatch):
    owner = user_id("owner")
    start_response = client.post(
        "/api/therapy/session/start",
        json={"user_id": owner, "mode": "voice"},
        headers=auth_headers(owner),
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["session_id"]

    messages_response = client.get(
        f"/api/therapy/session/{session_id}/messages",
        headers=auth_headers(owner),
    )
    assert messages_response.status_code == 200
    assert len(messages_response.json()["messages"]) == 1

    sessions_response = client.get(
        f"/api/therapy/sessions/{owner}",
        headers=auth_headers(owner),
    )
    assert sessions_response.status_code == 200
    assert any(item["id"] == session_id for item in sessions_response.json()["sessions"])

    chat_mock = AsyncMock(return_value={
        "session_id": session_id,
        "reply": "I am listening.",
        "risk_tier": "Low",
        "urgency_level": "STABLE",
        "crisis_activated": False,
        "tools_used": [],
    })
    monkeypatch.setattr("backend.app.main.process_chat_turn", chat_mock)
    chat_response = client.post(
        "/api/chat/message",
        json={"session_id": session_id, "user_id": owner, "message": "hello"},
        headers=auth_headers(owner),
    )
    assert chat_response.status_code == 200
    assert chat_mock.await_args.kwargs["user_id"] == owner

    voice_mock = AsyncMock(return_value={
        "session_id": session_id,
        "transcript": "hello",
        "reply_text": "I am listening.",
        "reply_audio_base64": None,
        "risk_tier": "Low",
        "urgency_level": "STABLE",
        "crisis_activated": False,
        "speech_emotion": "calm",
        "tools_used": [],
    })
    monkeypatch.setattr("backend.app.main.process_voice_turn", voice_mock)
    voice_response = client.post(
        "/api/voice-therapy/interact",
        data={"session_id": str(session_id), "user_id": owner},
        files={"audio": ("voice.wav", b"audio", "audio/wav")},
        headers=auth_headers(owner),
    )
    assert voice_response.status_code == 200

    greeting_mock = AsyncMock(return_value={
        "session_id": session_id,
        "greeting_text": "Welcome.",
        "audio_base64": None,
    })
    monkeypatch.setattr("backend.app.main.generate_voice_greeting", greeting_mock)
    greeting_response = client.post(
        "/api/voice-therapy/greeting",
        json={"session_id": session_id, "user_id": owner},
        headers=auth_headers(owner),
    )
    assert greeting_response.status_code == 200

    summary_mock = AsyncMock(return_value={
        "session_id": session_id,
        "summary_text": "A brief supportive session.",
        "concerns": [],
        "goals": [],
        "techniques_used": [],
        "key_insights": [],
        "action_steps": [],
    })
    monkeypatch.setattr("backend.app.main.generate_session_summary", summary_mock)
    end_response = client.post(
        "/api/therapy/session/end",
        json={"session_id": session_id, "user_id": owner},
        headers=auth_headers(owner),
    )
    assert end_response.status_code == 200
    assert end_response.json()["session_id"] == session_id
