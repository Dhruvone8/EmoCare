"""
EmoCare Streamlit Dashboard — Mental Health Self-Assessment

Features:
- Academic project disclaimer & consent check
- PHQ-9 (Depression) & GAD-7 (Anxiety) standard screening questionnaires
- Question-by-question response form
- Real-time score calculation, severity band, and app risk tier mapping
- Non-clinical, plain-language supportive interpretations
- FastAPI backend integration with local fallback
"""
import os
import streamlit as st
import requests

# ── Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EmoCare — Self-Assessment Check-in",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# ── Questionnaires Definition ──────────────────────────────────────────
SCALE_OPTIONS = [
    "0 - Not at all",
    "1 - Several days",
    "2 - More than half the days",
    "3 - Nearly every day",
]

PHQ9_QUESTIONS = [
    "1. Little interest or pleasure in doing things",
    "2. Feeling down, depressed, or hopeless",
    "3. Trouble falling or staying asleep, or sleeping too much",
    "4. Feeling tired or having little energy",
    "5. Poor appetite or overeating",
    "6. Feeling bad about yourself — or that you are a failure or have let yourself or your family down",
    "7. Trouble concentrating on things, such as reading the newspaper or watching television",
    "8. Moving or speaking slowly, or being fidgety and restless",
    "9. Thoughts that you would be better off dead or of hurting yourself in some way",
]

GAD7_QUESTIONS = [
    "1. Feeling nervous, anxious, or on edge",
    "2. Not being able to stop or control worrying",
    "3. Worrying too much about different things",
    "4. Trouble relaxing",
    "5. Being so restless that it is hard to sit still",
    "6. Becoming easily annoyed or irritable",
    "7. Feeling afraid, as if something awful might happen",
]


def score_locally(test_type: str, responses: list[int]):
    """Local fallback scoring if backend API is not running."""
    total = sum(responses)
    if test_type == "phq9":
        max_score = 27
        if total <= 4:
            severity, risk = "Minimal or None", "Low"
            summary = "Your responses suggest minimal or no depressive distress. You seem to be experiencing day-to-day emotional balance."
        elif total <= 9:
            severity, risk = "Mild", "Low"
            summary = "Your responses suggest mild signs of low mood or fatigue. Practicing daily self-care and mindfulness may be helpful."
        elif total <= 14:
            severity, risk = "Moderate", "Moderate"
            summary = "Your responses reflect moderate emotional distress. You may be experiencing persistent fatigue or low mood."
        elif total <= 19:
            severity, risk = "Moderately Severe", "High"
            summary = "Your responses indicate notable emotional strain. We encourage connecting with a counselor or healthcare professional."
        else:
            severity, risk = "Severe", "High"
            summary = "Your responses suggest significant distress. Reaching out to a healthcare professional or helpline can provide valuable support."
    else:
        max_score = 21
        if total <= 4:
            severity, risk = "Minimal Anxiety", "Low"
            summary = "Your responses indicate minimal anxiety. Your stress levels appear manageable."
        elif total <= 9:
            severity, risk = "Mild Anxiety", "Low"
            summary = "Your responses indicate mild anxiety. Simple breathing exercises and breaks can help keep stress in check."
        elif total <= 14:
            severity, risk = "Moderate Anxiety", "Moderate"
            summary = "Your responses reflect moderate anxiety. Worry or tension might be impacting your daily routine."
        else:
            severity, risk = "Severe Anxiety", "High"
            summary = "Your responses suggest heightened anxiety levels. We recommend consulting a healthcare or counseling provider."

    return {
        "total_score": total,
        "max_score": max_score,
        "severity_band": severity,
        "risk_tier": risk,
        "plain_language_summary": summary,
    }


# ── Header & Disclaimer ────────────────────────────────────────────────
st.title("🌱 EmoCare Check-in")
st.caption("Emotion-Aware AI Companion — Academic & Self-Reflection Platform")

# Consent & Disclaimer Notice
with st.container():
    st.info(
        "**Important Notice & Consent:**\n\n"
        "• **Screening Only:** This self-assessment is an academic screening tool, not a medical or clinical diagnosis.\n"
        "• **Tracking Trends:** Your responses and scores are logged securely to help track wellbeing trends over time.\n"
        "• **Immediate Support:** If you are experiencing severe distress or thoughts of self-harm, please reach out "
        "to a medical professional or local helpline (e.g., call or text **988** in the US/Canada or **112/911**)."
    )

consent = st.checkbox("I understand that this is a supportive screening tool and wish to proceed.", value=True)

if not consent:
    st.warning("Please check the consent box above to proceed with the self-assessment.")
    st.stop()

# ── Sidebar Setup ──────────────────────────────────────────────────────
st.sidebar.header("Assessment Options")
user_id = st.sidebar.text_input("User / Session ID", value="user_demo_1")

test_selection = st.sidebar.selectbox(
    "Choose a Check-in Test",
    options=["PHQ-9 (Depression Screening)", "GAD-7 (Anxiety Screening)"],
)

is_phq9 = "PHQ-9" in test_selection
test_type = "phq9" if is_phq9 else "gad7"
questions = PHQ9_QUESTIONS if is_phq9 else GAD7_QUESTIONS
test_name = "PHQ-9 (Depression Screening)" if is_phq9 else "GAD-7 (Anxiety Screening)"

st.sidebar.markdown("---")
st.sidebar.markdown("**About the Scales:**")
st.sidebar.markdown(
    "- **PHQ-9:** 9 questions assessing mood, energy, and depression indicators over the past 2 weeks (0–27).\n"
    "- **GAD-7:** 7 questions assessing anxiety, worry, and tension over the past 2 weeks (0–21)."
)

# ── Main Questionnaire Form ────────────────────────────────────────────
st.subheader(f"📋 {test_name}")
st.write("Over the **last 2 weeks**, how often have you been bothered by any of the following problems?")

with st.form("assessment_form"):
    responses = []
    for i, q in enumerate(questions):
        choice = st.radio(
            q,
            options=SCALE_OPTIONS,
            index=0,
            key=f"q_{test_type}_{i}",
        )
        score_val = int(choice.split(" - ")[0])
        responses.append(score_val)
        st.write("")  # Spacing

    submitted = st.form_submit_button("Submit Assessment", use_container_width=True)

# ── Results Handling ───────────────────────────────────────────────────
if submitted:
    st.markdown("---")
    st.subheader("📊 Your Assessment Results")

    # Call FastAPI backend
    api_url = f"{API_BASE_URL}/api/assessment/submit"
    payload = {
        "user_id": user_id,
        "test_type": test_type,
        "responses": responses,
    }

    result_data = None
    try:
        res = requests.post(api_url, json=payload, timeout=5)
        if res.status_code == 200:
            result_data = res.json()
        else:
            st.warning(f"Backend API returned status {res.status_code}. Using local calculation.")
    except Exception as e:
        st.info("Backend API unreachable. Evaluated locally.")

    if result_data is None:
        result_data = score_locally(test_type, responses)

    total_score = result_data["total_score"]
    max_score = result_data["max_score"]
    severity = result_data["severity_band"]
    risk_tier = result_data["risk_tier"]
    summary = result_data["plain_language_summary"]

    # Visual Metrics Columns
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Score", f"{total_score} / {max_score}")
    col2.metric("Severity Band", severity)

    # Risk Tier with badge color
    if risk_tier == "Low":
        col3.metric("App Risk Tier", f"🟢 {risk_tier}")
    elif risk_tier == "Moderate":
        col3.metric("App Risk Tier", f"🟡 {risk_tier}")
    else:
        col3.metric("App Risk Tier", f"🔴 {risk_tier}")

    # Plain-language explanation
    st.markdown("### 💬 Understanding Your Results")
    st.success(summary) if risk_tier == "Low" else (st.warning(summary) if risk_tier == "Moderate" else st.error(summary))

    # Next Steps & Self-Care Tips
    st.markdown("#### 🌿 Suggested Next Steps")
    if risk_tier == "Low":
        st.markdown(
            "- Continue checking in periodically to reflect on your mood patterns.\n"
            "- Maintain consistent sleep schedules and balanced daily routines."
        )
    elif risk_tier == "Moderate":
        st.markdown(
            "- Try guided mindfulness or progressive muscle relaxation exercises.\n"
            "- Share how you're feeling with a trusted friend, family member, or counselor."
        )
    else:
        st.markdown(
            "- Consider scheduling a conversation with a mental health professional for structured guidance.\n"
            "- If you feel overwhelmed, remember that help is always available through confidential hotlines."
        )

    st.caption("Results have been securely logged to assist in tracking your personal wellness journey.")
