"""
FinShield - Transaction Hold Service
Implements a 10-minute fund reservation pattern (like ticket seat locking).

Flow:
  1. POST /hold          → funds locked for 10 min, status = HELD
  2. POST /{id}/confirm  → payment done,  status = COMPLETED
  3. Timer fires         → no payment,    status = EXPIRED  (funds released)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from utils.logger import get_structured_logger

logger = get_structured_logger("finshield.hold_service")

HOLD_DURATION_SECONDS = 600  # 10 minutes

# In-memory store  {transaction_id: hold_dict}
# Replace with Redis in production (see README for Redis upgrade path)
_holds: dict[str, dict] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────────────────────

async def place_hold(
    transaction_id: str,
    sender_account: str,
    receiver_account: str,
    amount: float,
    currency: str,
    transaction_type: str,
    fraud_score: float,
) -> dict:
    """
    Lock funds for HOLD_DURATION_SECONDS seconds.
    Schedules an automatic expiry task so the hold self-releases
    if payment is never confirmed — exactly like ticket seat locking.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=HOLD_DURATION_SECONDS)

    hold = {
        "transaction_id":   transaction_id,
        "sender_account":   sender_account,
        "receiver_account": receiver_account,
        "amount":           amount,
        "currency":         currency,
        "transaction_type": transaction_type,
        "fraud_score":      fraud_score,
        "status":           "HELD",
        "created_at":       now.isoformat(),
        "expires_at":       expires_at.isoformat(),
        "message":          f"Funds held for {HOLD_DURATION_SECONDS // 60} minutes. Confirm payment before expiry.",
    }

    _holds[transaction_id] = hold

    logger.info(
        "Fund hold placed",
        extra={
            "transaction_id": transaction_id,
            "sender":         sender_account,
            "receiver":       receiver_account,
            "amount":         amount,
            "currency":       currency,
            "expires_at":     expires_at.isoformat(),
            "event":          "hold_placed",
        },
    )

    # Fire-and-forget expiry watcher — auto-releases hold after timeout
    asyncio.create_task(_expire_hold_after(transaction_id, HOLD_DURATION_SECONDS))

    return hold


def confirm_hold(transaction_id: str) -> dict | None:
    """
    Confirm payment for a HELD transaction → status becomes COMPLETED.
    Returns None if the hold doesn't exist or has already expired/been confirmed.
    """
    hold = _holds.get(transaction_id)
    if not hold or hold["status"] != "HELD":
        return None

    hold["status"]  = "COMPLETED"
    hold["message"] = "Payment confirmed. Funds transferred successfully."

    logger.info(
        "Fund hold confirmed",
        extra={
            "transaction_id": transaction_id,
            "amount":         hold["amount"],
            "event":          "hold_confirmed",
        },
    )
    return hold


def release_hold(transaction_id: str) -> dict | None:
    """
    Manually release a HELD transaction before expiry (e.g. user cancelled).
    Returns None if the hold doesn't exist or is not in HELD state.
    """
    hold = _holds.get(transaction_id)
    if not hold or hold["status"] != "HELD":
        return None

    hold["status"]  = "RELEASED"
    hold["message"] = "Hold manually released. Funds returned to sender."

    logger.info(
        "Fund hold released manually",
        extra={
            "transaction_id": transaction_id,
            "amount":         hold["amount"],
            "event":          "hold_released",
        },
    )
    return hold


def get_hold(transaction_id: str) -> dict | None:
    """Return the hold dict, enriched with live seconds_remaining."""
    hold = _holds.get(transaction_id)
    if not hold:
        return None

    # Compute remaining time only for active holds
    if hold["status"] == "HELD":
        expires_at = datetime.fromisoformat(hold["expires_at"])
        remaining  = (expires_at - datetime.now(timezone.utc)).total_seconds()
        hold = {**hold, "seconds_remaining": max(0, int(remaining))}
    else:
        hold = {**hold, "seconds_remaining": 0}

    return hold


def list_holds() -> list[dict]:
    """Return all holds (all statuses) enriched with seconds_remaining."""
    return [get_hold(txn_id) for txn_id in _holds]


# ─────────────────────────────────────────────────────────────────────────────
#  Internal expiry watcher
# ─────────────────────────────────────────────────────────────────────────────

async def _expire_hold_after(transaction_id: str, delay_seconds: int):
    """
    Waits delay_seconds then checks if the hold is still HELD.
    If yes → marks it EXPIRED (funds automatically released back to sender).
    This mirrors the ticket-booking pattern: seat unlocks after payment window.
    """
    await asyncio.sleep(delay_seconds)

    hold = _holds.get(transaction_id)
    if hold and hold["status"] == "HELD":
        hold["status"]  = "EXPIRED"
        hold["message"] = "Hold expired. Funds released back to sender account."

        logger.warning(
            "Fund hold expired — funds released",
            extra={
                "transaction_id": transaction_id,
                "amount":         hold["amount"],
                "sender":         hold["sender_account"],
                "event":          "hold_expired",
            },
        )
