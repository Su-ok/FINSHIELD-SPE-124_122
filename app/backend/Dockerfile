# FinShield — Backend Dockerfile
# Multi-stage build for lean production image

# ─── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="FinShield DevSecOps Team"
LABEL version="1.0.0"
LABEL description="Secure Financial Transaction API"

# Non-root user for security
RUN addgroup --system finshield && adduser --system --ingroup finshield finshield

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src/ .

RUN chown -R finshield:finshield /app

USER finshield

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
