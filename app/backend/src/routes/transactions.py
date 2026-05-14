"""
FinShield - Transaction Routes (original, clean)
POST   /api/v1/transactions/      → Create & complete instant transaction
GET    /api/v1/transactions/      → List all transactions
GET    /api/v1/transactions/{id}  → Get single transaction
DELETE /api/v1/transactions/{id}  → Delete transaction
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from models.transaction import TransactionCreate, TransactionResponse, TransactionListResponse
from services.fraud_detection import fraud_service, FRAUD_THRESHOLD
from utils.logger import get_structured_logger

router = APIRouter()
logger = get_structured_logger("finshield.transactions")

_transactions: dict[str, dict] = {}


@router.post("/", response_model=TransactionResponse, status_code=201)
async def create_transaction(payload: TransactionCreate):
    tx_id = f"TXN-{uuid.uuid4().hex[:12].upper()}"
    fraud_score = fraud_service.score(
        amount=payload.amount, sender=payload.sender_account,
        receiver=payload.receiver_account, tx_type=payload.transaction_type,
    )
    status = "FLAGGED" if fraud_score > FRAUD_THRESHOLD else "COMPLETED"
    tx = {
        "transaction_id": tx_id, "sender_account": payload.sender_account,
        "receiver_account": payload.receiver_account, "amount": payload.amount,
        "currency": payload.currency, "transaction_type": payload.transaction_type,
        "status": status, "fraud_score": fraud_score,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Transaction flagged for review." if fraud_score > FRAUD_THRESHOLD
                   else "Transaction completed successfully.",
    }
    _transactions[tx_id] = tx
    logger.info("Transaction created", extra={"transaction_id": tx_id, "amount": payload.amount,
        "status": status, "fraud_score": fraud_score})
    return TransactionResponse(**tx)


@router.get("/", response_model=TransactionListResponse)
async def list_transactions():
    txs = list(_transactions.values())
    return TransactionListResponse(transactions=[TransactionResponse(**t) for t in txs], total=len(txs))


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: str):
    tx = _transactions.get(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    return TransactionResponse(**tx)


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(transaction_id: str):
    if transaction_id not in _transactions:
        raise HTTPException(status_code=404, detail="Transaction not found")
    del _transactions[transaction_id]
    logger.info("Transaction deleted", extra={"transaction_id": transaction_id})
