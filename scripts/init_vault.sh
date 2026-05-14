#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  FinShield — Vault Initialization Script
#  Bootstraps all secrets in HashiCorp Vault for local development
#  Usage: bash scripts/init_vault.sh
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-finshield-root-token}"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[✓]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   FinShield — Vault Secret Bootstrapper          ║${NC}"
echo -e "${CYAN}║   DevSecOps Finance Domain — CSE 816             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

# ── Check Vault is reachable ──────────────────────────────────────
log "Connecting to Vault at ${VAULT_ADDR}..."
for i in {1..10}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${VAULT_ADDR}/v1/sys/health" || true)
  if [[ "$STATUS" == "200" || "$STATUS" == "429" ]]; then
    ok "Vault is reachable (HTTP $STATUS)"
    break
  fi
  warn "Vault not ready yet (attempt $i/10)... retrying in 3s"
  sleep 3
  if [[ $i -eq 10 ]]; then
    error "Cannot reach Vault at ${VAULT_ADDR}. Is it running? Run: docker compose up -d vault"
  fi
done

export VAULT_ADDR VAULT_TOKEN

# ── Enable KV v2 secrets engine ───────────────────────────────────
log "Enabling KV v2 secrets engine..."
vault secrets enable -version=2 secret 2>/dev/null && ok "KV v2 enabled" || warn "KV v2 already enabled (OK)"

# ── Store Database Credentials ────────────────────────────────────
log "Writing database credentials → secret/finshield/database"
vault kv put secret/finshield/database \
  host="postgres" \
  port="5432" \
  name="finshield" \
  user="finshield" \
  password="finshield_secret_$(openssl rand -hex 8)"
ok "Database credentials stored"

# ── Store API Keys ────────────────────────────────────────────────
log "Writing API keys → secret/finshield/api-keys"
vault kv put secret/finshield/api-keys \
  fraud_api_key="fs-fraud-$(openssl rand -hex 12)" \
  jwt_secret="finshield-jwt-$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)"
ok "API keys stored"

# ── Store Docker Hub Credentials ──────────────────────────────────
log "Writing Docker Hub credentials → secret/finshield/dockerhub"
read -rp "Enter your Docker Hub username: " DOCKERHUB_USER
read -rsp "Enter your Docker Hub password/token: " DOCKERHUB_PASS
echo ""
vault kv put secret/finshield/dockerhub \
  username="${DOCKERHUB_USER}" \
  password="${DOCKERHUB_PASS}"
ok "Docker Hub credentials stored"

# ── Store Jenkins Webhook Secret ──────────────────────────────────
log "Writing Jenkins webhook → secret/finshield/jenkins"
vault kv put secret/finshield/jenkins \
  webhook_secret="jenkins-$(openssl rand -hex 16)"
ok "Jenkins webhook secret stored"

# ── Verify all secrets ────────────────────────────────────────────
echo ""
log "Verifying stored secrets..."
vault kv get secret/finshield/database  | grep -E "host|port|name|user" && ok "DB creds ✓"
vault kv get secret/finshield/api-keys  | grep -E "fraud_api_key|jwt" && ok "API keys ✓"
vault kv get secret/finshield/dockerhub | grep username && ok "DockerHub ✓"
vault kv get secret/finshield/jenkins   | grep webhook && ok "Jenkins ✓"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅  Vault Initialization Complete!              ║${NC}"
echo -e "${GREEN}║                                                  ║${NC}"
echo -e "${GREEN}║  Vault UI: ${VAULT_ADDR}/ui                     ║${NC}"
echo -e "${GREEN}║  Token:    ${VAULT_TOKEN}                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
