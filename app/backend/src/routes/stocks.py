"""
FinShield - Stock Routes
GET  /api/v1/stocks/companies              → list all 5 companies
GET  /api/v1/stocks/companies/{id}         → company + stock matrix
POST /api/v1/stocks/hold                   → place 10-min hold on selected units
POST /api/v1/stocks/holds/{id}/confirm     → confirm payment → SOLD
POST /api/v1/stocks/holds/{id}/release     → cancel hold early → AVAILABLE
GET  /api/v1/stocks/holds/{id}/status      → hold status + countdown
GET  /api/v1/stocks/portfolio              → user's completed purchases
GET  /api/v1/stocks/my-holds              → all user's holds (any status)
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from models.stock import HoldRequest, HoldResponse, HoldListResponse, CompanyMatrixResponse
from services.auth_service import get_user_from_token
from services import stock_service as svc
from utils.logger import get_structured_logger

router = APIRouter()
logger = get_structured_logger("finshield.stocks.routes")
bearer = HTTPBearer(auto_error=False)


def require_auth(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Login required")
    user = get_user_from_token(creds.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# ── Companies ─────────────────────────────────────────────────────────────────

@router.get("/companies")
async def list_companies():
    return {"companies": svc.get_all_companies(), "total": len(svc.COMPANIES)}


@router.get("/companies/{company_id}")
async def get_company(company_id: str, user: dict = Depends(require_auth)):
    data = svc.get_matrix(company_id.upper(), current_user_id=user["user_id"])
    if not data:
        raise HTTPException(status_code=404, detail=f"Company {company_id} not found")
    return data


# ── Hold lifecycle ────────────────────────────────────────────────────────────

@router.post("/hold", response_model=HoldResponse, status_code=201)
async def place_hold(payload: HoldRequest, user: dict = Depends(require_auth)):
    if not payload.unit_ids:
        raise HTTPException(status_code=400, detail="Select at least one stock unit")
    if len(payload.unit_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 units per hold")
    try:
        hold = await svc.place_hold(payload.unit_ids, user["user_id"], user["username"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return HoldResponse(**hold)


@router.post("/holds/{hold_id}/confirm", response_model=HoldResponse)
async def confirm(hold_id: str, user: dict = Depends(require_auth)):
    hold = svc.confirm_hold(hold_id, user["user_id"])
    if not hold:
        existing = svc.get_hold(hold_id)
        if existing:
            raise HTTPException(status_code=409,
                detail=f"Hold is {existing['status']} — cannot confirm")
        raise HTTPException(status_code=404, detail="Hold not found or expired")
    return HoldResponse(**hold)


@router.post("/holds/{hold_id}/release", response_model=HoldResponse)
async def release(hold_id: str, user: dict = Depends(require_auth)):
    hold = svc.release_hold(hold_id, user["user_id"])
    if not hold:
        existing = svc.get_hold(hold_id)
        if existing:
            raise HTTPException(status_code=409,
                detail=f"Hold is {existing['status']} — cannot release")
        raise HTTPException(status_code=404, detail="Hold not found")
    return HoldResponse(**hold)


@router.get("/holds/{hold_id}/status", response_model=HoldResponse)
async def hold_status(hold_id: str, user: dict = Depends(require_auth)):
    hold = svc.get_hold(hold_id)
    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")
    return HoldResponse(**hold)


@router.get("/portfolio")
async def portfolio(user: dict = Depends(require_auth)):
    purchases = svc.get_user_portfolio(user["user_id"])
    return {"portfolio": purchases, "total": len(purchases)}


@router.get("/my-holds")
async def my_holds(user: dict = Depends(require_auth)):
    holds = svc.get_user_active_holds(user["user_id"])
    return {"holds": holds, "total": len(holds)}
