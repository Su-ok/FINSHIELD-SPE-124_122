"""
FinShield - Automated Test Suite
Run with: pytest app/tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)



def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_create_transaction_normal():
    payload = {
        "sender_account": "ACC-TEST001",
        "receiver_account": "ACC-TEST002",
        "amount": 150.00,
        "transaction_type": "transfer",
    }
    resp = client.post("/api/v1/transactions/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["transaction_id"].startswith("TXN-")
    assert data["status"] in ("COMPLETED", "FLAGGED")
    assert 0.0 <= data["fraud_score"] <= 1.0


def test_create_transaction_high_value():
    payload = {
        "sender_account": "ACC-WHALE01",
        "receiver_account": "ACC-WHALE02",
        "amount": 999_999.00,
        "transaction_type": "transfer",
    }
    resp = client.post("/api/v1/transactions/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    # High-value should trigger fraud
    assert data["fraud_score"] > 0.3


def test_create_transaction_loopback():
    payload = {
        "sender_account": "ACC-LOOP01",
        "receiver_account": "ACC-LOOP01",
        "amount": 500.00,
        "transaction_type": "transfer",
    }
    resp = client.post("/api/v1/transactions/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["fraud_score"] > 0.4


def test_list_transactions():
    # Create a transaction first
    client.post("/api/v1/transactions/", json={
        "sender_account": "ACC-A", "receiver_account": "ACC-B",
        "amount": 100, "transaction_type": "payment"
    })
    resp = client.get("/api/v1/transactions/")
    assert resp.status_code == 200
    data = resp.json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)
    assert data["total"] >= 1


def test_get_transaction_not_found():
    resp = client.get("/api/v1/transactions/TXN-DOESNOTEXIST")
    assert resp.status_code == 404


def test_invalid_amount():
    payload = {
        "sender_account": "ACC-X",
        "receiver_account": "ACC-Y",
        "amount": -50,
        "transaction_type": "transfer",
    }
    resp = client.post("/api/v1/transactions/", json=payload)
    assert resp.status_code == 422  # Validation error
