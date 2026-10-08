# Supervisory Analytics Tool for SOC Assessment (SAT-SA)

## Overview
SAT-SA is a prototype for the SIH 2026 problem statement SIH26157 by the National Technical Research Organisation (NTRO). It is a "Human-in-the-loop supervisory analytics" platform designed for supervisors to analyze periodic SOC alert and case-management data, specifically identifying areas requiring manual supervisory attention.

It is **NOT** a SOC, SIEM, or real-time log monitoring platform. It is a Supervisory Analytics Tool.

## Architecture
- **Frontend**: React, Vite, Tailwind CSS, React Router
- **Backend**: Python, FastAPI, SQLAlchemy, SQLite
- **Environment**: Designed for completely offline, air-gapped deployment.

## Workflow
1. **Upload**: Users upload periodic SOC exports (CSV/JSON).
2. **Analyze**: The backend runs validation and profiling.
3. **Execution Gaps**: Detects scenarios where security operators failed to follow proper procedures (e.g., closing critical alerts without escalation).
4. **Negative Space**: Identifies absence of expected security evidence (e.g., critical assets missing telemetry).
5. **Risk Assessment**: Computes overall supervisory risk based on findings.
6. **Explainability**: Every finding clearly explains *why* it was flagged, showing raw data deviations from peer baselines.
7. **Prioritization**: Generates a prioritized manual review queue for human validation.
8. **Evidence**: Provides an evidence explorer to drill down into the timeline of specific alerts/cases.
9. **Report**: Compiles all findings into a final Supervisory Report.

## Setup & Deployment (Offline)
This application can run completely offline.

### Requirements
- Node.js
- Python 3.9+

### Backend Setup
```bash
cd backend
python -m venv venv
# Activate virtual environment
source venv/bin/activate  # Or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
python seed.py # Seeds the database with synthetic data
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

## Demo Credentials
- **Username**: `demo_supervisor`
- **Password**: `demo_password`

## Synthetic Scenarios Injected
- **CSE-003**: Critical alerts closed without escalation (Execution Gap)
- **CSE-005**: Critical assets missing telemetry (Negative Space)
- **CSE-007**: Investigation Duration significantly lower than peers (Peer Deviation)

## Limitations & Future Work
- The current backend logic runs synthetic mocked analytics in `seed.py`. In a real-world scenario, the `POST /api/analysis/run` endpoint would execute the dataframes processing locally.
- Advanced machine learning (Isolation Forests for Anomaly detection) can be seamlessly integrated into the Python analytics engine.
