from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ActionDecision(str, Enum):
    ALLOW = "ALLOW"
    SOFT_CHALLENGE = "SOFT_CHALLENGE"
    STEP_UP_AUTH = "STEP_UP_AUTH"
    HOLD_FOR_REVIEW = "HOLD_FOR_REVIEW"

class ScoreRequest(BaseModel):
    account_id: str
    action_type: str = "transfer"
    amount: float
    currency: str = "USD"
    counterparty_id: str
    timestamp: str

class TypologyEvidence(BaseModel):
    name: str
    evidence: str

class ShapFactor(BaseModel):
    feature: str
    impact: float
    explanation: str

class LensScores(BaseModel):
    sequence_score: float
    network_score: float
    context_score: float
    anomaly_score: float

class ScoreResponse(BaseModel):
    transaction_id: str
    timestamp: str
    sender_id: str
    receiver_id: str
    amount: float
    currency: str
    fused_score: float
    risk_tier: RiskTier
    recommended_action: ActionDecision
    lenses: LensScores
    typologies: List[TypologyEvidence] = []
    shap_factors: List[ShapFactor] = []

class CommitRequest(BaseModel):
    transaction_id: str
    override_reason: Optional[str] = None

class CommitResponse(BaseModel):
    status: str
    transaction_id: str
    graph_updated: bool
    committed_at: str

class MetricsResponse(BaseModel):
    prevented_loss_value: float
    detection_lead_time_minutes: float
    false_challenge_rate_percent: float
    mule_ring_coverage_percent: float
    total_scored_actions: int
    flagged_critical_count: int

class GraphNode(BaseModel):
    id: str
    label: str
    risk_tier: RiskTier
    is_focus: bool = False

class GraphLink(BaseModel):
    source: str
    target: str
    amount: float
    gat_attention: float
    is_risky: bool = False

class EgoGraphResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]
