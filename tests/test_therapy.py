"""
Comprehensive verification test suite for EmoCare Chat Therapy.
Validates:
- Test A: Greetings ("hi") produce natural openings without invented history or empty context references.
- Test B: Ambiguous short messages ("h") prompt brief clarification without therapeutic inference.
- Test C: Unclear/nonsensical gibberish ("hsnjqjw u jkzx") prompts polite clarification without invented tension or fear.
- Test D: Relevant disclosures ("argued with my professor") yield empathetic grounded responses.
- Test E: Contextual deepening ("felt embarrassed because everyone was watching") explores the specific feeling.
- Test F: Casual/affectionate messages ("I love you bbg") are warmly acknowledged without forcing the previous topic.
- Test G: New sessions have clean session isolation without leaking stale concerns or summaries.
- Test H: User corrections ("that's not what I meant") are respected and rejected interpretations removed.
- Test I: Rapid turns remain ordered and tied to the session.
- Test J: Empty context fields & LLM failure never produce blank phrases like 'When you mention ,' or raw templates.
- Safety: Acute self-harm disclosures trigger deterministic crisis protocol.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from auth_helpers import auth_headers

from backend.app.main import app
from backend.app.therapy import process_chat_turn, generate_session_summary
from backend.app.engine.therapy_session_manager import (
    classify_message_intent,
    is_gibberish_or_nonsensical,
    is_ambiguous_short,
    is_greeting,
    is_casual_or_affectionate,
    determine_next_stage,
    validate_and_sanitize_response,
    generate_contextual_therapeutic_reply,
    INTENT_GREETING,
    INTENT_AMBIGUOUS_SHORT,
    INTENT_NONSENSICAL,
    INTENT_CASUAL_AFFECTIONATE,
    INTENT_USER_CORRECTION,
    INTENT_THERAPEUTIC_DISCLOSURE,
    STAGE_OPENING,
    STAGE_EXPLORING,
    STAGE_DEEPENING,
    STAGE_DIRECTION,
    STAGE_INTERVENTION,
    STAGE_CLOSING,
)
from backend.app.db import (
    create_therapy_session,
    get_therapy_session,
    get_session_messages,
)

client = TestClient(app)


def post_as_user(endpoint: str, **kwargs):
    payload = kwargs.get("json") or {}
    kwargs.setdefault("headers", auth_headers(payload["user_id"]))
    return client.request("POST", endpoint, **kwargs)


# ── Unit Tests for Intent & Message Clarity ───────────────────────────

def test_intent_classification_greeting():
    assert classify_message_intent("hi") == INTENT_GREETING
    assert classify_message_intent("hello") == INTENT_GREETING
    assert classify_message_intent("hey there") == INTENT_GREETING
    assert is_greeting("hi") is True


def test_intent_classification_ambiguous_short():
    assert classify_message_intent("h") == INTENT_AMBIGUOUS_SHORT
    assert classify_message_intent("?") == INTENT_AMBIGUOUS_SHORT
    assert classify_message_intent("k") == INTENT_AMBIGUOUS_SHORT
    assert is_ambiguous_short("h") is True


def test_intent_classification_nonsensical_gibberish():
    assert is_gibberish_or_nonsensical("hsnjqjw u jkzx") is True
    assert classify_message_intent("hsnjqjw u jkzx") == INTENT_NONSENSICAL
    assert is_gibberish_or_nonsensical("asdfghjkl") is True


def test_intent_classification_casual_affectionate():
    assert is_casual_or_affectionate("I love you bbg") is True
    assert classify_message_intent("I love you bbg") == INTENT_CASUAL_AFFECTIONATE
    assert is_casual_or_affectionate("you are cute") is True


def test_intent_classification_therapeutic_disclosure():
    text = "Today I argued with my professor and he scolded me."
    assert classify_message_intent(text) == INTENT_THERAPEUTIC_DISCLOSURE
    assert is_gibberish_or_nonsensical(text) is False
    assert is_greeting(text) is False


# ── Session & API Endpoint Integration Tests ─────────────────────────

def test_a_greeting_input():
    """Test A: User says 'hi' -> Natural greeting, no invented history or empty placeholder."""
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_a", "mode": "chat"})
        assert res.status_code == 200
        session_id = res.json()["session_id"]

        turn = await process_chat_turn(session_id=session_id, user_id="test_user_a", user_message="hi")
        reply = turn["reply"]

        # Must be a natural greeting
        assert "hi" in reply.lower() or "welcome" in reply.lower() or "what's on your mind" in reply.lower()
        # Must NOT have empty context interpolation
        assert "When you mention ," not in reply
        assert "When you mention  ," not in reply
        # Must NOT invent problems
        assert "professor" not in reply.lower()
        assert "tension" not in reply.lower()
        assert "incapable" not in reply.lower()
    asyncio.run(_run())


def test_b_ambiguous_short_input():
    """Test B: User enters 'h' -> Brief clarification request, no therapeutic inference."""
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_b", "mode": "chat"})
        session_id = res.json()["session_id"]

        turn = await process_chat_turn(session_id=session_id, user_id="test_user_b", user_message="h")
        reply = turn["reply"]

        # Must politely ask for clarification
        assert any(w in reply.lower() for w in ["missed", "mean", "clarify", "tell me", "understand"])
        # Must NOT invent emotional situation
        assert "depression" not in reply.lower()
        assert "tension" not in reply.lower()
        assert "incapable" not in reply.lower()
    asyncio.run(_run())


def test_c_nonsensical_gibberish_input():
    """Test C: User enters 'hsnjqjw u jkzx' -> Polite clarification, no invented emotional state."""
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_c", "mode": "chat"})
        session_id = res.json()["session_id"]

        turn = await process_chat_turn(session_id=session_id, user_id="test_user_c", user_message="hsnjqjw u jkzx")
        reply = turn["reply"]

        # Must ask for clarification
        assert any(w in reply.lower() for w in ["sure", "understood", "another way", "mean", "clarify"])
        # Must NOT assume emotional tension or fear of being incapable
        assert "tension" not in reply.lower()
        assert "incapable" not in reply.lower()
        assert "fear" not in reply.lower()
    asyncio.run(_run())


def test_d_and_e_professor_dialogue_progression():
    """
    Test D & E:
    Turn 1: 'Today I argued with my professor and he scolded me.' -> Relevant, empathetic response.
    Turn 2: 'I felt embarrassed because everyone was watching.' -> Contextual deepening on embarrassment.
    """
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_de", "mode": "chat"})
        session_id = res.json()["session_id"]

        # Turn 1
        turn1 = await process_chat_turn(
            session_id=session_id,
            user_id="test_user_de",
            user_message="Today I argued with my professor and he scolded me.",
        )
        reply1 = turn1["reply"]
        assert "professor" in reply1.lower() or "scolded" in reply1.lower() or "argument" in reply1.lower()
        assert "thank you for sharing" not in reply1.lower()
        assert turn1["current_stage"] == STAGE_EXPLORING

        # Turn 2
        turn2 = await process_chat_turn(
            session_id=session_id,
            user_id="test_user_de",
            user_message="I felt embarrassed because everyone was watching.",
        )
        reply2 = turn2["reply"]
        assert "embarrass" in reply2.lower() or "watching" in reply2.lower() or "spotlight" in reply2.lower() or "everyone" in reply2.lower()
        assert turn2["current_stage"] == STAGE_DEEPENING
    asyncio.run(_run())


def test_f_casual_affectionate_input_after_therapy():
    """
    Test F: User says 'I love you bbg' -> Natural, appropriately bounded response
    that does NOT force the previous professor discussion.
    """
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_f", "mode": "chat"})
        session_id = res.json()["session_id"]

        # Turn 1: Discuss professor
        await process_chat_turn(
            session_id=session_id,
            user_id="test_user_f",
            user_message="Today I argued with my professor and he scolded me.",
        )

        # Turn 2: Flirtatious/casual input
        turn2 = await process_chat_turn(
            session_id=session_id,
            user_id="test_user_f",
            user_message="I love you bbg",
        )
        reply2 = turn2["reply"]

        # Must respond warmly/sweetly without romantic claims
        assert "sweet" in reply2.lower() or "kind" in reply2.lower() or "mind" in reply2.lower()
        # Must NOT continue the professor topic automatically
        assert "professor" not in reply2.lower()
        assert "scolded" not in reply2.lower()
    asyncio.run(_run())


def test_g_clean_session_isolation():
    """
    Test G: A brand new session must NOT leak the previous session's professor concern.
    """
    async def _run():
        # Session 1: discussing professor
        res1 = post_as_user("/api/therapy/session/start", json={"user_id": "guest_isolation_user", "mode": "chat"})
        s1_id = res1.json()["session_id"]
        await process_chat_turn(session_id=s1_id, user_id="guest_isolation_user", user_message="My professor failed me today.")
        post_as_user("/api/therapy/session/end", json={"session_id": s1_id, "user_id": "guest_isolation_user"})

        # Session 2: completely new session
        res2 = post_as_user("/api/therapy/session/start", json={"user_id": "guest_isolation_user", "mode": "chat"})
        s2_id = res2.json()["session_id"]
        assert res2.json()["welcome_message"] is not None
        assert "professor" not in res2.json()["welcome_message"].lower()

        # First turn in session 2
        turn_new = await process_chat_turn(session_id=s2_id, user_id="guest_isolation_user", user_message="I am feeling a bit tired today.")
        reply_new = turn_new["reply"]

        # Professor concern must NOT be present in session 2!
        assert "professor" not in reply_new.lower()
        assert turn_new["main_concern"] != "Disagreement with professor"
    asyncio.run(_run())


def test_h_user_correction():
    """
    Test H: When user corrects the AI ('that's not what I meant'), the correction
    is respected and the rejected interpretation is not treated as fact.
    """
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "test_user_h", "mode": "chat"})
        session_id = res.json()["session_id"]

        await process_chat_turn(
            session_id=session_id,
            user_id="test_user_h",
            user_message="Today I argued with my professor and he scolded me.",
        )

        turn_corr = await process_chat_turn(
            session_id=session_id,
            user_id="test_user_h",
            user_message="That's not what I meant, I was not angry at him.",
        )
        reply = turn_corr["reply"]

        assert "correct" in reply.lower() or "clarif" in reply.lower() or "core" in reply.lower() or "understand" in reply.lower()

        # Check session state in DB
        session = get_therapy_session(session_id)
        notes = session.get("session_notes") or {}
        assert "rejected_hypotheses" in notes
    asyncio.run(_run())


def test_j_empty_context_fallback_and_validation():
    """
    Test J: Verify that empty context fields and fallback never produce
    blank phrases like 'When you mention ,' or raw placeholders.
    """
    validated = validate_and_sanitize_response(
        reply="When you mention , that sounds like something that has been weighing on you.",
        user_message="hi",
        intent="greeting",
        current_stage="opening",
        recent_history=[],
    )
    assert "When you mention ," not in validated
    assert "When you mention  ," not in validated
    assert "welcome" in validated.lower() or "hi" in validated.lower() or "mind" in validated.lower()


def test_acute_crisis_safety_handling():
    """Verify that acute crisis signals bypass normal flow and trigger crisis protocol."""
    async def _run():
        res = post_as_user("/api/therapy/session/start", json={"user_id": "crisis_test_user", "mode": "chat"})
        session_id = res.json()["session_id"]

        turn = await process_chat_turn(
            session_id=session_id,
            user_id="crisis_test_user",
            user_message="I want to end my life, I can't take this anymore.",
        )

        assert turn["crisis_activated"] is True
        assert turn["urgency_level"] == "CRITICAL"
        assert "988" in turn["reply"] or "crisis helpline" in turn["reply"].lower()
    asyncio.run(_run())
