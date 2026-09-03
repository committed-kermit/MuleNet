from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
import uuid
import json
from datetime import datetime

from app.models.schema import ScoreRequest, ScoreResponse, CommitRequest, CommitResponse, LensScores, TypologyEvidence, ShapFactor
from app.models.entities import DecisionLogEntity
from app.core.db import get_session
from app.core.memory_graph import memory_graph
from app.services.sequence_lens import sequence_risk_engine
from app.services.network_lens import network_risk_engine
from app.services.context_lens import context_risk_engine
from app.services.anomaly_engine import anomaly_engine
from app.services.typology_detector import typology_detector
from app.services.fusion_engine import risk_fusion_engine
from app.services.explainability import explainability_engine

router = APIRouter(tags=["Scoring & Decisions"])

# In-memory stores for prototype session
_SCORED_CACHE = {}

@router.post("/score-action", response_model=ScoreResponse)
async def score_action(payload: ScoreRequest, db: Session = Depends(get_session)):
    """
    Evaluates a pending transaction across Sequence, Network, and Context lenses
    strictly before the action timestamp. Does NOT write to the transaction graph.
    """
    txn_id = f"TXN-{uuid.uuid4().hex[:6].upper()}"

    # 0. Retrieve causal events and history
    events = memory_graph.get_events(payload.account_id)
    historical_txns = memory_graph.get_transactions(payload.account_id)

    # 1. Sequence Lens
    seq_score, seq_factors = sequence_risk_engine.score_sequence(
        account_id=payload.account_id,
        amount=payload.amount,
        as_of_timestamp=payload.timestamp,
        events=events,
        historical_txns=historical_txns
    )

    # 2. Network Lens
    net_score, net_factors = network_risk_engine.score_network(
        account_id=payload.account_id,
        counterparty_id=payload.counterparty_id,
        as_of_timestamp=payload.timestamp,
        graph_manager=memory_graph
    )

    # 3. Context Lens
    ctx_score, ctx_factors = context_risk_engine.score_context(
        amount=payload.amount,
        currency=payload.currency,
        counterparty_id=payload.counterparty_id,
        action_type=payload.action_type
    )

    # 4. Anomaly Engine
    feats = sequence_risk_engine.extract_features(
        account_id=payload.account_id,
        amount=payload.amount,
        as_of_timestamp=payload.timestamp,
        events=events,
        historical_txns=historical_txns
    )
    anom_score = anomaly_engine.score_anomaly(
        amount=payload.amount,
        velocity=max(1.0, feats.get("logins_1h", 1.0)),
        setup_gap=feats.get("setup_gap_minutes", 9999.0)
    )

    # 5. Fusion & Tier Assignment
    fused_score, tier, action = risk_fusion_engine.fuse_scores(
        seq_score=seq_score,
        net_score=net_score,
        ctx_score=ctx_score,
        anomaly_score=anom_score
    )

    # 6. Typologies & Explanations
    ego_data = memory_graph.get_ego_subgraph(payload.account_id, payload.timestamp, hops=2)
    neighbor_cnt = len(ego_data.get("nodes", []))

    typologies_raw = typology_detector.detect_typologies(
        amount=payload.amount,
        setup_gap_minutes=feats.get("setup_gap_minutes", 9999.0),
        neighbor_count=neighbor_cnt,
        is_ring_member=(net_score > 0.65)
    )

    shap_factors = explainability_engine.format_explanations(
        sequence_factors=seq_factors,
        network_factors=net_factors,
        context_factors=ctx_factors
    )

    typology_flags = [
        TypologyEvidence(name=t["name"], evidence=t["evidence"])
        for t in typologies_raw
    ]

    response = ScoreResponse(
        transaction_id=txn_id,
        timestamp=payload.timestamp,
        sender_id=payload.account_id,
        receiver_id=payload.counterparty_id,
        amount=payload.amount,
        currency=payload.currency,
        fused_score=fused_score,
        risk_tier=tier,
        recommended_action=action,
        lenses=LensScores(
            sequence_score=seq_score,
            network_score=net_score,
            context_score=ctx_score,
            anomaly_score=anom_score
        ),
        typologies=typology_flags,
        shap_factors=shap_factors
    )

    _SCORED_CACHE[txn_id] = {
        "score_data": response.model_dump() if hasattr(response, "model_dump") else response.dict(),
        "payload": payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    }

    # Log decision to SQLite
    try:
        log_entry = DecisionLogEntity(
            transaction_id=txn_id,
            sender_id=payload.account_id,
            receiver_id=payload.counterparty_id,
            amount=payload.amount,
            currency=payload.currency,
            timestamp=payload.timestamp,
            fused_score=fused_score,
            risk_tier=tier.value if hasattr(tier, "value") else str(tier),
            recommended_action=action.value if hasattr(action, "value") else str(action),
            sequence_score=seq_score,
            network_score=net_score,
            context_score=ctx_score,
            anomaly_score=anom_score,
            decision_payload=json.dumps(response.model_dump() if hasattr(response, "model_dump") else response.dict())
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        print(f"[routes_scoring] DB logging error: {e}")

    return response

@router.post("/commit-action", response_model=CommitResponse)
async def commit_action(payload: CommitRequest, db: Session = Depends(get_session)):
    """
    Post-Decision hook. If permitted/cleared, writes the verified edge to the memory graph.
    """
    cached = _SCORED_CACHE.get(payload.transaction_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Transaction pre-commitment score token expired or not found.")

    score_data = cached["score_data"]
    risk_tier = score_data.get("risk_tier")

    if risk_tier == "CRITICAL" and not payload.override_reason:
        raise HTTPException(
            status_code=403,
            detail="Transaction blocked by MuleNet CRITICAL Hold. Investigator override justification required."
        )

    # Add committed edge to the memory graph
    memory_graph.add_transaction_edge(
        sender_id=score_data["sender_id"],
        receiver_id=score_data["receiver_id"],
        amount=score_data["amount"],
        timestamp=score_data["timestamp"],
        currency=score_data.get("currency", "USD"),
        gat_attention=float(score_data.get("lenses", {}).get("network_score", 0.5)),
        is_risky=(score_data.get("fused_score", 0.0) > 0.6)
    )

    del _SCORED_CACHE[payload.transaction_id]

    return CommitResponse(
        transaction_id=payload.transaction_id,
        status="COMMITTED",
        graph_updated=True,
        committed_at=datetime.utcnow().isoformat() + "Z"
    )
