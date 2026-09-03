# MuleNet — Graph-First Pre-Commitment AML Risk Intelligence

MuleNet is an anti-money laundering (AML) detection and forensics platform designed to intercept mule account activity and coordinated laundering rings before transaction commitment.

By synthesizing IBM AML Graph Forensics with Lifecycle Pre-Commitment Intelligence, MuleNet evaluates transactions across three distinct risk dimensions: Sequence Risk, Network Risk (GNN), and Context Risk, outputting graduated friction tiers (LOW, MEDIUM, HIGH, CRITICAL) paired with human-readable forensic explanations.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │        PENDING ACTION REQUEST          │
                      │  (Amount, Payee, Account, Timestamp)   │
                      └───────────────────┬────────────────────┘
                                          │
                  Strict Causal Filter (as_of_timestamp < T)
                                          │
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
   ┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
   │  SEQUENCE LENS  │           │  NETWORK LENS   │           │  CONTEXT LENS   │
   │ XGBoost on Life-│           │ 2-Layer PyG GAT │           │ Heuristic rules │
   │ cycle Event Log │           │ + Attention Wts │           │ & Mismatch flags│
   └────────┬────────┘           └────────┬────────┘           └────────┬────────┘
            │                             │                             │
            └───────────────────────┬─────┴─────────────────────────────┘
                                    ▼
                      ┌───────────────────────────┐
                      │  FUSION & FORENSIC ENGINE │
                      │  * Multimodal Scoring     │
                      │  * Typology & Motif Rules │
                      │  * SHAP Tree Explanations │
                      └─────────────┬─────────────┘
                                    │
                                    ▼
                      ┌───────────────────────────┐
                      │ GRADUATED DECISION MATRIX │
                      │ Low | Medium | High | Crit│
                      └───────────────────────────┘
```

---

## Repository Structure

```
MuleNet/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application & lifespan loader
│   │   ├── config.py                   # Global configuration & thresholds
│   │   ├── api/                        # REST & Streaming endpoints
│   │   │   ├── routes_scoring.py       # /score-action, /commit-action
│   │   │   ├── routes_cases.py         # /cases, /cases/{id} forensic dossiers
│   │   │   ├── routes_graph.py         # /graph/ego/{account_id}
│   │   │   ├── routes_metrics.py       # /metrics (Loss prevented, lead time)
│   │   │   ├── routes_demo.py          # /demo/stream (Real-time SSE replay)
│   │   │   └── routes_simulator.py     # /simulator/inject (Attack triggers)
│   │   ├── core/                       # In-memory graph, DB sessions, causal checks
│   │   ├── models/                     # Pydantic schemas & SQLite entities
│   │   └── services/                   # ML lenses, GNN, SHAP & Typology engines
│   ├── artifacts/                      # Serialized ML models (.pt, .json, .joblib)
│   └── requirements.txt                # Pinned backend dependencies
├── frontend/
│   ├── src/
│   │   ├── components/                 # UI components (Feed, Graph, Modal, KPI)
│   │   ├── api/                        # API client & Mock fixtures
│   │   ├── App.jsx                     # Master platform layout & state store
│   │   └── main.jsx                    # React entrypoint
│   └── package.json                    # Frontend dependencies
├── data/
│   ├── raw/                            # IBM AML raw CSV files
│   ├── processed/                      # Parquet files & synthetic ground truth
│   └── README.md                       # Data dictionary & provenance
├── docs/
│   ├── ARCHITECTURE.md                 # Detailed architectural spec
│   └── API_SPEC.md                     # Complete JSON request/response contracts
└── requirements.txt                    # Top-level dependency manifest
```

---

## Quick Start

### 1. Backend Setup
```bash
# Navigate to backend and create virtual environment
cd backend
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run FastAPI development server
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger API documentation will be available at `http://localhost:8000/docs`.

### 2. Frontend Setup
```bash
# Navigate to frontend
cd frontend
npm install
npm run dev
```
Dashboard will be accessible at `http://localhost:5173`.

---

## Team Workstreams

* **Person 1 (Frontend Lead):** React Dashboard, Force-Directed Graph UI, Dossier Modal, Attack Simulator.
* **Person 2 (ML - GNN):** PyG GAT model, Graph Attention weights, Subgraph extractor.
* **Person 3 (ML - Sequence & SHAP):** Tabular feature extraction, Sequence XGBoost, Isolation Forest, SHAP explainability.
* **Person 4 (Backend Lead - Core):** FastAPI core, In-memory NetworkX engine, Time-safe scoring pipeline.
* **Person 5 (Backend Lead - Forensics & Streaming):** Typology detectors, Live Metrics engine, Replay streaming.
