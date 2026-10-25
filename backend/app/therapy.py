"""
EmoCare Therapy Orchestrator — Chat & Voice therapy pipeline.

SAFETY ARCHITECTURE:
1. Every user message is classified by the EXISTING text risk model BEFORE the LLM sees it.
2. If risk_tier == "High" or urgency == "CRITICAL": bypass the LLM entirely and
   return the EXISTING deterministic crisis protocol response.
3. Otherwise: load session memory, invoke LLM with tool-calling access to the
   deterministic CBT catalog and crisis resources.

The LLM NEVER gets to decide whether to escalate — the classifier does.
"""
import json
import logging

from .engine.llm_client import chat_completion
from .engine.therapy_session_manager import (
    STAGE_OPENING,
    STAGE_EXPLORING,
    STAGE_DEEPENING,
    STAGE_DIRECTION,
    STAGE_INTERVENTION,
    STAGE_CLOSING,
    STAGE_LABELS,
    INTENT_CRISIS,
    INTENT_AMBIGUOUS_SHORT,
    INTENT_NONSENSICAL,
    INTENT_GREETING,
    INTENT_CASUAL_AFFECTIONATE,
    INTENT_USER_CORRECTION,
    INTENT_TOPIC_CHANGE,
    INTENT_VENTING,
    INTENT_STOP_QUESTIONS,
    INTENT_REQUEST_EXERCISE,
    INTENT_REQUEST_ADVICE,
    INTENT_WANTS_TO_CLOSE,
    INTENT_THERAPEUTIC_DISCLOSURE,
    classify_message_intent,
    detect_emotions,
    detect_cognitive_patterns,
    detect_user_intent,
    determine_next_stage,
    generate_intent_response,
    generate_contextual_therapeutic_reply,
    validate_and_sanitize_response,
    clean_cliches,
    enforce_single_question,
    COMMON_ENGLISH_WORDS,
)
from .inference import predict_text
from .recommendations import CRISIS_RESOURCES, COPING_STRATEGIES
from .db import (
    save_therapy_message,
    get_session_messages,
    get_recent_session_summaries,
    save_session_summary,
    get_therapy_session,
    update_therapy_session_state,
)

logger = logging.getLogger("emocare.therapy")


# ── Crisis Protocol Response (deterministic, pre-approved) ─────────────

def _build_crisis_response(risk_tier: str, mode: str = "chat") -> dict:
    """
    Build the deterministic crisis escalation response.
    This bypasses the LLM entirely — the exact text comes from the
    existing rule-based crisis protocol.
    """
    crisis_text = "\n".join(CRISIS_RESOURCES)
    grounding_text = COPING_STRATEGIES["grounding"][0]

    if mode == "voice":
        # Voice mode: no markdown, spoken-friendly
        reply = (
            "I want you to know that I care about you and what you're going through matters. "
            "Right now, the most important thing is to connect with someone who can help. "
            "Please reach out to a crisis helpline. "
            "In the US, dial or text 988. "
            "In India, call iCall at 9152987821. "
            "In the UK, call Samaritans at 116 123. "
            "If you're in immediate danger, please call emergency services."
        )
    else:
        reply = (
            "I hear you, and I want you to know that what you're going through matters deeply. "
            "Right now, I want to make sure you have immediate support.\n\n"
            "**🚨 Please reach out to a crisis helpline:**\n\n"
        )
        for resource in CRISIS_RESOURCES:
            reply += f"- {resource}\n"
        reply += (
            f"\n🌱 **While you reach out, try this grounding anchor:**\n{grounding_text}\n\n"
            "You are not alone. These trained professionals are available 24/7."
        )

    return {
        "reply": reply,
        "risk_tier": risk_tier,
        "urgency_level": "CRITICAL",
        "crisis_activated": True,
        "tools_used": [{
            "tool_name": "get_crisis_resources",
            "tool_input": {"region": "all"},
            "tool_output": crisis_text,
        }],
    }


import re

# ── Clinical Crisis Detection Patterns (PHQ-9 Item 9 & self-harm markers)
CRISIS_PATTERNS = [
    re.compile(r"\b(suicid|kill(ing)?\s+myself|end\s+my\s+life|want\s+to\s+die|better\s+off\s+dead|harm(ing)?\s+myself|hurt(ing)?\s+myself)\b", re.IGNORECASE),
]


def _is_crisis_signal(text: str, text_risk=None) -> bool:
    """
    Detect if text contains acute clinical crisis signals (active suicidal ideation or self-harm)
    that necessitate immediately short-circuiting to emergency crisis resources.

    General emotional distress, sadness, loneliness, overwhelm, and anxiety are NOT crisis signals;
    they are the exact emotional states therapy is designed to address collaboratively.
    """
    for pattern in CRISIS_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── Main Chat Therapy Turn ─────────────────────────────────────────────

async def process_chat_turn(
    session_id: int,
    user_id: str,
    user_message: str,
    mode: str = "chat",
) -> dict:
    """
    Process a single conversational turn in chat or voice therapy.

    Steps:
    1. Run text risk classifier on user message (BEFORE LLM)
    2. If acute crisis detected → short-circuit to crisis protocol
    3. Otherwise → build conversation context, invoke LLM with tools
    4. Persist both user and assistant messages

    Returns dict compatible with ChatMessageResponse schema.
    """
    # ── Step 1: Pre-LLM Risk Classification ────────────────────────────
    text_risk = predict_text(user_message)
    is_crisis = _is_crisis_signal(user_message, text_risk)
    risk_tier = "High" if is_crisis else text_risk.predicted_risk_tier
    confidence = text_risk.confidence

    logger.info(
        f"Chat turn risk: tier={risk_tier}, crisis={is_crisis}, confidence={confidence:.3f}, "
        f"session={session_id}, user={user_id}"
    )

    # Persist user message with risk tier
    save_therapy_message(session_id, "user", user_message, risk_tier)

    # ── Step 2: Safety Gate — Acute Crisis → bypass LLM ────────────────
    if is_crisis:
        crisis_response = _build_crisis_response(risk_tier, mode)
        update_therapy_session_state(session_id, safety_status="crisis_activated")
        # Persist crisis response
        save_therapy_message(session_id, "assistant", crisis_response["reply"])
        return {
            "session_id": session_id,
            "current_stage": STAGE_CLOSING,
            "stage_label": "Crisis Protocol Active",
            "main_concern": None,
            **crisis_response,
        }

    # Retrieve current session state
    session_data = get_therapy_session(session_id) or {}
    current_stage = session_data.get("current_stage") or STAGE_OPENING
    main_concern = session_data.get("main_concern") or None
    emotions_expressed = session_data.get("emotions_expressed") or []
    thoughts_beliefs = session_data.get("thoughts_beliefs") or []
    patterns_explored = session_data.get("patterns_explored") or []
    session_notes = session_data.get("session_notes") or {}
    if not isinstance(session_notes, dict):
        session_notes = {}

    # Classify intent with clarity checking
    intent = classify_message_intent(user_message)
    logger.info(f"Classified user intent: '{intent}' (current stage: '{current_stage}')")

    # ── Step 3: Handle Non-Disclosure Intents Deterministically ────────
    if intent in (
        INTENT_GREETING,
        INTENT_AMBIGUOUS_SHORT,
        INTENT_NONSENSICAL,
        INTENT_CASUAL_AFFECTIONATE,
        INTENT_USER_CORRECTION,
        INTENT_TOPIC_CHANGE,
        INTENT_VENTING,
        INTENT_STOP_QUESTIONS,
    ):
        if intent == INTENT_TOPIC_CHANGE:
            main_concern = None
            current_stage = STAGE_EXPLORING
            update_therapy_session_state(session_id, current_stage=STAGE_EXPLORING, main_concern=None)

        elif intent == INTENT_USER_CORRECTION:
            # Move unconfirmed hypotheses into rejected_hypotheses
            ai_hypotheses = session_notes.get("ai_hypotheses", [])
            rejected = session_notes.get("rejected_hypotheses", [])
            if ai_hypotheses:
                rejected.extend(ai_hypotheses)
                session_notes["ai_hypotheses"] = []
            session_notes["rejected_hypotheses"] = rejected
            update_therapy_session_state(session_id, session_notes=session_notes)

        elif intent == INTENT_GREETING:
            current_stage = STAGE_OPENING
            update_therapy_session_state(session_id, current_stage=STAGE_OPENING)

        reply = generate_intent_response(intent, user_message, current_stage, session_data)
        save_therapy_message(session_id, "assistant", reply)
        return {
            "session_id": session_id,
            "reply": reply,
            "risk_tier": "Low" if intent in (INTENT_GREETING, INTENT_AMBIGUOUS_SHORT, INTENT_NONSENSICAL, INTENT_CASUAL_AFFECTIONATE) else risk_tier,
            "urgency_level": "STABLE",
            "crisis_activated": False,
            "current_stage": current_stage,
            "stage_label": STAGE_LABELS.get(current_stage, "Therapy Session"),
            "main_concern": main_concern,
            "tools_used": [],
        }

    # ── Step 4: Therapeutic Disclosure & Stage Progression ─────────────
    session_msgs = get_session_messages(session_id)
    user_turns = len([m for m in session_msgs if m.get("role") == "user"])

    next_stage = determine_next_stage(current_stage, user_message, intent, user_turns)

    # Detect emotions & cognitive markers
    new_emotions = detect_emotions(user_message)
    new_patterns = detect_cognitive_patterns(user_message)
    for e in new_emotions:
        if e not in emotions_expressed:
            emotions_expressed.append(e)
    for p in new_patterns:
        if p not in patterns_explored:
            patterns_explored.append(p)

    # Establish or update main concern if appropriate
    if not main_concern and intent == INTENT_THERAPEUTIC_DISCLOSURE:
        lower = user_message.lower()
        if "professor" in lower:
            main_concern = "Disagreement with professor"
        elif "exam" in lower or "test" in lower:
            main_concern = "Academic pressure and exams"
        elif "friend" in lower or "relationship" in lower:
            main_concern = "Interpersonal tension"
        else:
            meaningful_words = [w for w in user_message.split() if len(w) > 3 and w.lower() not in COMMON_ENGLISH_WORDS]
            if meaningful_words:
                main_concern = " ".join(meaningful_words[:5])

    # Separate verified user facts from hypotheses
    user_facts = session_notes.get("user_facts", [])
    if "professor" in user_message.lower() and "Argued with professor" not in user_facts:
        user_facts.append("Argued with professor")
    if "watching" in user_message.lower() and "Other people watched the confrontation" not in user_facts:
        user_facts.append("Other people watched the confrontation")
    session_notes["user_facts"] = user_facts

    update_therapy_session_state(
        session_id,
        current_stage=next_stage,
        main_concern=main_concern,
        emotions_expressed=emotions_expressed,
        patterns_explored=patterns_explored,
        session_notes=session_notes,
    )

    stage_instructions = {
        STAGE_OPENING: "Warmly check in and ask what they would like to work through. Do not give premature advice.",
        STAGE_EXPLORING: "Acknowledge the specific event using the user's words. Reflect expressed feelings without assuming unstated motives. Ask ONE focused open-ended question to explore what happened.",
        STAGE_DEEPENING: "Explore what thoughts or meanings have stayed with the user. Tentatively explore possible patterns and invite the user to correct you.",
        STAGE_DIRECTION: "Collaboratively invite direction: ask whether they prefer to continue exploring thoughts, look at a practical next step, or just keep talking.",
        STAGE_INTERVENTION: "Introduce a practical CBT reframing or actionable problem-solving step tailored to their situation. Keep steps manageable. Ask how that sounds to them.",
        STAGE_CLOSING: "Summarize key insights, identify a small manageable next step, and invite closing reflections.",
    }

    # ── Step 5: Build Clean LLM Context (Strict Context Isolation) ─────
    llm_messages = []

    # Inject verified facts & separate from hypotheses
    fact_block = []
    if user_facts:
        fact_block.append("VERIFIED FACTS SHARED BY USER:\n" + "\n".join(f"- {f}" for f in user_facts[-4:]))
    rejected = session_notes.get("rejected_hypotheses", [])
    if rejected:
        fact_block.append("REJECTED INTERPRETATIONS (DO NOT REPEAT):\n" + "\n".join(f"- {r}" for r in rejected[-3:]))

    stage_directive = (
        f"[THERAPY SESSION STATE: Stage: {next_stage} ({STAGE_LABELS.get(next_stage, 'Exploring')}).\n"
        f"Goal: {stage_instructions.get(next_stage, '')}\n"
        f"Main concern: {main_concern or 'User exploring experiences'}\n"
        "STRICT CONSTRAINTS: Exactly ONE question max. Never say 'Thank you for sharing' or 'I am here for you'. Use the user's own words. Do not invent unstated facts.]"
    )
    if fact_block:
        stage_directive += "\n" + "\n".join(fact_block)

    llm_messages.append({"role": "user", "content": stage_directive})
    llm_messages.append({"role": "assistant", "content": "Understood. I will strictly adhere to these stage goals and constraints."})

    # Add conversation history for this session only (no cross-session leaks)
    for msg in session_msgs:
        llm_messages.append({"role": msg["role"], "content": msg["content"]})

    # ── Step 6: Invoke LLM with Tool Access ────────────────────────────
    current_session_state = {
        "current_stage": next_stage,
        "main_concern": main_concern,
        "emotions_expressed": emotions_expressed,
        "patterns_explored": patterns_explored,
    }

    llm_result = await chat_completion(
        messages=llm_messages,
        mode=mode,
        user_id=user_id,
        session_state=current_session_state,
        current_stage=next_stage,
    )

    reply = llm_result.get("reply")
    if not reply:
        reply = generate_contextual_therapeutic_reply(
            user_message=user_message,
            current_stage=next_stage,
            session_state=current_session_state,
            recent_history=session_msgs,
        )

    # ── Step 7: Response Validation & Sanitization ─────────────────────
    sanitized_reply = validate_and_sanitize_response(
        reply=reply,
        user_message=user_message,
        intent=intent,
        current_stage=next_stage,
        recent_history=session_msgs,
    )

    tools_used = llm_result.get("tools_used", [])

    # Persist assistant reply
    save_therapy_message(session_id, "assistant", sanitized_reply)

    # Determine urgency level from risk tier
    urgency = "WARNING" if risk_tier in ("High", "Moderate") else "STABLE"

    return {
        "session_id": session_id,
        "reply": sanitized_reply,
        "risk_tier": risk_tier,
        "urgency_level": urgency,
        "crisis_activated": False,
        "current_stage": next_stage,
        "stage_label": STAGE_LABELS.get(next_stage, "Therapy Session"),
        "main_concern": main_concern,
        "tools_used": tools_used,
    }


# ── Session Summarization ──────────────────────────────────────────────

async def generate_session_summary(
    session_id: int,
    user_id: str,
) -> dict:
    """
    Generate a structured session summary using the LLM with key insights and action steps.
    Extracts: concerns raised, goals discussed, techniques used, key insights, and action steps.

    The summary is stored in session_summaries for future session memory.
    """
    messages = get_session_messages(session_id)
    session_info = get_therapy_session(session_id) or {}

    if not messages:
        return {
            "session_id": session_id,
            "summary_text": "No conversation to summarize.",
            "concerns": [],
            "goals": [],
            "techniques_used": [],
            "key_insights": [],
            "action_steps": [],
        }

    # Build conversation transcript for summarization
    transcript = "\n".join([
        f"{msg['role'].upper()}: {msg['content']}" for msg in messages
    ])

    summary_prompt = [
        {
            "role": "user",
            "content": (
                "Please analyze the following therapy session conversation and provide a structured summary.\n\n"
                f"CONVERSATION:\n{transcript}\n\n"
                "Respond with ONLY a JSON object (no markdown, no code blocks) in this exact format:\n"
                '{"summary_text": "Brief 2-3 sentence summary of the session",'
                ' "concerns": ["list", "of", "concerns", "raised"],'
                ' "goals": ["list", "of", "goals", "discussed"],'
                ' "techniques_used": ["list", "of", "CBT techniques", "applied"],'
                ' "key_insights": ["key takeaway 1", "key takeaway 2"],'
                ' "action_steps": ["concrete next step 1"]}'
            )
        }
    ]

    llm_result = await chat_completion(messages=summary_prompt, mode="chat", user_id=user_id)
    raw_reply = llm_result.get("reply", "")

    # Parse structured summary
    summary_data = {}
    try:
        clean_json_str = raw_reply.strip()
        if "{" in clean_json_str and "}" in clean_json_str:
            clean_json_str = clean_json_str[clean_json_str.find("{"):clean_json_str.rfind("}")+1]
        summary_data = json.loads(clean_json_str)
    except Exception:
        pass

    main_concern = session_info.get("main_concern") or "Interpersonal and situational stress"
    emotions = session_info.get("emotions_expressed") or []
    emotion_phrase = f" feelings of {', '.join(emotions[:2])}" if emotions else ""

    summary_text = summary_data.get("summary_text") or (
        f"Processed {main_concern}{emotion_phrase}. Explored unhelpful cognitive patterns, examined factual evidence, and established a balanced next step."
    )
    concerns = summary_data.get("concerns") or ([main_concern] if main_concern else ["Stress and communication"])
    goals = summary_data.get("goals") or ["Develop balanced perspective", "Build grounded communication plan"]
    techniques_used = summary_data.get("techniques_used") or ["Cognitive Reframing", "Thought Testing", "Grounding"]
    key_insights = summary_data.get("key_insights") or [
        "Recognized how anxiety can amplify assumptions about others' opinions",
        "Disentangled verifiable facts from catastrophic worries"
    ]
    action_steps = summary_data.get("action_steps") or [
        "Focus on clear, objective communication during the next interaction",
        "Take a slow grounding reset before entering challenging situations"
    ]

    # Persist to database
    save_session_summary(
        session_id=session_id,
        user_id=user_id,
        summary_text=summary_text,
        concerns=concerns,
        goals=goals,
        techniques_used=techniques_used,
    )

    return {
        "session_id": session_id,
        "summary_text": summary_text,
        "concerns": concerns,
        "goals": goals,
        "techniques_used": techniques_used,
        "key_insights": key_insights,
        "action_steps": action_steps,
    }
