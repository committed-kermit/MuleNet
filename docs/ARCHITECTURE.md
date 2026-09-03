# MuleNet — System Architecture & Design Specification

## 1. Overview
MuleNet is an end-to-end, graph-first pre-commitment Anti-Money Laundering (AML) risk intelligence platform.
It scores pending financial actions (transfers, payee additions, trades) in real time across three independent risk lenses before commitment, providing graduated action tiers (LOW, MEDIUM, HIGH, CRITICAL) and human-readable forensic evidence.

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 INCOMING REQUEST STREAM                 │
                  │        (Live / Replay / Single Scoring / Bulk CSV)      │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                               ▼
     ┌───────────────────────────────────────────────────────────────────────────────────┐
     │                      TIME-SAFE INGESTION & CAUSAL FILTER                          │
     │     Enforces as_of_timestamp < T: graph & sequence only see strictly prior state  │
     └─────────────────┬───────────────────────┬───────────────────────────┬─────────────┘
                       │                       │                           │
                       ▼                       ▼                           ▼
        ┌────────────────────────┐ ┌────────────────────────┐ ┌────────────────────────┐
        │     LENS 1: SEQUENCE   │ │     LENS 2: NETWORK    │ │     LENS 3: CONTEXT    │
        │   Lifecycle Event DB   │ │   In-Memory Ego-Graph  │ │  Rule Engine & Payload │
        │  * Setup-to-Action gap │ │   * 2-hop GAT / SAGE   │ │  * Amount vs entity    │
        │  * Login velocity      │ │   * Degree, PageRank   │ │  * Currency mismatch   │
        │  * XGBoost Sequence    │ │   * Attention Weights  │ │  * Rapid payee match   │
        └──────────────┬─────────┘ └───────────┬────────────┘ └────────────┬───────────┘
                       │                       │                           │
                       └───────────────────┐   │   ┌───────────────────────┘
                                           ▼   ▼   ▼
     ┌───────────────────────────────────────────────────────────────────────────────────┐
     │                             FUSION & FORENSICS CORE                               │
     │  * Ensemble Model: Sequence XGBoost + Network GAT + Context Heuristics            │
     │  * Typology & Motif Matcher: Rapid pass-through, Fan-in/out, Smurfing, Rings      │
     │  * Explainability Engine: SHAP TreeExplainer + GAT Attention Edge Attribution     │
     └─────────────────────────────────────────┬─────────────────────────────────────────┘
                                               │
                                               ▼
     ┌───────────────────────────────────────────────────────────────────────────────────┐
     │                             GRADUATED DECISION MATRIX                             │
     │    Tier: Low (Allow) | Medium (Challenge) | High (Step-Up) | Critical (Hold)      │
     │    Returns: Fused Score, Plain-Language Reasons, Typology Flags, Recommended SLA  │
     └────────────────────────┬────────────────────────────────────────┬─────────────────┘
                              │                                        │
           (If Transaction Committed)                     (If Case Flagged)
                              ▼                                        ▼
                 ┌───────────────────────────┐           ┌───────────────────────────┐
                 │ Dynamic Graph & DB Update │           │   Decisions & Case Log    │
                 │   (NetworkX + SQLite WAL) │           │    (Live Metrics API)     │
                 └───────────────────────────┘           └───────────────────────────┘
```

## 2. Risk Lenses & Forensic Pipeline

### 2.1 Lens 1: Sequence Risk Engine (Tabular ML)
- Computes behavioral features from strictly prior lifecycle events:
  - `setup_to_action_gap`: Elapsed time between recent profile/credential update or payee addition and the pending transaction.
  - `time_since_last_profile_change_minutes`
  - `dormancy_then_activity_flag`: Burst in activity following >30 days of dormancy.
  - `login_velocity_1h` and `login_velocity_24h`
  - `amount_zscore_vs_account_history`
- Evaluated via a trained XGBoost Classifier yielding sequence_score in [0, 1].

### 2.2 Lens 2: Network Risk Engine (GNN & Graph Forensics)
- Graph built from `TRANSACTED_WITH` and `SHARES_DEVICE` edges.
- Node features: In-degree, out-degree, PageRank, account tenure, historical volume.
- Model: 2-Layer Graph Attention Network (GAT) with exposed attention coefficients (alpha).
- Inference: Evaluates 1–2 hop ego-subgraphs dynamically, outputting network_score in [0, 1] and top contributing neighbor edges.

### 2.3 Lens 3: Context Risk Engine (Rule & Heuristics)
- Validates transaction payload against established behavioral norms:
  - First-time high-value transfer to unverified payee.
  - Currency mismatch flags (payment vs receiving currency).
  - Cross-bank velocity thresholds.

### 2.4 Anomaly Detection Engine (Novelty Scoring)
- Unsupervised Isolation Forest fitted on legitimate baseline behavior, outputting anomaly_score in [0, 1].

### 2.5 Typology & Motif Detector
- Deterministic rules identifying complex money laundering topographies:
  - Rapid Pass-Through: Forwarding >= 80% of received funds within tight time windows.
  - Fan-In / Collection Hub: Disproportionate ratio of incoming counterparties.
  - Fan-Out / Dispersal Node: Rapid dispersal of large deposits to multiple destinations.
  - Circular Routing: Multi-hop closed-loop cycles (A -> B -> C -> A).
  - Device Sharing Syndicate: Multiple accounts operating from identical device fingerprints.

---

## 3. Decision Matrix & Action Tiers

| Tier | Fused Score Range | Recommended Action | Friction Level |
|---|---|---|---|
| Low | 0.00 – 0.30 | ALLOW | Seamless (Zero user friction) |
| Medium | 0.30 – 0.60 | SOFT_CHALLENGE | Passive MFA / Biometric verification |
| High | 0.60 – 0.85 | STEP_UP_AUTH | Dynamic delay, payee re-confirmation, Level 1 AML review |
| Critical | 0.85 – 1.00 | HOLD_FOR_REVIEW | Transaction blocked, Account freeze, Level 2 AML investigation |
