from typing import Tuple, Dict, Any
from app.models.schema import RiskTier, ActionDecision
from app.config import settings

class RiskFusionEngine:
    """
    Fuses Sequence, Network, Context, and Anomaly scores into a single
    calibrated risk metric and maps to graduated action tiers.
    """
    @staticmethod
    def fuse_scores(
        seq_score: float,
        net_score: float,
        ctx_score: float,
        anomaly_score: float
    ) -> Tuple[float, RiskTier, ActionDecision]:
        # Weighted ensemble fusion
        fused = (
            0.45 * seq_score +
            0.35 * net_score +
            0.10 * ctx_score +
            0.10 * anomaly_score
        )
        fused = max(0.0, min(1.0, round(fused, 4)))

        # Tier & Action classification
        if fused <= settings.TIER_LOW_MAX:
            tier = RiskTier.LOW
            action = ActionDecision.ALLOW
        elif fused <= settings.TIER_MEDIUM_MAX:
            tier = RiskTier.MEDIUM
            action = ActionDecision.SOFT_CHALLENGE
        elif fused <= settings.TIER_HIGH_MAX:
            tier = RiskTier.HIGH
            action = ActionDecision.STEP_UP_AUTH
        else:
            tier = RiskTier.CRITICAL
            action = ActionDecision.HOLD_FOR_REVIEW

        return fused, tier, action

risk_fusion_engine = RiskFusionEngine()
