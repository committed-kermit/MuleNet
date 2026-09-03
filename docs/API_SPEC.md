# MuleNet — API Specification & JSON Contracts

## Base URL
`http://localhost:8000/api/v1`

---

## Endpoints Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/score-action` | Pre-commitment transaction scoring across Sequence, Network, and Context lenses. |
| `POST` | `/commit-action` | Finalizes a scored action, writes to DB, and mutates the in-memory graph. |
| `GET` | `/graph/ego/{account_id}` | Returns 1-2 hop neighborhood graph with GAT attention edge weights. |
| `GET` | `/cases` | Lists all flagged alerts and audit logs sorted by risk score. |
| `GET` | `/cases/{transaction_id}` | Detailed forensic dossier with SHAP factor impacts and typology evidence. |
| `GET` | `/metrics` | Live problem-statement metrics (Prevented Loss, Lead Time, False Challenge Rate, Ring Coverage). |
| `GET` | `/demo/stream` | Server-Sent Events (SSE) streaming real-time normal and malicious transactions. |
| `POST` | `/simulator/inject` | Injects synthetic attack scenarios (ATO, Smurfing, Ring Laundering) into the stream. |

---

## JSON Contracts

### 1. `POST /api/v1/score-action`
**Request:**
```json
{
  "account_id": "BANK01_ACC1042",
  "action_type": "transfer",
  "amount": 48500.0,
  "currency": "USD",
  "counterparty_id": "BANK04_ACC9011",
  "timestamp": "2026-09-03T14:32:00Z"
}
```

**Response:**
```json
{
  "transaction_id": "TXN-80412",
  "timestamp": "2026-09-03T14:32:00Z",
  "sender_id": "BANK01_ACC1042",
  "receiver_id": "BANK04_ACC9011",
  "amount": 48500.0,
  "currency": "USD",
  "fused_score": 0.88,
  "risk_tier": "CRITICAL",
  "recommended_action": "HOLD_FOR_REVIEW",
  "lenses": {
    "sequence_score": 0.92,
    "network_score": 0.84,
    "context_score": 0.70,
    "anomaly_score": 0.79
  },
  "typologies": [
    {
      "name": "Rapid Pass-Through",
      "evidence": "94% of received funds forwarded in under 8 minutes."
    },
    {
      "name": "Cross-Bank Mule Ring",
      "evidence": "Account belongs to a 4-node circular cycle crossing 3 banking institutions."
    }
  ],
  "shap_factors": [
    {
      "feature": "setup_to_action_gap",
      "impact": 0.38,
      "explanation": "Mobile number updated 45s before transfer attempt."
    },
    {
      "feature": "amount_zscore",
      "impact": 0.26,
      "explanation": "Transfer amount is 6.2x above sender historical average."
    }
  ]
}
```

---

### 2. `POST /api/v1/commit-action`
**Request:**
```json
{
  "transaction_id": "TXN-80412",
  "override_reason": "Investigator authorized release"
}
```

**Response:**
```json
{
  "status": "COMMITTED",
  "transaction_id": "TXN-80412",
  "graph_updated": true,
  "committed_at": "2026-09-03T14:32:05Z"
}
```

---

### 3. `GET /api/v1/metrics`
**Response:**
```json
{
  "prevented_loss_value": 1420500.00,
  "detection_lead_time_minutes": 14.2,
  "false_challenge_rate_percent": 1.8,
  "mule_ring_coverage_percent": 95.0,
  "total_scored_actions": 1250,
  "flagged_critical_count": 42
}
```

---

### 4. `GET /api/v1/graph/ego/{account_id}`
**Response:**
```json
{
  "nodes": [
    { "id": "BANK01_ACC1042", "label": "Sender", "risk_tier": "CRITICAL", "is_focus": true },
    { "id": "BANK04_ACC9011", "label": "Receiver", "risk_tier": "CRITICAL", "is_focus": false },
    { "id": "BANK02_ACC5510", "label": "Mule Hub", "risk_tier": "HIGH", "is_focus": false }
  ],
  "links": [
    { "source": "BANK01_ACC1042", "target": "BANK04_ACC9011", "amount": 48500, "gat_attention": 0.89, "is_risky": true },
    { "source": "BANK04_ACC9011", "target": "BANK02_ACC5510", "amount": 47000, "gat_attention": 0.75, "is_risky": true }
  ]
}
```
