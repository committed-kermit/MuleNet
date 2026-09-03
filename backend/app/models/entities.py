from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class AccountEntity(SQLModel, table=True):
    __tablename__ = "accounts"
    account_id: str = Field(primary_key=True)
    entity_id: str = Field(index=True)
    bank_id: str
    created_at: str

class EventEntity(SQLModel, table=True):
    __tablename__ = "events"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_id: str = Field(index=True)
    timestamp: str = Field(index=True)
    event_type: str
    metadata_json: Optional[str] = None

class TransactionEntity(SQLModel, table=True):
    __tablename__ = "transactions"
    transaction_id: str = Field(primary_key=True)
    sender_id: str = Field(index=True)
    receiver_id: str = Field(index=True)
    amount: float
    currency: str
    payment_format: str
    timestamp: str = Field(index=True)
    is_laundering_ground_truth: int = Field(default=0)

class DecisionLogEntity(SQLModel, table=True):
    __tablename__ = "decisions_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(index=True)
    sender_id: str = Field(index=True)
    receiver_id: str = Field(index=True)
    amount: float
    currency: str
    timestamp: str
    fused_score: float
    risk_tier: str
    recommended_action: str
    is_synthetic_risk: int = Field(default=0)
    decision_payload: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
