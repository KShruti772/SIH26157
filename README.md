# SAT-SA: Supervisory Analytics Tool for SOC Assessment

**Problem Statement:** SIH26157 — *Supervisory Analytics Tool for SOC Assessment (SAT-SA)*  
**Organization:** National Technical Research Organisation (NTRO) / Smart India Hackathon (SIH)

---

## 1. Executive Summary

**SAT-SA (Supervisory Analytics Tool for SOC Assessment)** is a human-in-the-loop supervisory analytics platform engineered for SOC leads, auditors, and security supervisors. Unlike traditional SIEMs or real-time intrusion detection systems, SAT-SA focuses on **post-operational supervisory oversight**—evaluating periodic SOC alert dumps, case-management records, and asset inventories to identify systemic security operational risks.

SAT-SA enables supervisors to:
- Ingest, validate, and normalize multi-format SOC dumps (CSV, TSV, TXT, JSON, JSONL).
- Profile data quality, detect malformed rows, missing timestamps, and duplicate identifiers.
- Detect **Execution Gaps** (e.g., critical alerts closed prematurely without proper escalation or investigation).
- Identify **Negative Space** (e.g., high-criticality assets lacking mandatory telemetry or logging).
- Uncover **Anomalies & Peer Deviations** (e.g., entities or analysts with abnormal resolution durations or disposition rates).
- Compute multi-factor **Supervisory Risk Scores** across Critical Sector Entities (CSEs).
- Prioritize findings into an actionable **Human-in-the-Loop Review Queue**.
- Inspect correlated timeline evidence in an interactive **Evidence Explorer**.
- Generate executive and technical **Supervisory Assessment Reports**.

---

## 2. Ingestion & Normalization Architecture (Modules 1 & 2)

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                REAL INGESTION PIPELINE                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Multipart Ingestion  ──► Safe stream reader with format & size verification         │
│ 2. Schema Detection     ──► Classifies dataset as Alerts, Assets, or Cases             │
│ 3. Canonical Adapters   ──► Maps external/vendor aliases to canonical SAT-SA fields    │
│ 4. Normalization Engine ──► Column snake_casing, Severity, Booleans, UTC Timestamps   │
│ 5. Quality Profiling    ──► Real calculations: missing fields, duplicates, invalid ts  │
│ 6. SQLite Persistence   ──► Atomically writes DatasetUpload and domain records         │
│ 7. Isolated Preview     ──► Previews exact records bound to the upload submission      │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Canonical Schemas
1. **Alerts Schema**: `alert_id` (Required), `timestamp` (Required, UTC), `severity` (`Critical`, `High`, `Medium`, `Low`), `category`, `asset_id`, `acknowledged`, `investigation_started`, `escalated`, `closed_at`, `disposition`, `investigation_duration_mins`, `closure_duration_mins`.
2. **Assets Schema**: `asset_id` (Required), `entity_id`, `type`, `criticality` (`Critical`, `High`, `Medium`, `Low`), `has_telemetry` (`True`/`False`).
3. **Cases Schema**: `case_id` (Required), `entity_id`, `alert_id`, `created_at` (Required, UTC), `investigator`, `investigation_duration`, `escalation_status`, `closure_time`, `closure_reason`, `evidence_count`.

### Normalization Policies
- **Column Names**: Converted to canonical lowercase snake_case (e.g., `"Alert ID"` -> `"alert_id"`).
- **Severity**: Canonicalized to `Critical`, `High`, `Medium`, `Low`, or `Unknown` from vendor variations (`"crit"`, `"Sev 1"`, `"1"`, `"informational"`, etc.).
- **Booleans**: Canonicalized from `1/0`, `yes/no`, `true/false`, `t/f`, `escalate/none`.
- **Timestamps**: Converted to UTC datetime objects; timezone-naive timestamps assume UTC and record a `timezone_assumed_utc` quality notice.
- **Duplicates**: Uniqueness enforced on primary IDs per submission; default policy retains the first valid record and records duplicates in the quality report.

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
  - Pytest (Automated test suite)

---

## 4. Repository Structure

```
SIH26157/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point & CORS configuration
│   │   ├── database.py          # SQLAlchemy SQLite connection & session management
│   │   ├── models/
│   │   │   └── domain.py        # Database models (DatasetUpload, Entity, Alert, Finding, etc.)
│   │   ├── schemas/
│   │   │   └── api.py           # Pydantic request/response & quality report schemas
│   │   ├── routers/
│   │   │   └── api.py           # API routes (/upload, /preview, /dashboard, /findings, etc.)
│   │   ├── services/            # Core business logic services
│   │   │   ├── ingestion.py     # Safe parsing, duplicate detection & DB persistence
│   │   │   ├── validation.py    # Schema validation (Required vs Optional vs Unknown)
│   │   │   ├── normalization.py # Normalizers (column names, severity, timestamps, booleans)
│   │   │   └── adapters.py      # Canonical field mappings & dataset type detection
│   │   ├── analytics/           # Analytics module directory (Module 4)
│   │   └── utils/               # Backend utility helpers
│   ├── tests/
│   │   └── test_ingestion.py    # Unit & integration test suite for Ingestion & Normalization
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
│   │   │   ├── UploadData.jsx    # Real file upload with dynamic quality breakdown
│   │   │   ├── DataPreview.jsx   # Real uploaded dataset preview table & search
│   │   │   ├── AnalysisEngine.jsx
│   │   │   ├── Findings.jsx
│   │   │   ├── FindingDetail.jsx
│   │   │   ├── ReviewQueue.jsx
│   │   │   ├── EntityDetail.jsx
│   │   │   ├── EvidenceExplorer.jsx
│   │   │   ├── Benchmarks.jsx
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

## 6. Assessment Assurance & Supervisory Core (Modules 3, 4 & 5)

> [!IMPORTANT]
> **Supervisory Assessment Assurance Methodology Disclaimer:**
> Assessment assurance is a proposed analytical methodology and prototype implementation. Thresholds, weights, and decision rules defined herein require validation against expert supervisory review and do not constitute statutory NCIIPC / NTRO standards.

### Core Conceptual Distinction: Finding Confidence vs. Assessment Validity
- **Finding Confidence**: Answers *"How strongly does the available evidence support this specific finding within the submitted dataset?"* (e.g., 91% / HIGH).
- **Assessment Validity**: Answers *"Is the available evidence sufficiently complete, representative, temporally covered, severity-covered, process-covered, internally consistent, and independent to support a broader supervisory conclusion?"* (Evaluated as `HIGH`, `CAUTION`, `LOW`, or `INDETERMINATE`).

A finding may possess **HIGH confidence** based on observed evidence while exhibiting **CAUTION validity** if the submitted evidence covers only part of the declared operational population. SAT-SA explicitly rejects opaque single 0–100 validity scores, presenting instead a structured, explainable assurance profile.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        ASSESSMENT ASSURANCE PROFILE (MODULE 5)                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. Population Exposure    ──► Observable records / Declared population (or UNKNOWN)    │
│ 2. Multidimensional Cov   ──► Temporal span, Severity tiers, Assets & 4 Process stages │
│ 3. Evidence Independence  ──► Evaluates shared source records across findings          │
│ 4. Contradiction Engine   ──► Detects conflicting records vs missing records           │
│ 5. Blind-Spot Detection   ──► Flags unmonitored assets & missing process stages        │
│ 6. Source Hash Integrity  ──► Deterministic SHA-256 baseline verification               │
│ 7. Supervisory Synthesis  ──► Human-in-the-loop explainable limitations & interpretation│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Assessment Assurance Dimensions
1. **Finding Confidence**: Deterministic heuristic calculation reflecting the volume, clarity, and consistency of observed records supporting a specific finding.
2. **Assessment Validity**: Multi-dimensional evaluation across 5 operational dimensions classifying overall assurance as `HIGH`, `CAUTION`, `LOW`, or `INDETERMINATE`.
3. **Population Exposure**: Compares observable population against declared submission population ($N_{\text{obs}} / N_{\text{claimed}}$). If no declared population is supplied, the system explicitly reports `UNKNOWN` without inventing a denominator.
4. **Multidimensional Evidence Coverage**: Evaluates observable span across Temporal window, Severity representation (Critical, High, Medium, Low), Asset inventory telemetry, and Process stages (Detection $\rightarrow$ Investigation $\rightarrow$ Escalation $\rightarrow$ Closure).
5. **Evidence Dependency & Independence**: Evaluates source record clustering to determine if multiple findings share identical underlying alert IDs (`HIGH_INDEPENDENCE`, `MODERATE_INDEPENDENCE`, `LOW_INDEPENDENCE`).
6. **Contradiction Detection**: Explicitly differentiates between `MISSING` evidence (an unrecorded stage) and `CONTRADICTORY` evidence (e.g., alert marked escalated while case record states unescalated, or `created_at` > `closure_time`).
7. **Evidence Blind Spots**: Identifies structural visibility gaps (e.g., zero critical alerts submitted, unmonitored critical assets, absent escalation telemetry) using neutral, non-accusatory supervisory language.
8. **Data Integrity & SHA-256 Hashing**: Calculates deterministic SHA-256 cryptographic hashes at ingestion for data immutability tracking and baseline tamper detection.
9. **Human Examiner Role**: Assures that automated heuristics advise and prioritize human examiners rather than making autonomous statutory judgments.

---

## 7. Local Agentic AI (Module 6)

> [!IMPORTANT]
> **Agentic AI Supervisory Safety Notice & Disclaimer:**
> The agentic layer provides analytical recommendations and evidence-grounded reasoning support. It does **NOT** replace human supervisory judgment or autonomously finalize supervisory assessments. Local LLM outputs require human validation and must not be treated as authoritative or immutable evidence.

SAT-SA incorporates an offline, evidence-grounded agentic reasoning layer designed to assist an NCIIPC human examiner in interrogating findings, performing adversarial critique, and formulating next-best evidence requests.

```
                  Evidence Graph + Analytics Findings + Assessment Assurance
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │   ASSESSMENT AGENT  │
                                  └──────────┬──────────┘
                                             │
                                   Assessment Hypothesis
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │   CHALLENGE AGENT   │
                                  └──────────┬──────────┘
                                             │
                                    Counter-evidence,
                                 Contradictions & Blind Spots
                                             │
                                             ▼
                                ┌──────────────────────────┐
                                │  INVESTIGATION PLANNER   │
                                └────────────┬─────────────┘
                                             │
                                 Next-Best Evidence Requests
                                             │
                                             ▼
                                 ┌────────────────────────┐
                                 │ HUMAN EXAMINER WORKSPACE│
                                 └────────────────────────┘
```

### 1. The Three Primary Agents
- **Assessment Agent**: Converts deterministic analytics and evidence traces into a structured, evidence-cited supervisory hypothesis.
- **Challenge Agent**: Performs adversarial critique to probe whether missing logs, submission truncation, or alternative operational explanations (e.g., external ticketing systems, SOAR automation) explain the observation.
- **Investigation Planner**: Recommends the next-best supervisory evidence request to reduce analytical uncertainty using a transparent prioritization heuristic:
  $$\text{Investigation Priority} = \frac{\text{Evidence Relevance} \times \text{Uncertainty Reduction} \times \text{Finding Importance}}{\text{Review Effort}}$$

### 2. Conceptual Separation of Confidences
$$\text{Finding Confidence} \neq \text{Assessment Validity} \neq \text{Agent Confidence}$$
- **Finding Confidence**: Strength of observed telemetry supporting a specific finding.
- **Assessment Validity**: Completeness and representativeness of evidence across the operational population.
- **Agent Confidence**: Model uncertainty in formulated hypotheses (not used as a substitute for evidence).

### 3. Agent Permissions & Guardrails
- **Strictly Prohibited Actions**: Agents cannot modify source evidence, delete records, alter findings, change risk scores, or finalize supervisory decisions.
- **Evidence ID Validation**: Every cited evidence ID is strictly verified against the bounded context; hallucinated identifiers are rejected or repaired.
- **Bounded Execution**: Maximum 3 agent steps (`MAX_AGENT_STEPS = 3`) to prevent unbounded loops.
- **Human-in-the-Loop**: Workflow strictly terminates at `HUMAN_REVIEW_REQUIRED`. Only a human examiner can record a final decision (`CONFIRMED`, `REQUEST_EVIDENCE`, `MODIFY`, `REJECTED`).

### 4. Local Model Architecture & Deterministic Fallback
- **Local Ollama Integration**: Interacts with local open-weight models (e.g., Llama-3, Mistral, Qwen 2.5) over `http://127.0.0.1:11434` with zero external network access.
- **Deterministic Fallback (`AGENT_MODE=DETERMINISTIC_FALLBACK`)**: If Ollama is offline or unavailable, SAT-SA automatically switches to deterministic template-based reasoning, ensuring that all supervisory functions remain operational without failure.

### 5. Machine-Readable Audit Trail
Every agent execution step records:
`run_id`, `agent_id`, `finding_id`, `timestamp`, `input_context_hash`, `model_provider`, `model_name`, `prompt_version`, `output_hash`, `referenced_evidence_ids`, `action`, `status`, `validation_result`.
These immutable audit records support post-assessment supervisory review and replay in Module 9.

---

## 8. Module 7: Human Examiner Workspace

Module 7 implements the dedicated supervisory workstation empowering human examiners as the sole final decision-makers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              HUMAN EXAMINER WORKFLOW                                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ REVIEW QUEUE ──► FINDING OVERVIEW ──► EVIDENCE TRACE ──► ASSESSMENT ASSURANCE          │
│                                                                  │                     │
│                                                                  ▼                     │
│ FINAL ASSESSMENT ◄── DECISION HISTORY ◄── HUMAN DECISION ◄── AGENTIC REVIEW           │
│                                            (Confirm/Request/                           │
│                                             Modify/Reject/Defer)                       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Workspace Features
1. **Interactive Review Queue**:
   - Multi-parameter filtering by Entity, Severity, Category, Assessment Validity, Decision Status, and Agent Status.
   - Dynamic sorting by Priority Score, Severity, Finding Confidence, Assessment Validity, and Created Timestamp.
   - Supervisory context callout (*"Why should the examiner look at this?"*).
2. **Unified Finding Workspace (`FindingDetail.jsx`)**:
   - **Section A: Finding Header**: Prominent presentation of Severity, Priority, Confidence, Assessment Validity (`HIGH`, `CAUTION`, `LOW`, `INDETERMINATE`), and Decision Status with advisory disclaimer.
   - **Section B: Observed Facts**: Ground-truth deterministic metrics, rule IDs, affected record counts, source hashes, and evidence IDs.
   - **Section C: Supervisory Rationale**: Triggering conditions and evidence-grounded interpretation.
   - **Section D: Interactive Evidence Explorer**: Full Entity → Asset → Alert → Case → Investigation → Escalation chain with missing link indicators.
   - **Section E: Assessment Assurance Matrix**: Structured breakdown across 8 dimensions (Population Exposure, Temporal Coverage, Severity Coverage, Asset Coverage, Process Coverage, Dependency, Contradictions, Source Integrity).
   - **Section F: Evidence Limitations**: Explicit segregation of Missing, Contradictory, Unknown, and Partial evidence.
   - **Section G: Agentic Supervisory Review**: Tri-panel advisory review presenting Assessment Agent hypotheses, Challenge Agent counter-evidence, and Investigation Planner recommendations.
   - **Section H: Human Examiner Decision**: Interactive action forms for `[ CONFIRM ]`, `[ REQUEST EVIDENCE ]`, `[ MODIFY ]`, `[ REJECT ]`, and `[ DEFER ]` with mandatory notes/rationale enforcement.
   - **Section I: Chronological Decision History & Audit Timeline**: Immutable append-only audit trail showing all analytical stages, agent evaluations, evidence requests, and examiner adjudications.

---

## 9. Module 8: Reporting & Supervisory Dashboard

Module 8 transforms underlying evidence, analytics, assessment assurance, and human adjudication into a complete, evidence-grounded supervisory evaluation:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              MODULE 8 REPORTING PIPELINE                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ CSE DATA ──► ANALYTICS ──► ASSURANCE ──► AGENT REVIEW ──► HUMAN ADJUDICATION           │
│                                                                  │                     │
│                                                                  ▼                     │
│ TRACEABLE EVIDENCE ◄── EXPORT (PDF/JSON) ◄── FINAL REPORT ◄── SUPERVISORY DASHBOARD    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Capabilities
1. **Supervisory Assessment Dashboard (`Dashboard.jsx`)**:
   - Live entity overview cards (record counts, finding counts, validity profile).
   - Prioritized Supervisory Attention Feed with direct link to examiner workspace.
   - 8 Operational Capabilities Overview with evidence-backed status chips (`OBSERVED CONCERN`, `NO OBSERVED CONCERN`, `INSUFFICIENT EVIDENCE`, `NOT ASSESSED`).
   - Categorized findings distribution & human examiner adjudication summary.
2. **Entity-Level Assessment View (`EntityDetail.jsx`)**:
   - Dedicated CSE evaluation view covering all 8 operational capabilities, assurance dimensions, evidence limitations, and active evidence requests.
   - One-click JSON export and printable PDF download.
3. **8 Operational Capability Evaluation**:
   - Evidence-grounded mapping across the 8 NCIIPC dimensions: *Threat Detection, Investigation, Escalation, Incident Response, Security Operations, Governance & Oversight, Operational Discipline, Cyber Resilience*.
   - Strictly enforces: *"Absence of a finding is not equivalent to proof of adequate performance."*
4. **Deterministic Report Compilation (`backend/app/services/reporting.py`)**:
   - Machine-readable structured JSON report objects.
   - Cryptographic traceability registry mapping every finding: $\text{Finding ID} \rightarrow \text{Analysis ID} \rightarrow \text{Evidence IDs} \rightarrow \text{Assurance} \rightarrow \text{Agent Run} \rightarrow \text{Human Decision}$.
5. **Printable Supervisory PDF Generator (ReportLab)**:
   - Self-contained, offline PDF compilation producing official NTRO/NCIIPC supervisory assessment documents with dynamic multi-page numbering, metadata tables, assurance matrices, and evidence limitation summaries.

---

## 10. Module 9: Cryptographic Audit & Replay Engine

Module 9 implements an offline, append-oriented, **tamper-evident cryptographic audit chain** and deterministic supervisory replay engine. It answers the fundamental supervisory question: *"Why did this assessment occur, what evidence and system actions led to it, what did the agents recommend, what did the human examiner decide, and can the final assessment state be mathematically reconstructed?"*

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        CRYPTOGRAPHIC AUDIT & REPLAY SUBSYSTEM                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ DATA INGESTION ──► ANALYTICS ──► ASSURANCE ──► AGENT RUNS ──► HUMAN ADJUDICATION       │
│        │                 │            │             │                 │                │
│        ▼                 ▼            ▼             ▼                 ▼                │
│  [DATA_INGESTED]   [FINDING_CRTD] [ASSURANCE] [AGENT_ASSESS]  [HUMAN_DECISION_CRTD]    │
│        │                 │            │             │                 │                │
│        └─────────────────┴────────────┼─────────────┴─────────────────┘                │
│                                       ▼                                                │
│                 TAMPER-EVIDENT CRYPTOGRAPHIC AUDIT CHAIN (SHA-256)                     │
│                (Canonical RFC-8785 JSON · Sequential Hash Linkage)                     │
│                                       │                                                │
│                   ┌───────────────────┴───────────────────┐                            │
│                   ▼                                       ▼                            │
│     ASSESSMENT SNAPSHOTS (SHA-256)          DETERMINISTIC REPLAY ENGINE                │
│     (Point-in-Time State Capture)      (Replay Events == Persisted State)              │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Key Capabilities
1. **Append-Only Audit Ledger (`backend/app/models/domain.py`)**:
   - `AuditEvent` records with canonical event identifiers, entity references, actor classification, timestamps, and structured payloads.
   - Strictly controlled event vocabulary: `DATA_INGESTED`, `DATA_VALIDATED`, `ANALYSIS_STARTED`, `ANALYSIS_COMPLETED`, `FINDING_CREATED`, `FINDING_UPDATED`, `ASSURANCE_CREATED`, `ASSURANCE_UPDATED`, `AGENT_RUN_STARTED`, `AGENT_ASSESSMENT_CREATED`, `AGENT_CHALLENGE_CREATED`, `AGENT_RECOMMENDATION_CREATED`, `AGENT_RUN_COMPLETED`, `EVIDENCE_REQUEST_CREATED`, `EVIDENCE_REQUEST_UPDATED`, `HUMAN_DECISION_CREATED`, `REPORT_GENERATED`, `SNAPSHOT_CREATED`, `REPLAY_STARTED`, `REPLAY_COMPLETED`.
   - Distinct actor tracking: `SYSTEM`, `ANALYTICS_ENGINE`, `ASSESSMENT_AGENT`, `CHALLENGE_AGENT`, `INVESTIGATION_PLANNER`, `HUMAN_EXAMINER`, `REPORTING_ENGINE`, `REPLAY_ENGINE`.
2. **Canonical Hashing & Cryptographic Chaining (`backend/app/services/audit.py`)**:
   - Deterministic canonical JSON serialization conforming to RFC-8785 conventions (sorted dictionary keys, normalized whitespace separators `(',', ':')`, ISO-8601 UTC timestamps, and UTF-8 encoding).
   - Sequential SHA-256 hash chaining: each event references the previous event's `event_hash` (`previous_event_hash = null` for stream genesis).
   - Tamper-evident verification: `verify_chain(...)` isolates exact event index, ID, and payload discrepancy if history is modified.
3. **Assessment Snapshots (`AssessmentSnapshot`)**:
   - Deterministic point-in-time state capture across entity profile, active findings, capability statuses, evidence limitations, agent conclusions, human decisions, and open evidence requests.
   - Computed `snapshot_hash` references evidence record IDs without duplicating raw underlying datasets.
4. **Deterministic Replay Engine (`ReplayEngine`)**:
   - Offline, rule-based state reconstruction without LLM non-determinism.
   - Validates chronological ordering, checks cryptographic hash links, applies state transitions, and compares reconstructed state directly against SQLite database records.
   - Returns structured evaluation metrics: `replay_valid`, `chain_integrity` (`VERIFIED`), `state_match` (`True`), `events_processed`, and `mismatches`.
5. **Human Adjudication Preservation & Historical Immutability**:
   - Historical audit records cannot be overwritten, modified, or deleted by agents.
   - Any modification or human reconsideration appends a new `HUMAN_DECISION_CREATED` or `FINDING_UPDATED` event to the chain, preserving complete supervisory provenance.
6. **Audit & Replay UI (`frontend/src/pages/AuditReplay.jsx`)**:
   - Dedicated supervisory workspace showing analysis ID, entity ID, chained event count, chain integrity badge, replay validity, and 100% state match confirmation.
   - Side-by-side comparative inspection of reconstructed vs live persisted database state.
   - Raw cryptographic event stream inspector displaying SHA-256 hashes, previous hash linkage, and formatted JSON payloads.

---

## 11. SOC Datasets & Public Benchmarks

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

---

## 11. Getting Started & Local Setup

### Prerequisites
- **Python**: 3.9 or higher
- **Node.js**: 18 or higher (tested with Node 20 / 24)
- **npm**: 9 or higher
- **Ollama** *(Optional for local LLM mode)*: `http://localhost:11434`

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

5. Run the automated test suite:
   ```bash
   PYTHONPATH=. pytest tests -v
   ```

6. Start the FastAPI backend server:
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

## 12. Demo Credentials & Test Scenarios

### Login Credentials
- **Username**: `demo_supervisor`
- **Password**: `demo_password`

### Injected Diagnostic Scenarios (Seeded Data)
- **Scenario 1 (CSE-003 — Execution Gap)**: Critical-severity exfiltration alerts were acknowledged and closed within 5–6 minutes without required tier escalation, triggering finding `EG-0042` with high priority in the review queue.
- **Scenario 2 (CSE-005 — Negative Space)**: Critical infrastructure assets identified with zero incoming log telemetry over the assessment window, triggering finding `NS-0015`.
- **Scenario 3 (Peer Deviations)**: Investigation duration distributions and closure rates benchmarked against peer median/average percentiles across CSE cohorts.

---

## 13. Offline & Air-Gapped Operation

SAT-SA is architected with strict air-gapped constraints:
- **Zero External API Dependencies**: No runtime calls to external third-party cloud services or telemetry collectors.
- **Embedded Database Engine**: Uses self-contained local SQLite storage requiring no external database servers.
- **Local Asset Bundling**: All JavaScript, CSS, and icon assets (Lucide) are bundled locally through Vite.
- **Local Model Runner**: Uses local Ollama instance on localhost or deterministic fallback.
- **No Secret Leakage**: Fully configurable via local `.env` variables with safe `.env.example` templates.

---

## 14. Implemented Milestone Status

- **Module 1 — CSE Data Submission**: Complete (100%)
- **Module 2 — Data Validation & Normalization**: Complete (100%)
- **Module 3 — Evidence Reconstruction**: Complete (100%)
- **Module 4 — Supervisory Analytics Engine**: Complete (100%)
- **Module 5 — Assessment Assurance**: Complete (100%)
- **Module 6 — Local Agentic AI**: Complete (100%)
- **Module 7 — Human Examiner Workspace**: Complete (100%)
- **Module 8 — Reporting & Supervisory Dashboard**: Complete (100%)
- **Module 9 — Audit & Replay Engine**: Complete (100%)

---

## 15. License & Attribution

Developed for **Smart India Hackathon (SIH) — Problem Statement SIH26157**.



