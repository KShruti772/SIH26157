# SAT-SA: Supervisory Analytics Tool for SOC Assessment

**Problem Statement:** SIH26157 — *Supervisory Analytics Tool for SOC Assessment (SAT-SA)*  
**Organization:** National Technical Research Organisation (NTRO) / Smart India Hackathon (SIH)

---

## 1. Executive Summary

**SAT-SA (Supervisory Analytics Tool for SOC Assessment)** is a human-in-the-loop supervisory analytics platform engineered for SOC leads, auditors, and security supervisors. Unlike traditional SIEMs or real-time intrusion detection systems, SAT-SA focuses on **post-operational supervisory oversight**—evaluating periodic SOC alert dumps, case-management records, and asset inventories to identify systemic security operational risks.

SAT-SA enables supervisors to:
- Detect **Execution Gaps** (e.g., critical alerts closed prematurely without proper escalation or investigation).
- Identify **Negative Space** (e.g., high-criticality assets lacking mandatory telemetry or logging).
- Uncover **Anomalies & Peer Deviations** (e.g., entities or analysts with abnormal resolution durations or disposition rates).
- Compute multi-factor **Supervisory Risk Scores** across Critical Sector Entities (CSEs).
- Prioritize findings into an actionable **Human-in-the-Loop Review Queue**.
- Inspect correlated timeline evidence in an interactive **Evidence Explorer**.
- Generate executive and technical **Supervisory Assessment Reports**.

---

## 2. Core Capabilities & Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SAT-SA Supervisory System                       │
├───────────────────────────────┬────────────────────────────────────────┤
│     Frontend (React + Vite)   │          Backend (FastAPI)             │
├───────────────────────────────┼────────────────────────────────────────┤
│ • Executive Dashboard         │ • RESTful API Endpoints (`/api/*`)     │
│ • Analysis Pipeline Trigger   │ • Multi-stage Analysis Workflow        │
│ • Findings & Risk Explorer    │ • SQLAlchemy ORM & Schema Validation   │
│ • Review Queue with Triage    │ • SQLite Local Storage Engine          │
│ • Evidence Timeline Inspector │ • Synthetic Scenario Ingestion Engine  │
│ • Statistical Peer Benchmarks │ • Audit Logging & Report Generation    │
│ • SOC Export Upload & Preview │ • Completely Air-Gapped / Offline      │
└───────────────────────────────┴────────────────────────────────────────┘
```

### Key Modules
1. **Executive Dashboard (`/`)**: High-level overview of entities analyzed, findings generated, risk distributions, and pending review counts.
2. **Analysis Pipeline (`/analysis`)**: Simulated 11-stage batch analytics pipeline (data validation, normalization, profiling, alert/case analysis, gap detection, anomaly scoring, risk computation).
3. **Findings & Gaps (`/findings`, `/findings/:id`)**: Drilldown into specific execution gaps, negative-space findings, and peer deviations with confidence scores and recommended remediation.
4. **Human-in-the-Loop Review Queue (`/review-queue`)**: Priority-ranked workflow allowing supervisors to review, annotate, and update status on high-risk findings.
5. **Entity Profiling (`/entities/:id`)**: Comprehensive breakdown of individual Critical Sector Entities (CSEs), alert histories, and multi-dimensional risk vectors.
6. **Evidence Explorer (`/evidence/:findingId`)**: Forensic timeline correlation linking findings to underlying alerts, cases, assets, and timestamps.
7. **Peer Benchmarking (`/benchmarks`)**: Statistical peer comparisons (medians, averages, percentiles, deviations) across operational metrics.
8. **Data Upload & Preview (`/upload`, `/upload/:id/preview`)**: Interface for uploading periodic SOC log dumps (CSV/JSON) and inspecting data schemas.
9. **Supervisory Reporting (`/reports`)**: Report compilation and export for compliance and auditing.

---

## 3. Technology Stack

- **Frontend**:
  - React 19 + Vite 8
  - Tailwind CSS v4
  - Lucide React (Icons)
  - Recharts (Data Visualizations)
  - Axios (HTTP Client)
  - React Router DOM v7 (Client-side Routing)
- **Backend**:
  - Python 3.9+
  - FastAPI (REST API framework)
  - Uvicorn (ASGI server)
  - SQLAlchemy 2.0 (ORM)
  - Pydantic v2 (Data validation & schemas)
  - SQLite (Local embedded relational database)
  - Pandas (Data analysis & inspection)

---

## 4. Repository Structure

```
SIH26157/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point & CORS configuration
│   │   ├── database.py          # SQLAlchemy SQLite connection & session management
│   │   ├── models/
│   │   │   └── domain.py        # SQLAlchemy database models (Entity, Alert, Finding, etc.)
│   │   ├── schemas/
│   │   │   └── api.py           # Pydantic request/response schemas
│   │   ├── routers/
│   │   │   └── api.py           # API endpoints (dashboard, findings, reviews, etc.)
│   │   ├── analytics/           # Analytics & ML module directory
│   │   ├── services/            # Business logic & services directory
│   │   └── utils/               # Backend utility helpers
│   ├── data/                    # Local SQLite database storage (excluded from git)
│   ├── seed.py                  # Database initialization and synthetic scenario seeding
│   └── requirements.txt         # Python backend dependencies
├── frontend/
│   ├── public/                  # Static assets (favicons, SVG icons)
│   ├── src/
│   │   ├── components/
│   │   │   └── Layout.jsx       # Global navigation bar, sidebar, and layout shell
│   │   ├── pages/               # Application views
│   │   │   ├── Dashboard.jsx
│   │   │   ├── AnalysisEngine.jsx
│   │   │   ├── Findings.jsx
│   │   │   ├── FindingDetail.jsx
│   │   │   ├── ReviewQueue.jsx
│   │   │   ├── EntityDetail.jsx
│   │   │   ├── EvidenceExplorer.jsx
│   │   │   ├── Benchmarks.jsx
│   │   │   ├── UploadData.jsx
│   │   │   ├── DataPreview.jsx
│   │   │   ├── ReportGeneration.jsx
│   │   │   └── Login.jsx
│   │   ├── services/
│   │   │   └── api.js           # Axios API client with auth interceptor
│   │   ├── App.jsx              # Application router configuration
│   │   ├── main.jsx             # React application DOM root
│   │   └── index.css            # Tailwind CSS styling definitions
│   ├── package.json             # Frontend dependencies and scripts
│   ├── vite.config.js           # Vite build and plugin configuration
│   └── .env.example             # Frontend environment variables template
├── data/
│   ├── public/                  # Raw public benchmark datasets (excluded from git)
│   │   ├── salad/               # SALAD-SOC dataset directory
│   │   └── ai_soc/              # AI-Improved SOC dataset directory
│   └── synthetic/               # Synthetic test datasets (excluded from git)
├── inspect_datasets.py          # Standalone dataset schema & sample inspection utility
├── requirements.txt             # Top-level Python dependency specification
├── .env.example                 # Top-level environment variable template
├── .gitignore                   # Comprehensive git ignore rules
└── README.md                    # Project documentation
```

---

## 5. SOC Datasets & Public Benchmarks

SAT-SA is designed to work with periodic exports from Security Operations Centers. For evaluation, benchmarking, and development, the project references two public SOC research datasets:

### 1. SALAD-SOC Dataset
- **Official Source**: [GitHub: nutthakorn7/SALAD-SOC](https://github.com/nutthakorn7/SALAD-SOC) | [HuggingFace: SALAD-SOC](https://huggingface.co/datasets/nutthakorn7/SALAD-SOC)
- **Purpose**: Large-scale benchmark of realistic SOC alert streams for evaluating triage decisions, alert prioritization, and attack categorization.
- **Local Placement**: Place downloaded raw files (`salad_train.txt`, `salad_val.txt`, `salad_test.txt` or `.csv`) into `data/public/salad/`.
- **Note**: Excluded from Git tracking due to file size (~880MB).

### 2. AI-Improved SOC Dataset
- **Official Source**: [Zenodo Record 21159447](https://zenodo.org/records/21159447)
- **Purpose**: Multi-table SOC dataset containing alerts, asset metadata, cyber threat intelligence (CTI) indicators, and analyst feedback. Used for analyzing telemetry coverage gaps and analyst disposition patterns.
- **Local Placement**: Place CSV files (`soc_alerts.csv`, `assets.csv`, `cti_indicators.csv`, `analyst_feedback.csv`) into `data/public/ai_soc/`.
- **Note**: Excluded from Git tracking.

### Inspecting Datasets
To inspect column schemas, data types, and sample records of local datasets:
```bash
python inspect_datasets.py
```

---

## 6. Getting Started & Local Setup

### Prerequisites
- **Python**: 3.9 or higher
- **Node.js**: 18 or higher (tested with Node 20 / 24)
- **npm**: 9 or higher

---

### Backend Installation & Database Setup

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # On macOS / Linux:
   python3 -m venv venv
   source venv/bin/activate

   # On Windows:
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize and seed the SQLite database with test scenarios:
   ```bash
   python seed.py
   ```
   *This initializes the database schema in `backend/data/satsa.db` and populates 10 Critical Sector Entities (CSE-001 to CSE-010) with realistic baseline alerts, injected execution gaps (CSE-003), and missing telemetry scenarios (CSE-005).*

5. Start the FastAPI backend server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *API will be live at `http://localhost:8000`. Interactive OpenAPI documentation is accessible at `http://localhost:8000/docs`.*

---

### Frontend Installation & Setup

1. In a new terminal, navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   *Frontend will be running at `http://localhost:5173`.*

4. To create a production build of the frontend:
   ```bash
   npm run build
   ```

---

## 7. Demo Credentials & Test Scenarios

### Login Credentials
- **Username**: `demo_supervisor`
- **Password**: `demo_password`

### Injected Diagnostic Scenarios (Seeded Data)
- **Scenario 1 (CSE-003 — Execution Gap)**: Critical-severity exfiltration alerts were acknowledged and closed within 5–6 minutes without required tier escalation, triggering finding `EG-0042` with high priority in the review queue.
- **Scenario 2 (CSE-005 — Negative Space)**: Critical infrastructure assets identified with zero incoming log telemetry over the assessment window, triggering finding `NS-0015`.
- **Scenario 3 (Peer Deviations)**: Investigation duration distributions and closure rates benchmarked against peer median/average percentiles across CSE cohorts.

---

## 8. Offline & Air-Gapped Operation

SAT-SA is architected with strict air-gapped constraints:
- **Zero External API Dependencies**: No runtime calls to external third-party cloud services or telemetry collectors.
- **Embedded Database Engine**: Uses self-contained local SQLite storage requiring no external database servers.
- **Local Asset Bundling**: All JavaScript, CSS, and icon assets (Lucide) are bundled locally through Vite.
- **No Secret Leakage**: Fully configurable via local `.env` variables with safe `.env.example` templates.

---

## 9. Limitations & Planned Roadmap

- **Batch Analytics Execution**: In the current version, `POST /api/analysis/run` simulates the multi-stage background execution pipeline; custom batch analytics scripts can be plugged into `backend/app/analytics/`.
- **ML Anomaly Detectors**: Isolation Forest, One-Class SVM, and clustering models for unsupervised SOC anomaly detection can be mounted into the analytics pipeline.
- **Custom Exporters**: Direct integration for STIX/TAXII and PDF export formats for supervisory compliance reports.

---

## 10. License & Attribution

Developed for **Smart India Hackathon (SIH) — Problem Statement SIH26157**.
