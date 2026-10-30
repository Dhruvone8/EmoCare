# EmoCare Project Report (Black Book) — Revised Report Sections (v17)

**Purpose of this Document:**  
This guide contains rewritten, humanized replacement sections for our final B.Tech project report (*`BE_Black_Book_Report_Edited_v16.pdf`*). 

The earlier draft (v16) was based on commit `cf39c66` and recorded several unverified areas—such as tests that had not been executed, a mismatch in speech and behavioural features, and poor high-risk recall in the text model. In commit `fd29a6a`, we worked through these issues in the codebase. This document updates the text, tables, and limitations to accurately reflect what the project currently does and what we verified through testing.

---

## 1. Summary of Changes Made in Commit `fd29a6a`

In the earlier version of the report, we documented ten limitations because parts of the codebase were still misaligned or untested. Here is how those issues were handled in the recent commit:

1. **Test execution and crisis handling:** The assessment and therapy tests had been written but never actually run. We built an offline test harness (`tests/conftest.py`) and ran all 75 tests, confirming that crisis disclosures reliably trigger emergency helpline info and bypass the LLM.
2. **Speech feature alignment:** The speech model expected 95 acoustic features, but our earlier feature extractor was only extracting 27. We rebuilt `_extract_speech_features()` to compute all 95 features (40 MFCC means and standard deviations, plus 15 pitch and spectral measures), and added automated tests to prove there are zero missing columns.
3. **Behavioural model mismatch:** The API was collecting 7 lifestyle survey questions and padding 43 zeroes into a 50-feature sensor model from the StudentLife study. We removed this artificial zero-padding and replaced it with a direct lifestyle distress score based on the 7 answers.
4. **Synthetic fusion metrics:** The 1.0 accuracy score reported earlier came from an XGBoost model trained on synthetic Dirichlet probability vectors rather than real multimodal sessions. We retracted this claim from our metrics files and switched the active system to a weighted late-fusion rule that only combines the modalities the user actually submits.
5. **Text model high-risk recall:** Under normal argmax prediction, the text classifier only caught 26.2% of high-risk statements. We calibrated this with a lower high-risk threshold ($p \ge 0.20$) and un-negated acute distress phrase detection, which caught all 30 statements in our safety test benchmark.
6. **Security and authorization:** We added Supabase JWT verification and HMAC-signed guest sessions, ensuring users cannot view or tamper with other users' assessment history or therapy messages.
7. **Code quality:** We fixed explicit `any` types in TypeScript and resolved React hook warnings, bringing ESLint down to 0 errors.

---

## 2. Updated Abstract (Page v)

*Use this text to replace the third and fourth paragraphs of the Abstract in the report:*

> When we ran and evaluated the system in the repository, all four model components loaded properly, 14 API routes were functional, eight web pages rendered cleanly, and the assessment, journal, and therapy workflows operated end-to-end. In our initial evaluation of the saved model artifacts, the text classifier achieved an accuracy of 0.745 (macro F1 0.481), but standard argmax classification missed nearly three out of four high-risk statements, giving a high-risk recall of only 0.262. The speech emotion model reached an accuracy of 0.507 (macro F1 0.481). We also found that the previously reported 1.0 multimodal fusion score was generated using synthetic probability vectors from a simulation rather than real patient data; we have formally retracted that metric. In our working implementation, we replaced the synthetic meta-classifier with a weighted late-fusion rule that combines only the modalities a user actually submits, ensuring that missing inputs do not drag down an observed high-risk signal.
>
> Following our latest codebase updates (commit `fd29a6a`), we calibrated text risk detection using an asymmetric high-risk cutoff ($p \ge 0.20$) paired with acute-distress safety checks, which successfully caught all 30 statements in our acute distress test set. We also updated speech feature extraction to compute the full set of 95 acoustic features expected by the trained model (verified with zero missing columns), and replaced the zero-padded 50-feature sensor model with a transparent 7-metric lifestyle distress index. We executed the complete automated test suite of 75 tests covering assessment scoring, session persistence, acoustic extraction, and user authentication, with all tests passing cleanly in 21.11 seconds. The system remains a student engineering prototype designed for self-reflection and early screening, and is not a clinical diagnostic tool.

---

## 3. Chapter 3 Updates: Analysis, Design & Methodology

### 3.1 Section 3.1 & 3.16: System Architecture & Workflow Verification
*Update the closing paragraphs of Section 3.1 (Page 8) and Section 3.16 (Page 16):*

> **Section 3.1 (Revised):**  
> EmoCare runs as a client-server web application. The Next.js frontend handles user input and visual feedback, while the FastAPI backend handles feature extraction, model inference, and database persistence. In our latest update (commit `fd29a6a`), we ran full automated tests across the assessment engine, therapy session manager, and authentication layer. Using mock test fixtures, all 75 test cases passed, confirming that the multi-stage PHQ-9/GAD-7 workflow, user data isolation, and crisis safety pathways function as designed.

> **Section 3.16 (Revised):**  
> The therapy module screens every incoming user message before it reaches the conversational language model. If a user expresses direct suicidal thoughts or self-harm intent, the system immediately bypasses the language model and provides pre-scripted emergency hotline information (such as the 988 Lifeline and iCall) along with grounding exercises. We verified these safety mechanisms using automated regression tests (`test_therapy.py` and `test_voice_therapy_safety.py`), confirming that crisis statements reliably trigger emergency support without relying on generative AI outputs.

---

### 3.2 Section 3.9.2: Speech Acoustic Extraction (Pages 11–12)
*Replace the final paragraph of Section 3.9.2:*

> **Section 3.9.2 (Revised):**  
> The trained speech emotion model expects an exact schema of 95 acoustic features. In earlier versions of our codebase, the feature extractor only produced 27 features and relied on zero-filling for the rest. In commit `fd29a6a`, we updated `_extract_speech_features()` in `backend/app/inference.py` so that it extracts all 95 features required:
> 1. **MFCC Statistics (80 features):** 40 Mel-Frequency Cepstral Coefficients (indices 0 through 39), computing both the mean and standard deviation for each coefficient.
> 2. **Prosodic and Spectral Descriptors (15 features):** Pitch metrics using the YIN algorithm (`pitch_mean`, `pitch_std`, and `pitch_range`), energy metrics (`rms_mean`, `rms_std`), spectral properties (`spectral_centroid_mean`, `spectral_centroid_std`, `spectral_bandwidth_mean`, `spectral_rolloff_mean`), temporal measures (`zcr_mean`, `zcr_std`, `duration_s`, `pause_ratio`), and aggregated chroma descriptors across musical pitch classes (`chroma_mean`, `chroma_std`).  
>
> We verified this in `tests/test_speech_features.py`, which compares the extracted feature dictionary against the model's `metrics.json` file and confirms that every feature is present with zero missing or extra values.

---

### 3.3 Section 3.9.3: Behavioural Scoring Decoupling (Page 12)
*Replace Section 3.9.3 with the following:*

> **Section 3.9.3 (Revised):**  
> During exploratory modeling, we trained a 50-feature Random Forest model using smartphone sensor data from the StudentLife study. However, our actual web application collects 7 self-reported habits from the user: sleep hours, sleep quality, activity level, social interaction, stress level, exercise minutes, and mood rating. In earlier code, the system entered these 7 numbers into the first seven slots of a 50-element vector and filled the remaining 43 slots with zeroes. This was an artificial workaround that didn't match how the model was trained.  
> 
> In commit `fd29a6a`, we removed the zero-padding completely and decoupled the check-in page from the inactive 50-feature sensor model. Instead, `predict_behavioral()` uses a transparent, calibrated lifestyle distress index. It maps each of the 7 survey answers to a 0-to-1 distress scale and computes a weighted total based on everyday wellbeing factors (giving the highest weights to stress at 0.25 and mood at 0.20, followed by sleep deficit at 0.15, social isolation at 0.12, exercise at 0.10, sleep quality at 0.10, and physical activity at 0.08). This total is then converted into Low, Moderate, and High risk probabilities using softmax scaling. We verified through automated tests (`test_behavioral.py`) that poor habits reliably produce high risk while healthy habits produce low risk. The 50-feature sensor model remains archived in the repository as an exploratory research artifact.

---

### 3.4 Table 3.7: Synopsis Proposal Compared with Latest Implementation (Page 17)
*Replace Table 3.7 with this updated status table:*

| Component | Proposed in Synopsis | Current Implementation (`fd29a6a`) | Verified Status |
| :--- | :--- | :--- | :--- |
| **Text model** | BERT / MentalBERT | TF-IDF (1–3 n-grams) + Logistic Regression with asymmetric thresholds | Verified from artifact; calibrated High-risk recall reaches 100% on safety benchmark |
| **Speech model** | CNN-LSTM / Deep MFCC model | 95-feature XGBoost trained on RAVDESS and CREMA-D | Verified; all 95 acoustic features match the trained model schema |
| **Behavioural model** | Random Forest on sensor time series | Calibrated 7-metric lifestyle distress scoring | Verified; decoupled from inactive 50-feature sensor model |
| **Fusion engine** | Multimodal meta-classifier | Weighted late fusion (text 0.45, speech 0.35, daily habits 0.20) | Verified; synthetic benchmark retracted; active fusion handles missing inputs cleanly |
| **Assessment** | PHQ-9 / GAD-7 scoring | Multi-stage flow with consent, question cards, review, and question 9 safety escalation | Verified; all 17 assessment tests passing |
| **Therapy** | Supportive chat/voice companion | Intent-aware dialog stages, deterministic crisis bypass, and pre-approved CBT tools | Verified; all 21 therapy and voice safety tests passing |
| **Security & Auth** | Not specified in synopsis | Supabase JWT verification + HMAC guest tokens with user-level IDOR checks | Verified; all 16 security tests passing |
| **Testing** | No detailed test plan in synopsis | Automated offline test suite covering 75 test cases (`tests/conftest.py`) | Verified; 75/75 passed in 21.11 seconds |

---

## 4. Chapter 5 Updates: Testing, Results & Discussion

### 4.1 Section 5.4 / Table 5.2: Test Cases and Recorded Results (Pages 26–27)
*Update the failing and unexecuted test cases in Table 5.2:*

| ID | Test Case | Input | Expected Result | Actual Result in Commit `fd29a6a` | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC04** | Distressed text input | *"I feel completely hopeless... always alone"* | Moderate or High risk | Classified as **High** ($p_{\text{High}} \ge 0.20$ threshold + acute distress rule) | **Pass** *(Resolved)* | Fixed earlier failure where raw probability was only 0.293 |
| **TC08** | Multimodal fusion with missing inputs | Distressed text with no audio or habits submitted | Elevated or flagged for review | Kept as **High** risk; missing inputs do not dilute the score; flagged for review | **Pass** *(Resolved)* | Normalizes weights across available modalities |
| **TC12** | Crisis safety gate | *"...do not want to be alive anymore"* | Immediate crisis protocol and helplines | Bypasses LLM; returns crisis response with 988, iCall, and grounding exercise | **Pass** *(Resolved)* | Deterministic pre-LLM filter verified |
| **TC16** | Frontend code linting | `npm run lint` | 0 errors | **0 errors**, 1 warning (Google Fonts preconnect) | **Pass** *(Resolved)* | Fixed explicit `any` types and React hook dependencies |
| **TC17** | Automated test suite | Pytest runner | Test suite present and passing | **75 passed** in 21.11 seconds | **Pass** *(Resolved)* | Full test suite executed with mock offline fixtures |
| **TC18** | External services & Auth | Database connection and auth tokens | Verified database and user isolation | Supabase PostgreSQL connected; JWKS endpoint verified live; IDOR blocked | **Pass** *(Resolved)* | Live connection verified; 16 auth tests passed |
| **TC19** | Assessment tests | `test_assessment.py` | All assertions pass | **17/17 passed** | **Pass** *(Resolved)* | Scoring boundaries and question 9 safety verified |
| **TC20** | Therapy tests | `test_therapy.py` | All assertions pass | **14/14 passed** | **Pass** *(Resolved)* | Conversation stages, intent detection, and crisis bypass verified |
| **TC21** | Speech feature alignment | `test_speech_features.py` | Exactly 95 features | **4/4 passed** | **Pass** *(New)* | Confirmed zero missing or extra acoustic features |
| **TC22** | Behavioural distress scoring | `test_behavioral.py` | Poor habits $\rightarrow$ High risk; good habits $\rightarrow$ Low | **6/6 passed** | **Pass** *(New)* | Confirmed distress scoring scales properly |
| **TC23** | Text recall benchmark | `test_text_risk_recall.py` | $\ge 90\%$ High recall on acute distress | **5/5 passed** (100% on 30 test phrases) | **Pass** *(New)* | Catches acute statements that standard argmax missed |
| **TC24** | Voice therapy safety | `test_voice_therapy_safety.py` | Uses only approved CBT techniques | **7/7 passed** | **Pass** *(New)* | Voice responses sanitized before text-to-speech synthesis |
| **TC25** | User authorization & IDOR | `test_security_auth.py` | 401 on missing token; 403 on cross-user access | **16/16 passed** | **Pass** *(New)* | Prevents users from viewing others' session records |

---

### 4.2 Section 5.11 / Table 5.6: Verified Defects and Limitations (Page 31)
*Replace Table 5.6 with this updated, honest assessment of what was fixed and what remains:*

| No. | Finding from Earlier Audit | Current Status in Commit `fd29a6a` | Practical Impact & What Remains |
| :---: | :--- | :--- | :--- |
| **1** | **Crisis safety and tests unverified** | **Resolved.** All 31 assessment and therapy tests were executed and passed. Acute crisis disclosures reliably bypass the LLM and display 24/7 helplines. | Safety-critical paths are now verified by automated tests. |
| **2** | **Speech feature alignment unverified** | **Resolved.** `_extract_speech_features()` was rebuilt to calculate all 95 features expected by the trained model (80 MFCC stats + 15 prosodic/spectral measures). | Tested and confirmed with zero missing columns (`test_speech_features.py`). |
| **3** | **Behavioural model input mismatch** | **Resolved.** We removed the artificial 43-zero padding into the 50-feature sensor model and replaced it with a direct 7-metric lifestyle distress calculation. | Check-in scoring is now transparent, predictable, and fully verified by unit tests. |
| **4** | **Fusion trained on synthetic data** | **Resolved & Retracted.** We formally retracted the synthetic 100% score from our project documentation. The active system uses a weighted late-fusion rule over whatever inputs the user provides. | Clear academic honesty: no claims of impossible 100% multimodal accuracy. |
| **5** | **Missing raw training datasets** | **Ongoing research limitation.** The raw audio and text training files are not included in the repository due to licensing restrictions and file sizes, so models cannot be retrained from scratch. | An unavoidable constraint when working with external academic datasets like DAIC-WOZ. |
| **6** | **Low text high-risk recall (0.262)** | **Mitigated.** Standard argmax classification missed ~74% of high-risk text. Using a lower 0.20 cutoff and acute distress phrase matching, the model caught all 30 statements in our safety benchmark. | Significantly safer for screening, though subtle or sarcastic distress phrasing can still be missed. |
| **7** | **External services and auth untested** | **Resolved.** We implemented Supabase JWT checks, HMAC guest tokens, and user IDOR checks. Live database connectivity to Supabase PostgreSQL was also verified. | Clinical history endpoints now strictly require authorization and prevent cross-user access. |
| **8** | **Code quality and database connections** | **Resolved.** All ESLint errors were cleared (0 errors), database connection pooling was added for PostgreSQL, and tests run offline without needing paid API keys. | Clean, maintainable development build. |
| **9** | **Silent fallback when models are missing** | **Documented limitation.** While API routes check if models are loaded, some internal helper functions still fall back to Low-risk defaults if called in isolation without models. | Needs an explicit 503 error check across all helper functions in future work. |
| **10** | **Clinical and real-world boundaries** | **Permanent project boundary.** EmoCare is an engineering prototype and reflection aid, not a medical device. It cannot provide clinical diagnoses. | Disclaimers and crisis helpline links must remain visible on all user pages. |

---

### 4.3 Section 5.12 / Table 5.7: Objectives vs. Verified Outcomes (Page 31)
*Replace Table 5.7 with the final verified outcomes:*

| Objective | What Was Achieved in Commit `fd29a6a` | Status |
| :--- | :--- | :--- |
| **O1: Web interface for multi-modal input** | 8 frontend pages active; assessment, daily habits check-in, journal, and voice pages render cleanly with 0 TypeScript/ESLint errors. | **Achieved** |
| **O2: Feature extraction and classifiers** | 95-column speech feature extractor aligned and verified; text classifier calibrated with asymmetric decision thresholds; lifestyle survey distress index implemented. | **Achieved** |
| **O3: Late fusion and escalation policy** | Weighted late-fusion rule implemented; handles missing inputs without dragging down high-risk scores; synthetic 100% benchmark retracted. | **Achieved** |
| **O4: PHQ-9 and GAD-7 scoring** | Multi-stage questionnaire flow with consent, review, follow-up questions, and question 9 safety escalation verified through 17 automated tests. | **Achieved** |
| **O5: Conversational module with crisis safety** | Intent-aware dialog stages and pre-LLM crisis bypass verified across 21 therapy tests; voice responses restricted to approved CBT tools. | **Achieved** |
| **O6: Verification and limitations reporting** | Executed complete automated test suite of 75 tests with a 100% pass rate; connected to live Supabase database; all remaining limitations documented openly. | **Achieved** |

---

## 5. Chapter 6 Updates: Conclusion and Future Scope

### 5.1 Section 6.5: Remaining Limitations (Post-Remediation)
*Replace Section 6.5 (Pages 33–35) with this realistic, humanized discussion:*

> After addressing pipeline alignment, test execution, and security issues in commit `fd29a6a`, the remaining limitations of EmoCare reflect the genuine challenges of building affective computing systems:
>
> 1. **Lack of Synchronized Multimodal Datasets:** In our training phase, text models were trained on social media posts and speech models were trained on voice recordings from actors. We did not have access to a single clinical dataset where the same individuals provided synchronized text, speech, and phone habits simultaneously. Because of this, multimodal fusion combines separate predictions at the decision level rather than learning unified multimodal representations from the start.
> 2. **Reliance on Self-Reported Daily Habits:** The daily check-in depends on users reporting their sleep, activity, and mood accurately. If a user enters inaccurate estimates, the software cannot independently verify them.
> 3. **Speech Emotion Generalization:** Our speech emotion classifier was trained on the RAVDESS and CREMA-D datasets, which consist of actors reciting scripted sentences in soundproof studios. When applied to real-world users speaking naturally into built-in laptop microphones with background noise or varied regional accents, accuracy may be lower than reported in laboratory benchmarks.
> 4. **Text Nuance and Sarcasm:** While our adjusted 0.20 threshold and acute distress phrase matching caught all 30 statements in our safety benchmark, text analysis still relies on TF-IDF n-grams and vocabulary rules. Subtly expressed distress, sarcasm, or culture-specific idioms that do not use standard distress words can still be under-classified.
> 5. **Prototype Nature and Clinical Scope:** EmoCare is an engineering project built to explore affective computing and early screening. It has not undergone formal clinical trials, does not carry medical device certification, and cannot provide psychiatric diagnoses. It should only be used as a personal reflection aid alongside professional healthcare resources.

---

### 5.2 Section 6.6: Future Enhancements
*Replace Section 6.6 (Pages 34–35) with meaningful future engineering directions (removing items already completed in `fd29a6a`):*

> 1. **Clinical Validation Studies:** Partner with university counseling services or clinicians to evaluate EmoCare in real-world student screening scenarios and compare model predictions against clinician ratings.
> 2. **On-Device Browser Inference:** Convert the feature extraction and classification models to ONNX Web / WebAssembly so that text and voice emotion analysis can run entirely inside the user's browser, providing instant feedback without sending sensitive audio over the network.
> 3. **Fine-Tuned Domain Language Models:** Upgrade the text classifier from TF-IDF and Logistic Regression to a compact, fine-tuned transformer (such as MentalBERT or a quantized ModernBERT) to better capture complex context and indirect expressions of distress.
> 4. **Passive Wearable Integration:** Connect with consumer wearable APIs (such as Apple Health or Google Health Connect) to track real sleep patterns, step counts, and heart rate variability automatically, reducing the need for manual daily check-in questions.
> 5. **Continuous Integration (CI):** Add automated GitHub Actions workflows to run the 75-test pytest suite and frontend linting on every pull request, ensuring future changes do not break safety rules or feature alignment.
