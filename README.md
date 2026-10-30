# EmoCare

EmoCare is a multi-modal emotional health analysis, speech/text emotion recognition, and risk classification framework.

## Project Structure

```
EmoCare/
├── data/
│   ├── raw/                     # untouched original downloads — never edit these
│   │   ├── goemotions/
│   │   ├── dreaddit/
│   │   ├── depression_severity/
│   │   ├── ravdess/
│   │   ├── crema_d/
│   │   ├── daic_woz/
│   │   ├── iemocap/
│   │   └── studentlife/
│   ├── interim/                 # partially cleaned/in-progress data
│   ├── processed/                # final, model-ready datasets
│   └── external/                 # label maps, lookup tables, reference files
│
├── backend/
│   └── app/                     # FastAPI application
│
├── frontend/                    # Next.js application (sole frontend)
│   └── src/
│       ├── app/                 # App Router pages
│       ├── components/          # Reusable UI components
│       ├── context/             # React context providers
│       ├── lib/                 # API helpers & utilities
│       └── types/               # TypeScript type definitions
│
├── notebooks/
│   ├── 01_eda/                   # exploratory analysis, data cleaning & feature extraction
│   └── 02_modeling/              # text, speech, and multimodal fusion modeling & evaluation
│
├── src/
│   ├── data/                     # loading + cleaning scripts
│   ├── features/                 # linguistic markers, prosodic feature extraction
│   ├── models/
│   │   ├── text_emotion/
│   │   ├── speech_emotion/
│   │   ├── risk_classifier/
│   │   └── fusion/
│   ├── explainability/           # SHAP/LIME wrappers
│   └── utils/
│
├── models/                       # saved trained model artifacts
│   ├── text_mentalbert/          # legacy directory name; TF-IDF + logistic regression artifacts
│   ├── speech_classifier/        # RAVDESS + CREMA-D speech emotion model
│   ├── behavioral_classifier/    # inactive StudentLife research artifact
│   └── fusion_engine/            # inactive meta-classifier artifact and retracted metrics
│
├── configs/                      # yaml/json config files (paths, hyperparams)
├── tests/                        # offline backend and API tests
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── scripts/                      # one-off setup/download scripts
├── docs/                         # product documentation and implementation plans
├── logs/
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Active implementation

- **Text risk:** TF-IDF N-gram Logistic Regression Classifier with asymmetric High and Moderate decision thresholds plus deterministic acute-distress safety signals. The directory name `text_mentalbert` is legacy; the active model is not MentalBERT or Bio_ClinicalBERT.
- **Speech emotion:** 40 MFCCs with mean and standard deviation, plus 15 prosodic features, classified by the RAVDESS + CREMA-D model.
- **Behavioral survey:** calibrated self-report lifestyle scoring. It does not pad survey answers into the StudentLife sensor model.
- **Multimodal fusion:** rule-based weighted late fusion over available modalities, with no synthetic meta-classifier decision in the active route.

DAIC-WOZ and IEMOCAP are pending acquisition and are not current training datasets. StudentLife remains an inactive research artifact rather than the behavioral survey engine.

## Clinical data authentication

Assessment history and therapy session routes require a verified Supabase bearer token or a server-issued guest token. Configure `SUPABASE_URL`, either `SUPABASE_JWT_SECRET` or `SUPABASE_JWKS_URL`, and an independent `GUEST_SESSION_SECRET` using `.env.example`. Guest IDs are generated and signed by the backend; client-provided IDs are not trusted.

## Benchmark status

The earlier perfect multimodal scores were produced by a preliminary synthetic simulation and are retracted. `reports/ablation_study.json` and `.csv` retain documented single-modality baselines and mark the synthetic multimodal metrics as null. No validated multimodal accuracy is currently claimed.

## Setup & Quickstart

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**
   - Root / Backend:
     ```bash
     cp .env.example .env
     ```
     Ensure `DATABASE_URL` (or leave empty for SQLite), `GUEST_SESSION_SECRET` (at least 32 characters), and your chosen LLM API key (`GROQ_API_KEY` or `OPENROUTER_API_KEY`) are set.
   - Frontend:
     ```bash
     cd frontend
     cp .env.example .env.local
     ```

3. **Run Tests**
   ```bash
   pytest
   ```

4. **Run FastAPI Backend**
   ```bash
   cd backend
   uvicorn app.main:app --reload --port 8000
   ```

5. **Run Next.js Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
