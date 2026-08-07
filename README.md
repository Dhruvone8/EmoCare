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
├── notebooks/
│   ├── 01_eda/                   # exploratory analysis, per dataset
│   ├── 02_preprocessing/
│   ├── 03_modeling/
│   └── 04_evaluation/
│
├── src/
│   ├── data/                     # loading + cleaning scripts (reusable, not notebook-only)
│   ├── features/                 # linguistic markers, prosodic feature extraction
│   ├── models/
│   │   ├── text_emotion/
│   │   ├── speech_emotion/
│   │   ├── risk_classifier/
│   │   └── fusion/
│   ├── explainability/           # SHAP/LIME wrappers
│   ├── api/                      # FastAPI app
│   ├── dashboard/                # Streamlit app
│   └── utils/
│
├── models/                       # saved trained model artifacts (gitignored — too large for git)
│   ├── text/
│   ├── speech/
│   └── risk/
│
├── configs/                      # yaml/json config files (paths, hyperparams)
├── tests/                        # unit tests for src/
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.dashboard
│   └── docker-compose.yml
├── scripts/                      # one-off setup/download scripts
├── docs/                         # your feature list, dataset docs, report drafts
├── logs/
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup & Quickstart

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**
   ```bash
   cp .env.example .env
   ```

3. **Run FastAPI Backend**
   ```bash
   uvicorn src.api.main:app --reload
   ```

4. **Run Streamlit Dashboard**
   ```bash
   streamlit run src/dashboard/app.py
   ```
