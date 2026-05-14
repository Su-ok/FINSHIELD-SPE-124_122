"""
FinShield - Pytest Configuration & Fixtures
Ensures test isolation by resetting in-memory state between tests.
"""

import sys
import os
import pytest

# Make sure the backend src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend/src"))


@pytest.fixture(autouse=True)
def reset_transaction_store():
    """
    Clears the in-memory transaction store before each test.
    This prevents tests from sharing state and causing order-dependent failures.
    """
    from routes.transactions import _transactions
    _transactions.clear()
    yield
    _transactions.clear()


@pytest.fixture(autouse=True)
def reset_fraud_velocity():
    """
    Resets the fraud detection velocity window before each test.
    Prevents velocity-breach false positives from accumulating across tests.
    """
    from services.fraud_detection import fraud_service
    fraud_service._recent.clear()
    yield
    fraud_service._recent.clear()
