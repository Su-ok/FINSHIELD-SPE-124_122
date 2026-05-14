"""
FinShield - Stock Service
5 fake companies, each with a tiered stock matrix (like cinema seat selection).
10-minute hold locks prevent double-purchasing — exactly like ticket booking.
"""
import uuid, asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from utils.logger import get_structured_logger

logger = get_structured_logger("finshield.stocks")

HOLD_SECONDS = 600          # 10 minutes
TIER_ORDER = ["Bronze", "Silver", "Gold", "Platinum"]

# ── Fake company catalogue ────────────────────────────────────────────────────
COMPANIES: dict[str, dict] = {
    "TKCR": {
        "company_id": "TKCR", "name": "TechCore Ltd", "ticker": "TKCR",
        "sector": "Technology", "logo": "💻",
        "description": "Leading AI & Cloud solutions provider in India",
        "market_cap": "₹45,230 Cr", "current_price": 342.50, "change_pct": 2.34,
        "tiers": {"Bronze": {"price": 20, "cols": 10}, "Silver": {"price": 50, "cols": 10},
                  "Gold": {"price": 100, "cols": 8}, "Platinum": {"price": 200, "cols": 5}},
    },
    "FNBK": {
        "company_id": "FNBK", "name": "FinBank Corp", "ticker": "FNBK",
        "sector": "Banking & Finance", "logo": "🏦",
        "description": "India's fastest growing digital banking platform",
        "market_cap": "₹82,100 Cr", "current_price": 1204.75, "change_pct": -0.87,
        "tiers": {"Bronze": {"price": 30, "cols": 10}, "Silver": {"price": 75, "cols": 10},
                  "Gold": {"price": 150, "cols": 8}, "Platinum": {"price": 300, "cols": 5}},
    },
    "GREN": {
        "company_id": "GREN", "name": "GreenEnergy", "ticker": "GREN",
        "sector": "Renewable Energy", "logo": "⚡",
        "description": "Solar & wind energy solutions across South Asia",
        "market_cap": "₹28,750 Cr", "current_price": 567.20, "change_pct": 5.12,
        "tiers": {"Bronze": {"price": 25, "cols": 10}, "Silver": {"price": 60, "cols": 10},
                  "Gold": {"price": 120, "cols": 8}, "Platinum": {"price": 250, "cols": 5}},
    },
    "MDCR": {
        "company_id": "MDCR", "name": "MediCure", "ticker": "MDCR",
        "sector": "Healthcare", "logo": "💊",
        "description": "Pharmaceutical & biotech research leader",
        "market_cap": "₹19,400 Cr", "current_price": 892.30, "change_pct": -1.45,
        "tiers": {"Bronze": {"price": 45, "cols": 10}, "Silver": {"price": 90, "cols": 10},
                  "Gold": {"price": 180, "cols": 8}, "Platinum": {"price": 350, "cols": 5}},
    },
    "SPXI": {
        "company_id": "SPXI", "name": "SpaceX India", "ticker": "SPXI",
        "sector": "Aerospace", "logo": "🚀",
        "description": "Satellite launch & space tech pioneer",
        "market_cap": "₹1,12,000 Cr", "current_price": 4521.00, "change_pct": 8.76,
        "tiers": {"Bronze": {"price": 100, "cols": 10}, "Silver": {"price": 250, "cols": 8},
                  "Gold": {"price": 500, "cols": 6}, "Platinum": {"price": 1000, "cols": 4}},
    },
}

# ── Stock unit store ──────────────────────────────────────────────────────────
_units: dict[str, dict] = {}   # unit_id → unit
_holds: dict[str, dict] = {}   # hold_id → hold


def _init():
    for comp_id, comp in COMPANIES.items():
        for row_idx, tier in enumerate(TIER_ORDER):
            cfg = comp["tiers"].get(tier)
            if not cfg:
                continue
            for col in range(cfg["cols"]):
                uid = f"{comp_id}-{tier[:3].upper()}-{col+1:02d}"
                _units[uid] = {
                    "unit_id": uid, "company_id": comp_id, "tier": tier,
                    "price": cfg["price"], "status": "AVAILABLE",
                    "row": row_idx, "col": col,
                    "held_by_user_id": None, "held_by_username": None,
                    "hold_id": None, "held_until": None,
                }

_init()


# ── Public helpers ────────────────────────────────────────────────────────────

def get_all_companies() -> list[dict]:
    result = []
    for comp_id, comp in COMPANIES.items():
        these = [u for u in _units.values() if u["company_id"] == comp_id]
        result.append({**comp,
                        "available_units": sum(1 for u in these if u["status"] == "AVAILABLE"),
                        "total_units": len(these)})
    return result


def get_matrix(company_id: str, current_user_id: str = "") -> Optional[dict]:
    comp = COMPANIES.get(company_id)
    if not comp:
        return None
    now = datetime.now(timezone.utc)
    matrix = {t: [] for t in TIER_ORDER if t in comp["tiers"]}
    these = [u for u in _units.values() if u["company_id"] == company_id]
    for unit in sorted(these, key=lambda x: (x["row"], x["col"])):
        u = unit.copy()
        if u["status"] == "HELD" and u["held_until"]:
            exp = datetime.fromisoformat(u["held_until"])
            if now > exp:
                _free_unit(u["unit_id"])
                u.update({"status": "AVAILABLE", "held_by_username": None, "seconds_remaining": None})
            else:
                u["seconds_remaining"] = max(0, int((exp - now).total_seconds()))
                if u["held_by_user_id"] != current_user_id:
                    u["held_by_username"] = "another user"
        matrix[u["tier"]].append(u)

    these = [u for u in _units.values() if u["company_id"] == company_id]   # refresh
    return {
        "company": {**comp,
                    "available_units": sum(1 for u in these if u["status"] == "AVAILABLE"),
                    "total_units": len(these)},
        "matrix": matrix,
    }


def _free_unit(unit_id: str):
    u = _units.get(unit_id)
    if u:
        u.update({"status": "AVAILABLE", "held_by_user_id": None,
                  "held_by_username": None, "hold_id": None, "held_until": None})


# Global lock to prevent race conditions during inventory checks
inventory_lock = asyncio.Lock()


async def place_hold(unit_ids: list[str], user_id: str, username: str) -> dict:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=HOLD_SECONDS)
    
    # ATOMIC BLOCK: Ensure no other request can check/modify status during this check
    async with inventory_lock:
        for uid in unit_ids:
            u = _units.get(uid)
            if not u:
                raise ValueError(f"Unit {uid} not found")
            if u["status"] != "AVAILABLE":
                # Race condition handled: if someone else grabbed it while this request was in flight
                raise ValueError(f"Unit {uid} is no longer available")

        total = sum(_units[uid]["price"] for uid in unit_ids)
        hold_id = f"HOLD-{uuid.uuid4().hex[:10].upper()}"

        for uid in unit_ids:
            _units[uid].update({"status": "HELD", "held_by_user_id": user_id,
                                 "held_by_username": username, "hold_id": hold_id,
                                 "held_until": expires_at.isoformat()})

    # Capture company details for the portfolio view
    first_u = _units[unit_ids[0]]
    comp = COMPANIES.get(first_u["company_id"], {})
    comp_name = comp.get("name", "Unknown")
    ticker = comp.get("ticker", "---")

    hold = {"hold_id": hold_id, "user_id": user_id, "username": username,
            "company_name": comp_name, "ticker": ticker, "tier": first_u["tier"],
            "unit_ids": unit_ids, "total_amount": total, "status": "HELD",
            "created_at": now.isoformat(), "expires_at": expires_at.isoformat(),
            "seconds_remaining": HOLD_SECONDS,
            "message": f"₹{total:,.0f} locked for 10 min. Confirm before expiry."}
    _holds[hold_id] = hold

    logger.info("Stock hold placed", extra={"hold_id": hold_id, "user": username,
                                             "units": unit_ids, "total": total})
    asyncio.create_task(_auto_expire(hold_id, HOLD_SECONDS))
    return hold


def confirm_hold(hold_id: str, user_id: str) -> Optional[dict]:
    h = _holds.get(hold_id)
    if not h or h["user_id"] != user_id or h["status"] != "HELD":
        return None
    if datetime.now(timezone.utc) > datetime.fromisoformat(h["expires_at"]):
        return None
    for uid in h["unit_ids"]:
        u = _units.get(uid)
        if u:
            u["status"] = "SOLD"
    h.update({"status": "COMPLETED", "seconds_remaining": 0,
               "message": "Payment confirmed! Stocks are now yours. 🎉"})
    logger.info("Stock hold confirmed", extra={"hold_id": hold_id, "user_id": user_id})
    return h


def release_hold(hold_id: str, user_id: str) -> Optional[dict]:
    h = _holds.get(hold_id)
    if not h or h["user_id"] != user_id or h["status"] != "HELD":
        return None
    for uid in h["unit_ids"]:
        _free_unit(uid)
    h.update({"status": "RELEASED", "seconds_remaining": 0,
               "message": "Hold cancelled. Stocks returned to market."})
    logger.info("Stock hold released", extra={"hold_id": hold_id, "user_id": user_id})
    return h


def get_hold(hold_id: str) -> Optional[dict]:
    h = _holds.get(hold_id)
    if not h:
        return None
    if h["status"] == "HELD":
        exp = datetime.fromisoformat(h["expires_at"])
        remaining = max(0, int((exp - datetime.now(timezone.utc)).total_seconds()))
        return {**h, "seconds_remaining": remaining}
    return h


def get_user_portfolio(user_id: str) -> list[dict]:
    return [get_hold(h["hold_id"]) for h in _holds.values()
            if h["user_id"] == user_id and h["status"] == "COMPLETED"]


def get_user_active_holds(user_id: str) -> list[dict]:
    result = []
    for h in _holds.values():
        if h["user_id"] != user_id:
            continue
        result.append(get_hold(h["hold_id"]))
    return result


async def _auto_expire(hold_id: str, delay: int):
    await asyncio.sleep(delay)
    h = _holds.get(hold_id)
    if h and h["status"] == "HELD":
        for uid in h["unit_ids"]:
            _free_unit(uid)
        h.update({"status": "EXPIRED", "seconds_remaining": 0,
                   "message": "Hold expired. Stocks released back to market."})
        logger.warning("Stock hold expired", extra={"hold_id": hold_id})
