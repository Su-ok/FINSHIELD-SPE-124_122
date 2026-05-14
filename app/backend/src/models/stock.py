"""FinShield - Stock Models"""
from pydantic import BaseModel
from typing import Optional, List


class StockUnit(BaseModel):
    unit_id: str
    company_id: str
    tier: str
    price: float
    status: str          # AVAILABLE | HELD | SOLD
    row: int
    col: int
    held_by_username: Optional[str] = None
    seconds_remaining: Optional[int] = None


class Company(BaseModel):
    company_id: str
    name: str
    ticker: str
    sector: str
    logo: str
    description: str
    market_cap: str
    current_price: float
    change_pct: float
    available_units: int
    total_units: int


class CompanyMatrixResponse(BaseModel):
    company: Company
    matrix: dict   # tier_name -> List[StockUnit]


class HoldRequest(BaseModel):
    unit_ids: List[str]


class HoldResponse(BaseModel):
    hold_id: str
    user_id: str
    username: str
    company_name: Optional[str] = "Unknown Company"
    ticker: Optional[str] = "---"
    tier: Optional[str] = "Unknown Tier"
    unit_ids: List[str]
    total_amount: float
    status: str
    created_at: str
    expires_at: str
    seconds_remaining: int
    message: str


class HoldListResponse(BaseModel):
    holds: List[HoldResponse]
    total: int
