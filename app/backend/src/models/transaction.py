"""
FinShield - Transaction Models
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
import uuid


class TransactionCreate(BaseModel):
    sender_account: str = Field(..., json_schema_extra={"example": "ACC-001234"})
    receiver_account: str = Field(..., json_schema_extra={"example": "ACC-005678"})
    amount: float = Field(..., gt=0, le=1_000_000, json_schema_extra={"example": 500.00})
    transaction_type: str = Field(default="transfer", json_schema_extra={"example": "transfer"})
    currency: str = Field(default="USD", max_length=3)
    metadata: Optional[dict] = None


class TransactionResponse(BaseModel):
    transaction_id: str
    sender_account: str
    receiver_account: str
    amount: float
    currency: str
    transaction_type: str
    status: str
    fraud_score: float
    timestamp: str
    message: str


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int


# ── Hold Models ───────────────────────────────────────────────────────────────

class HoldCreate(BaseModel):
    """Request body for placing a fund hold (10-min payment window)."""
    sender_account: str   = Field(..., json_schema_extra={"example": "ACC-001234"})
    receiver_account: str = Field(..., json_schema_extra={"example": "ACC-005678"})
    amount: float         = Field(..., gt=0, le=1_000_000, json_schema_extra={"example": 500.00})
    transaction_type: str = Field(default="transfer", json_schema_extra={"example": "transfer"})
    currency: str         = Field(default="USD", max_length=3)


class HoldResponse(BaseModel):
    """Full hold object returned by the API."""
    transaction_id:   str
    sender_account:   str
    receiver_account: str
    amount:           float
    currency:         str
    transaction_type: str
    fraud_score:      float
    status:           str          # HELD | COMPLETED | EXPIRED | RELEASED
    created_at:       str
    expires_at:       str
    seconds_remaining: int
    message:          str


class HoldListResponse(BaseModel):
    holds: list[HoldResponse]
    total: int
