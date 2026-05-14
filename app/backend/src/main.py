"""
FinShield - Secure Financial Transaction API + Stock Market
DevSecOps SDLC Pipeline | Finance Domain
"""
import os, uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from routes.transactions import router as tx_router
from routes.auth import router as auth_router
from routes.stocks import router as stocks_router
from utils.logger import get_structured_logger

logger = get_structured_logger("finshield.main")
DASHBOARD = Path(__file__).parent / "templates" / "dashboard.html"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FinShield API starting", extra={"event": "startup",
                "version": os.getenv("APP_VERSION", "1.0.0")})
    yield
    logger.info("FinShield API shutting down", extra={"event": "shutdown"})


app = FastAPI(
    title="FinShield API",
    description="Secure Financial Transaction Processing + Stock Market — DevSecOps Pipeline",
    version=os.getenv("APP_VERSION", "1.0.0"),
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_logger(request: Request, call_next):
    rid = str(uuid.uuid4())
    start = datetime.now(timezone.utc)
    response = await call_next(request)
    ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
    logger.info("HTTP request", extra={"request_id": rid, "method": request.method,
        "path": request.url.path, "status_code": response.status_code,
        "duration_ms": round(ms, 2),
        "client_ip": request.client.host if request.client else "unknown"})
    response.headers["X-Request-ID"] = rid
    return response


app.include_router(tx_router,     prefix="/api/v1/transactions", tags=["Transactions"])
app.include_router(auth_router,   prefix="/api/v1/auth",         tags=["Auth"])
app.include_router(stocks_router, prefix="/api/v1/stocks",       tags=["Stocks"])


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "finshield-api",
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=DASHBOARD.read_text(encoding="utf-8"))
