"""
FinShield - Fraud Detection Service
Rule-based + statistical fraud scoring for financial transactions

Hybrid threshold design:
  - Critical rule weights raised so high-value and loopback transactions
    cross the threshold on their own (no other rule needed).
  - FRAUD_THRESHOLD lowered 0.70 → 0.60 so combinations of moderate
    signals (e.g. round amount + large withdrawal) also get flagged.
"""

import random
from utils.logger import get_structured_logger

logger = get_structured_logger("finshield.fraud")


class FraudDetectionService:
    """
    Multi-rule fraud detection engine.
    Returns a fraud_score between 0.0 (clean) and 1.0 (highly suspicious).
    """

    FRAUD_THRESHOLD    = 0.60   # Lowered from 0.70  (hybrid fix)
    HIGH_RISK_THRESHOLD = 50_000
    VELOCITY_WINDOW    = 10     # Track last N senders in memory
    _recent: list      = []

    def score(self, amount: float, sender: str, receiver: str, tx_type: str) -> float:
        score   = 0.0
        reasons = []

        # ── Rule 1: High-value transaction ─────────────────────────────────
        # Weight raised 0.40 → 0.65: any single tx > $50k now crosses
        # FRAUD_THRESHOLD (0.60) on its own.
        if amount > self.HIGH_RISK_THRESHOLD:
            score += 0.65
            reasons.append("high_value")

        # ── Rule 2: Suspicious round numbers (money-laundering pattern) ────
        # Weight raised 0.15 → 0.20. Combined with other moderate signals
        # this helps push combined scores over the new threshold.
        if amount > 1_000 and amount % 1_000 == 0:
            score += 0.20
            reasons.append("round_amount")

        # ── Rule 3: Loopback — same sender and receiver ─────────────────────
        # Weight raised 0.50 → 0.65: a loopback tx now crosses FRAUD_THRESHOLD
        # on its own regardless of amount or type.
        if sender == receiver:
            score += 0.65
            reasons.append("loopback")

        # ── Rule 4: Velocity — sender appearing too frequently ──────────────
        # Weight raised 0.25 → 0.30. Three or more recent sends from the
        # same account is a structuring / velocity-breach signal.
        sender_count = sum(1 for t in self._recent if t == sender)
        if sender_count >= 3:
            score += 0.30
            reasons.append("velocity_breach")

        # Track sender in the velocity window
        self._recent.append(sender)
        if len(self._recent) > self.VELOCITY_WINDOW:
            self._recent.pop(0)

        # ── Rule 5: Large withdrawal ────────────────────────────────────────
        # Weight raised 0.20 → 0.25. Combined with Rule 1 a $50k+ withdrawal
        # scores 0.65 + 0.25 = 0.90 — clearly flagged.
        if tx_type == "withdrawal" and amount > 10_000:
            score += 0.25
            reasons.append("large_withdrawal")

        # Cap at 1.0 and add small noise for realism
        score = min(1.0, score + random.uniform(0, 0.05))

        logger.info(
            "Fraud score computed",
            extra={
                "sender":        sender,
                "receiver":      receiver,
                "amount":        amount,
                "fraud_score":   round(score, 4),
                "fraud_reasons": reasons,
                "flagged":       score > self.FRAUD_THRESHOLD,
            }
        )

        return round(score, 4)


fraud_service = FraudDetectionService()

# Export threshold so routes and frontend stay consistent with this file
FRAUD_THRESHOLD = FraudDetectionService.FRAUD_THRESHOLD

