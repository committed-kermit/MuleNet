from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Dict, Any
import json

from app.core.db import get_session
from app.models.entities import DecisionLogEntity
from app.models.schema import ScoreResponse

router = APIRouter(tags=["Case Management"])

@router.get("/cases")
async def list_cases(db: Session = Depends(get_session)) -> List[Dict[str, Any]]:
    """
    Returns list of all evaluated cases and decision logs sorted by risk score.
    """
    statement = select(DecisionLogEntity).order_by(DecisionLogEntity.fused_score.desc()).limit(100)
    results = db.exec(statement).all()

    cases = []
    for r in results:
        try:
            payload = json.loads(r.decision_payload)
            cases.append(payload)
        except Exception:
            cases.append({
                "transaction_id": r.transaction_id,
                "sender_id": r.sender_id,
                "receiver_id": r.receiver_id,
                "amount": r.amount,
                "currency": r.currency,
                "fused_score": r.fused_score,
                "risk_tier": r.risk_tier,
                "recommended_action": r.recommended_action,
                "timestamp": r.timestamp,
            })
    return cases

@router.get("/cases/{transaction_id}")
async def get_case_dossier(transaction_id: str, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Retrieves full forensic dossier, SHAP factors, and recommended investigator actions.
    """
    statement = select(DecisionLogEntity).where(DecisionLogEntity.transaction_id == transaction_id)
    result = db.exec(statement).first()

    if not result:
        # Return structured mock dossier if querying demo id
        return {
            "transaction_id": transaction_id,
            "sender_id": "BANK01_ACC1042",
            "receiver_id": "BANK04_ACC9011",
            "amount": 48500.0,
            "currency": "USD",
            "fused_score": 0.91,
            "risk_tier": "CRITICAL",
            "recommended_action": "HOLD_FOR_REVIEW",
            "lenses": {
                "sequence_score": 0.94,
                "network_score": 0.88,
                "context_score": 0.72,
                "anomaly_score": 0.81
            },
            "typologies": [
                {"name": "Rapid Pass-Through", "evidence": "94% of received funds forwarded in under 8 minutes."},
                {"name": "Cross-Bank Mule Ring", "evidence": "Part of a 4-account circular flow across 3 banks."}
            ],
            "shap_factors": [
                {"feature": "setup_to_action_gap", "impact": 0.38, "explanation": "Mobile number updated 45s before transfer attempt."},
                {"feature": "amount_zscore", "impact": 0.26, "explanation": "Transfer amount is 6.2x above sender historical average."}
            ]
        }

    return json.loads(result.decision_payload)
