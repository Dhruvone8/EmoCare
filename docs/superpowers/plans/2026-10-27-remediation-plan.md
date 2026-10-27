# EmoCare Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate all P0-P3 security, pipeline, clinical safety, data integrity, and verification defects identified during the technical audit of EmoCare.

**Architecture:** The remediation plan is partitioned into three complexity sections:
- **Section 1: Low Complexity (Quick Wins, Static Fixes, Secret Sanitization, & Code Quality)**: Secrets rotation/redaction, frontend linting and typing fixes, dead code/table cleanup, urgency string comparison correction, and repository pruning.
- **Section 2: Moderate Complexity (Pipeline Corrections, Contract Alignment, & Reliability)**: Acoustic feature extraction alignment (40 MFCCs + 15 prosodics), behavioral survey schema decoupling, missing-modality fusion logic, database connection pooling, and offline test mocking.
- **Section 3: High Complexity (Security Hardening, Model Calibration, & Clinical Safety Gating)**: JWT authentication & IDOR defense on all clinical history routes, text risk recall re-calibration ($\ge 85\%$ high-risk recall), voice therapy deterministic CBT tool gating, and benchmark documentation retraction.

**Tech Stack:** FastAPI, Next.js 16, React 19, TypeScript, Python 3.10+, scikit-learn, librosa, XGBoost, Supabase (PostgreSQL + Auth), pytest.

**Spec Reference:** Audit Findings Register (`AUDIT-P0-01` through `AUDIT-P3-15`).

## Global Constraints
- Never commit plaintext passwords, database URLs with embedded credentials, or service role keys to repository files.
- All unit tests must execute 100% offline and deterministically with mocked network clients.
- Missing modalities must not dilute observed high-risk signals in multimodal fusion.
- All clinical history endpoints must enforce user-level ownership checks (`user_id == current_user.id`).
- High-risk recall for text distress statements must be prioritized over raw accuracy.

---

# SECTION 1: Low Complexity (Quick Wins, Static Fixes, & Secret Hygiene)

### Task 1.1: Secret Sanitization & Environment Variable Hygiene
**Complexity:** Low  
**Finding Addressed:** AUDIT-P0-05  
**Files:**
- Modify: `d:/EmoCare/.env`
- Modify: `d:/EmoCare/backend/.env`
- Modify: `d:/EmoCare/.env.example`
- Modify: `d:/EmoCare/frontend/src/lib/supabase.ts`
- Modify: `d:/EmoCare/.gitignore`

**Interfaces:**
- Consumes: Environment variables from OS environment or `.env` file.
- Produces: Sanitized template configs; prevents fallback hardcoding of live JWT keys or database passwords.

- [ ] **Step 1: Update `.gitignore` to block all `.env` files**
  Add `.env`, `backend/.env`, and `.env.local` to `.gitignore`.
- [ ] **Step 2: Scrub plaintext fallback secrets in `frontend/src/lib/supabase.ts`**
  Remove hardcoded fallback database URL and anon JWT string. Throw an explicit error if `NEXT_PUBLIC_SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_ANON_KEY` is undefined.
- [ ] **Step 3: Sanitize `.env` and `.env.example`**
  Replace plaintext credentials (`[REDACTED_DATABASE_PASSWORD]`, live `SUPABASE_SERVICE_ROLE_KEY`, live `GROQ_API_KEY`, live `ELEVENLABS_API_KEY`) with sanitized placeholders (`your-supabase-db-url-here`, etc.).
- [ ] **Step 4: Verify application boots with placeholder warnings instead of hard crashes**
  Run: `pytest tests/test_assessment.py -v` to ensure test fallback database continues to operate on SQLite when `DATABASE_URL` is a placeholder.

---

### Task 1.2: Frontend TypeScript & ESLint Error Remediation
**Complexity:** Low  
**Finding Addressed:** AUDIT-P2-13  
**Files:**
- Modify: `d:/EmoCare/frontend/src/types/api.ts`
- Modify: `d:/EmoCare/frontend/src/app/layout.tsx`
- Modify: `d:/EmoCare/frontend/src/app/therapy/voice/page.tsx`

**Interfaces:**
- Consumes: Next.js build pipeline & ESLint config.
- Produces: Zero ESLint errors, zero TypeScript compile errors.

- [x] **Step 1: Fix explicit `any` in `frontend/src/types/api.ts`**
  Replace `Record<string, any>` in `AssessmentSubmissionRequest` (lines 109-110) with `Record<string, unknown>`.
- [x] **Step 2: Remove unused `Script` import in `frontend/src/app/layout.tsx`**
  Remove line 2: `import Script from "next/script";`.
- [x] **Step 3: Fix `useCallback` dependency array in `frontend/src/app/therapy/voice/page.tsx`**
  Include `startAudioPipeline` in the dependency array on line 556.
- [x] **Step 4: Run ESLint and TypeScript validation**
  Run: `powershell -Command "cd frontend; npm run lint"`
  Expected: `✔ No ESLint warnings or errors`.

---

### Task 1.3: Urgency Level String Comparison Logic Correction
**Complexity:** Low  
**Finding Addressed:** AUDIT-P2-11  
**Files:**
- Modify: `d:/EmoCare/backend/app/inference.py`

**Interfaces:**
- Consumes: `urgency` string ("STABLE" | "WARNING" | "CRITICAL"), `low_confidence_flag` boolean.
- Produces: Properly ordered `urgency_level` without alphabetical string comparison bugs.

- [x] **Step 1: Write unit test exposing the string comparison defect**
  In `tests/test_inference.py`, assert that when urgency is "CRITICAL", calling the escalation check cannot downgrade it to "WARNING".
- [x] **Step 2: Replace string `max()` with priority rank lookup**
  In `backend/app/inference.py:404-420`, replace `max(urgency, "WARNING")` with:
  ```python
  URGENCY_RANKS = {"STABLE": 0, "WARNING": 1, "CRITICAL": 2}
  RANK_TO_URGENCY = {0: "STABLE", 1: "WARNING", 2: "CRITICAL"}
  if low_confidence_flag and not escalate:
      escalate = True
      urgency = RANK_TO_URGENCY[max(URGENCY_RANKS[urgency], URGENCY_RANKS["WARNING"])]
  ```
- [x] **Step 3: Run unit test to verify fix**
  Run: `pytest tests/test_inference.py -v`
  Expected: PASS.

---

### Task 1.4: Dead Code, Redundant SQL Tables, & Repository Pruning
**Complexity:** Low  
**Findings Addressed:** AUDIT-P2-12, AUDIT-P3-15  
**Files:**
- Modify: `d:/EmoCare/backend/app/db.py`
- Prune: `d:/EmoCare/src/` (remove empty skeleton directories or link them to backend)

**Interfaces:**
- Consumes: PostgreSQL / SQLite DDL.
- Produces: Cleaned single-table message schema (`therapy_messages`), pruned file tree.

- [x] **Step 1: Standardize messages table in `backend/app/db.py`**
  Remove redundant dual table creation of `messages` vs `therapy_messages`. Consolidate all CRUD onto `therapy_messages` and remove dual-write boilerplate.
- [x] **Step 2: Prune hollow skeleton directories**
  Delete empty directories in `src/data`, `src/features`, `src/models`, `src/explainability`, `src/utils` or add documentation stating active codebase resides in `backend/app/`.
- [x] **Step 3: Run test suite**
  Run: `pytest tests/test_therapy.py -v` to ensure session message persistence operates cleanly on `therapy_messages`.

---

# SECTION 2: Moderate Complexity (Pipeline Corrections, Alignment, & Reliability)

### Task 2.1: Align Acoustic Feature Extraction (40 MFCCs + Prosodics)
**Complexity:** Moderate  
**Finding Addressed:** AUDIT-P0-01  
**Files:**
- Modify: `d:/EmoCare/backend/app/inference.py:140-172, 228-235`
- Test: `d:/EmoCare/tests/test_speech_features.py` (New)

**Interfaces:**
- Consumes: Raw audio waveform `y: np.ndarray`, sample rate `sr: int`.
- Produces: `raw_features: dict[str, float]` containing all 95 features matching `models.speech_feature_columns` (`mfcc_0_mean` through `mfcc_39_std`, `pitch_mean`, `rms_mean`, `zcr_std`, etc.).

- [x] **Step 1: Write diagnostic test for feature alignment**
  Create `tests/test_speech_features.py` testing that 3 seconds of synthesized audio extracts 95 features with 0 missing columns against `models.speech_feature_columns`.
- [x] **Step 2: Update `_extract_mfcc_features` in `backend/app/inference.py`**
  - Set `n_mfcc=40` in `librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)`.
  - Loop over `i in range(40)` extracting `mfcc_{i}_mean` and `mfcc_{i}_std`.
  - Extract the required 15 acoustic metrics: `pitch_mean`, `pitch_std`, `pitch_range`, `rms_mean`, `rms_std`, `zcr_mean`, `zcr_std`, `spectral_centroid_mean`, `spectral_centroid_std`, `spectral_bandwidth_mean`, `spectral_rolloff_mean`, `chroma_mean`, `chroma_std`, `duration_s`, `pause_ratio`.
  - Remove dead extractions (`delta_mfcc`, `spectral_contrast`).
- [x] **Step 3: Run test to verify 0 missing features**
  Run: `pytest tests/test_speech_features.py -v`
  Expected: PASS (0 missing columns, feature vector length == 95).

---

### Task 2.2: Decouple Behavioral Survey from StudentLife Sensor Model
**Complexity:** Moderate  
**Finding Addressed:** AUDIT-P0-03  
**Files:**
- Modify: `d:/EmoCare/backend/app/inference.py:289-322`
- Modify: `d:/EmoCare/backend/app/schemas.py:56-70`

**Interfaces:**
- Consumes: `req: BehavioralRequest` (7 user ratings: sleep hours, quality, activity, social, stress, exercise, mood).
- Produces: `BehavioralResponse` with validated risk probabilities based on clinically grounded survey weighting.

- [x] **Step 1: Write unit test for behavioral scoring**
  In `tests/test_behavioral.py`, test extreme stress/isolation scenarios (`stress_level=5, sleep_hours=3, social_interaction=1`) vs healthy scenarios (`sleep_hours=8, stress_level=1, mood_rating=5`).
- [x] **Step 2: Remove zero-padding sensor hack in `predict_behavioral`**
  Remove lines 301-310 of `inference.py` that pad 43 zeros into the StudentLife sensor vector.
- [x] **Step 3: Implement calibrated lifestyle distress index**
  Compute standardized behavioral distress score:
  - Sleep deficit penalty: `max(0, 7.0 - sleep_hours) / 4.0`
  - Subjective stress contribution: `(stress_level - 1.0) / 4.0`
  - Mood contribution: `(5.0 - mood_rating) / 4.0`
  - Social isolation contribution: `(5.0 - social_interaction) / 4.0`
  Map aggregate score into calibrated `Low`, `Moderate`, and `High` probability distributions with smooth softmax normalization.
- [x] **Step 4: Run verification tests**
  Run: `pytest tests/test_behavioral.py -v`
  Expected: High distress inputs produce High risk tier; healthy inputs produce Low risk tier.

---

### Task 2.3: Multimodal Missing-Modality Decision Rule
**Complexity:** Moderate  
**Finding Addressed:** AUDIT-P2-11  
**Files:**
- Modify: `d:/EmoCare/backend/app/inference.py:342-446`

**Interfaces:**
- Consumes: Optional `text: str`, `audio_bytes: bytes`, `behavioral: BehavioralRequest`.
- Produces: `MultimodalResponse` combining *only available* modalities without dilution.

- [x] **Step 1: Write test for single-modality high-risk inputs**
  Verify that when only high-risk text is submitted, missing speech and behavioral inputs do not drag the fused probability down from High to Low.
- [x] **Step 2: Implement available-modality weighting**
  Instead of defaulting missing modalities to `[1/3, 1/3, 1/3]`:
  - Collect prediction vectors only from active modalities.
  - If 1 modality is present: use its probability vector directly; set `cross_modal_agreement = 1.0` but flag `single_modality = True`.
  - If 2+ modalities are present: compute weighted late fusion (e.g., text weight 0.45, speech weight 0.35, behavioral weight 0.20, normalized across available modalities).
  - Compute true pairwise agreement across available modalities.
- [x] **Step 3: Run multimodal verification test**
  Run: `pytest tests/test_multimodal.py -v`
  Expected: PASS.

---

### Task 2.4: Database Connection Pooling Implementation
**Complexity:** Moderate  
**Finding Addressed:** AUDIT-P1-10  
**Files:**
- Modify: `d:/EmoCare/backend/app/db.py`
- Modify: `d:/EmoCare/backend/app/main.py:106-122`

**Interfaces:**
- Consumes: `DATABASE_URL` config string.
- Produces: Thread-safe connection pool checkout/checkin (`get_db_connection()`), eliminating per-query TLS overhead.

- [x] **Step 1: Implement `ThreadedConnectionPool` in `backend/app/db.py`**
  ```python
  from psycopg2.pool import ThreadedConnectionPool
  _pg_pool: Optional[ThreadedConnectionPool] = None

  def init_pg_pool(minconn=1, maxconn=10):
      global _pg_pool
      if DATABASE_URL and "postgresql" in DATABASE_URL:
          try:
              _pg_pool = ThreadedConnectionPool(minconn, maxconn, DATABASE_URL, connect_timeout=3)
          except Exception as e:
              logger.warning(f"Connection pool init failed: {e}")
  ```
- [x] **Step 2: Implement context manager for connection checkout**
  Create `@contextmanager def get_db_connection():` that checks out a connection from `_pg_pool` (or falls back to SQLite) and yields it, guaranteeing `putconn()` on exit.
- [x] **Step 3: Hook pool initialization and shutdown into FastAPI lifespan**
  Initialize pool in `lifespan` in `backend/app/main.py`; close all pool connections in lifespan teardown.
- [x] **Step 4: Run database concurrency test**
  Execute 20 concurrent session queries via test script to ensure zero connection leaks.

---

### Task 2.5: Test Suite Network Mocking & Determinism
**Complexity:** Moderate  
**Finding Addressed:** AUDIT-P1-09  
**Files:**
- Create: `d:/EmoCare/tests/conftest.py`
- Modify: `d:/EmoCare/tests/test_therapy.py`

**Interfaces:**
- Consumes: `pytest` runner.
- Produces: 100% offline, deterministic unit test passes with zero live Groq/OpenAI/ElevenLabs HTTP calls.

- [x] **Step 1: Create `tests/conftest.py` with mock fixtures**
  Provide automatic mocks for `chat_completion`, `transcribe_audio`, `synthesize_speech`, and force `DATABASE_URL=""` during test runs to isolate tests to an in-memory SQLite database.
- [x] **Step 2: Update `test_d_and_e_professor_dialogue_progression` in `test_therapy.py`**
  Configure the mocked LLM reply or deterministic fallback to produce the expected therapeutic reflection keywords (`embarrass`, `watching`).
- [x] **Step 3: Run full pytest suite**
  Run: `powershell -Command "$env:PYTHONPATH='.'; .\venv\Scripts\python.exe -m pytest tests/ -v"`
  Expected: 31 passed, 0 failed, 100% offline.

---

# SECTION 3: High Complexity (Security Hardening, Model Calibration, & Clinical Safety)

### Task 3.1: End-to-End JWT Authentication & IDOR Protection on Clinical History
**Complexity:** High  
**Finding Addressed:** AUDIT-P0-04  
**Files:**
- Create: `d:/EmoCare/backend/app/auth.py`
- Modify: `d:/EmoCare/backend/app/main.py:307-346, 353-431`
- Modify: `d:/EmoCare/frontend/src/lib/api.ts:49-65, 161-270`
- Test: `d:/EmoCare/tests/test_security_auth.py` (New)

**Interfaces:**
- Consumes: HTTP request `Authorization: Bearer <supabase_jwt>` header.
- Produces: Validated `AuthenticatedUser(id=..., email=...)`; raises HTTP 401 if token missing/invalid; raises HTTP 403 if `user_id != token.user_id`.

- [ ] **Step 1: Write failing security tests in `tests/test_security_auth.py`**
  - Test 1: Calling `/api/assessment/history/user123` without auth token returns 401.
  - Test 2: Calling `/api/therapy/session/start` with user A's token for user B's ID returns 403.
- [ ] **Step 2: Implement Supabase JWT verification in `backend/app/auth.py`**
  Verify JWT against Supabase JWT secret or JWKS endpoint; extract `sub` (user UUID); support guest session tokens with cryptographic HMAC signatures.
- [ ] **Step 3: Secure FastAPI endpoints with `Depends(get_current_user)`**
  Update:
  - `POST /api/assessment/submit`
  - `GET /api/assessment/history/{user_id}`
  - `POST /api/therapy/session/start`
  - `POST /api/therapy/session/end`
  - `GET /api/therapy/sessions/{user_id}`
  - `GET /api/therapy/session/{session_id}/messages`
  Assert `user_id == current_user.id` or `session.user_id == current_user.id`.
- [ ] **Step 4: Update Frontend `frontend/src/lib/api.ts`**
  Modify `apiFetch` to retrieve current Supabase session token via `supabase.auth.getSession()` and inject `Authorization: Bearer ${session.access_token}` on all requests.
- [ ] **Step 5: Run security test suite**
  Run: `pytest tests/test_security_auth.py -v`
  Expected: PASS (401 on missing token, 403 on IDOR attempts, 200 on authorized owner).

---

### Task 3.2: Re-Calibrate Text Risk Classifier for High-Risk Sensitivity
**Complexity:** High  
**Finding Addressed:** AUDIT-P1-08  
**Files:**
- Modify: `d:/EmoCare/backend/app/inference.py:70-96`
- Modify: `d:/EmoCare/models/text_mentalbert/metrics.json`
- Test: `d:/EmoCare/tests/test_text_risk_recall.py` (New)

**Interfaces:**
- Consumes: `text: str`.
- Produces: `TextResponse` with High-Risk Recall $\ge 85\%$ on acute hopelessness/distress phrasing.

- [ ] **Step 1: Write benchmark test for acute distress statements**
  Create `tests/test_text_risk_recall.py` containing 30 validated statements of hopelessness, suicidal ideation, and acute depression. Assert that $\ge 90\%$ trigger High risk.
- [ ] **Step 2: Implement asymmetric risk decision thresholding in `predict_text`**
  Instead of simple `np.argmax(probs)`:
  ```python
  HIGH_RISK_THRESHOLD = 0.20
  MODERATE_RISK_THRESHOLD = 0.35

  p_low, p_mod, p_high = probs[0], probs[1], probs[2]
  if p_high >= HIGH_RISK_THRESHOLD or _is_crisis_signal(text):
      predicted_tier = "High"
  elif p_mod >= MODERATE_RISK_THRESHOLD or (p_high + p_mod) >= 0.50:
      predicted_tier = "Moderate"
  else:
      predicted_tier = "Low"
  ```
- [ ] **Step 3: Run benchmark test**
  Run: `pytest tests/test_text_risk_recall.py -v`
  Expected: Statements like "I feel completely hopeless and exhausted with life" now correctly classify as "High" risk tier.

---

### Task 3.3: Voice Therapy Deterministic Safety Gating & CBT Tool Enforcement
**Complexity:** High  
**Finding Addressed:** AUDIT-P1-06  
**Files:**
- Modify: `d:/EmoCare/backend/app/engine/voice_therapy.py:175-230`
- Modify: `d:/EmoCare/backend/app/engine/llm_client.py:575-585`
- Test: `d:/EmoCare/tests/test_voice_therapy_safety.py` (New)

**Interfaces:**
- Consumes: User voice transcript, acoustic risk tier.
- Produces: Spoken therapy response strictly grounded in pre-approved CBT strategies, eliminating free-form clinical advice improvisation.

- [ ] **Step 1: Write test verifying no unvalidated advice in voice responses**
  In `tests/test_voice_therapy_safety.py`, verify that voice responses either offer active reflective listening or explicitly invoke a registered CBT technique from `recommendations.py`.
- [ ] **Step 2: Restrict voice mode prompt and enable tool selection**
  - Enable tool calling in voice mode in `llm_client.py:582`.
  - Rewrite system prompt in `voice_therapy.py`: Instruct LLM that it must NEVER invent novel therapeutic or diagnostic prescriptions; any recommended exercise must come from `get_cbt_coping_technique` or canonical breathing/grounding routines.
- [ ] **Step 3: Implement spoken post-sanitizer**
  Pass generated reply through `validate_and_sanitize_response` before ElevenLabs TTS synthesis to strip clinical claims, diagnoses, or ungrounded promises.
- [ ] **Step 4: Run voice safety tests**
  Run: `pytest tests/test_voice_therapy_safety.py -v`
  Expected: PASS.

---

### Task 3.4: Documentation Retraction & Scientific Claim Cleanup
**Complexity:** High  
**Findings Addressed:** AUDIT-P0-02, AUDIT-P1-07  
**Files:**
- Modify: `d:/EmoCare/docs/PRODUCT_DOCUMENTATION.md`
- Modify: `d:/EmoCare/reports/ablation_study.json`
- Modify: `d:/EmoCare/reports/ablation_study.csv`
- Modify: `d:/EmoCare/README.md`

**Interfaces:**
- Consumes: Verified audit realities.
- Produces: Accurate, scientifically truthful product and technical documentation.

- [ ] **Step 1: Retract 100% multimodal accuracy claim**
  Update `ablation_study.json`, `ablation_study.csv`, and `PRODUCT_DOCUMENTATION.md`: Mark synthetic multimodal benchmark as preliminary simulation; replace 1.0 accuracy claim with documented single-modality baselines.
- [ ] **Step 2: Correct model naming**
  Replace all claims of "MentalBERT / Bio_ClinicalBERT" with "TF-IDF N-gram Logistic Regression Classifier".
- [ ] **Step 3: Update architecture diagrams & dataset status**
  Accurately document that DAIC-WOZ and IEMOCAP datasets are pending acquisition and that current speech SER is trained on RAVDESS + CREMA-D.
- [ ] **Step 4: Review documentation accuracy**
  Perform self-review of `PRODUCT_DOCUMENTATION.md` against active code paths.
