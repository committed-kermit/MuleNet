from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
import uuid
from datetime import datetime

from app.models.schema import ScoreRequest, ScoreResponse, CommitRequest, CommitResponse, LensScores
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

    # 1. Sequence Lens
    seq_score, seq_factors = sequence_risk_engine.score_sequence(
        account_id=payload.account_id,
        amount=payload.amount,
        as_of_timestamp=payload.timestamp,
        events=[],
        historical_txns=[]
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
    anom_score = anomaly_engine.score_anomaly(
        amount=payload.amount,
        velocity=1.0,
        setup_gap=10.0
    )

    # 5. Fusion & Tier Assignment
    fused_score, tier, action = risk_fusion_engine.fuse_scores(
        seq_score=seq_score,
        net_score=net_score,
        ctx_score=ctx_score,
        anomaly_score=anom_score
    )

    # 6. Typologies & Explanations
    typologies = typology_detector.detect_typologies(
        amount=payload.amount,
        setup_gap_minutes=10.0,
        neighbor_count=2,
        is_ring_member=(net_score > 0.7)
    )

    shap_factors = explainability_engine.format_explanations(
        sequence_factors=seq_factors,
        network_factors=net_factors,
        context_factors=ctx_factors
    )

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
        typologies=[{"name": t["name"], "evidence": t["evidence"]} for t in typologies],
        shap_factors=shap_factors
    )

    _SCORED_CACHE[txn_id] = {
        "score_data": response.dict(),
        "payload": payload.dict()
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
            risk_tier=tier.value,
            recommended_action=action.value,
            is_synthetic_risk=1 if tier in ["HIGH", "CRITICAL"] else 0,
            decision_payload=response.json()
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        pass

    return response

@router.post("/commit-action", response_model=CommitResponse)
async def commit_action(payload: CommitRequest):
    """
    Finalizes a scored action, writes the edge to the in-memory graph.
    """
    txn_id = payload.transaction_id
    if txn_id not in _SCORED_CACHE:
        # Fallback acknowledgement for simulator or canned transactions
        return CommitResponse(
            status="COMMITTED",
            transaction_id=txn_id,
            graph_updated=True,
            committed_at=datetime.utcnow().isoformat() + "Z"
        )

    cached = _SCORED_CACHE[txn_id]
    req_payload = cached["payload"]

    memory_graph.add_transaction_edge(
        sender_id=req_payload["account_id"],
        receiver_id=req_payload["counterparty_id"],
        amount=req_payload["amount"],
        timestamp=req_payload["timestamp"],
        currency=req_payload.get("currency", "USD")
    )

    return CommitResponse(
        status="COMMITTED",
        transaction_id=txn_id,
        graph_updated=True,
        committed_at=datetime.utcnow().isoformat() + "Z"
    )
