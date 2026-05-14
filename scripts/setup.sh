#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  FinShield — One-Shot Full Stack Setup
#  Run from ANYWHERE:  bash scripts/setup.sh
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

# Always anchor to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
echo "Project root: $PROJECT_ROOT"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'
YELLOW='\033[1;33m'; NC='\033[0m'
log()   { echo -e "${CYAN}►${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC} $*"; exit 1; }
hr()    { echo -e "${CYAN}─────────────────────────────────────────────${NC}"; }

echo ""
echo -e "${CYAN}"
cat << 'BANNER'
 ███████╗██╗███╗   ██╗███████╗██╗  ██╗██╗███████╗██╗     ██████╗
 ██╔════╝██║████╗  ██║██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗
 █████╗  ██║██╔██╗ ██║███████╗███████║██║█████╗  ██║     ██║  ██║
 ██╔══╝  ██║██║╚██╗██║╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║
 ██║     ██║██║ ╚████║███████║██║  ██║██║███████╗███████╗██████╔╝
 ╚═╝     ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝
 DevSecOps Pipeline — CSE 816 Finance Domain Project
BANNER
echo -e "${NC}"

hr
log "Step 1/6 — Checking prerequisites..."
command -v docker   &>/dev/null && ok "Docker found"     || error "Docker not installed. Visit https://docs.docker.com/get-docker/"
command -v git      &>/dev/null && ok "Git found"        || error "Git not installed"
command -v python3  &>/dev/null && ok "Python3 found"    || error "Python3 not installed"
command -v curl     &>/dev/null && ok "curl found"       || warn "curl not found (optional)"

hr
log "Step 2/6 — Building Docker image..."
# $PROJECT_ROOT is set at top — always correct regardless of where you run this
docker build -t finshield-api:latest "$PROJECT_ROOT/app/backend/" \
  && ok "Image built: finshield-api:latest"

hr
log "Step 3/6 — Starting full stack (Vault + Postgres + ELK + Jenkins + API)..."
# docker-compose.yml is at project root — use -f with absolute path
docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d
ok "All containers started"

hr
log "Step 4/6 — Waiting for services to become healthy..."
echo "   (ELK takes ~60s on first run — please wait)"
sleep 20

for i in {1..15}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/health" 2>/dev/null || echo "000")
  if [[ "$STATUS" == "200" ]]; then
    ok "FinShield API is up"
    break
  fi
  printf "   waiting for API... attempt %d/15\r" "$i"
  sleep 5
done

for i in {1..15}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8200/v1/sys/health" 2>/dev/null || echo "000")
  if [[ "$STATUS" =~ ^(200|429|472)$ ]]; then
    ok "Vault is up"
    break
  fi
  sleep 3
done

hr
log "Step 5/6 — Initializing Vault secrets..."
sleep 3
docker exec finshield-vault vault kv put secret/finshield/database \
  host=postgres port=5432 name=finshield user=finshield password=finshield_secret 2>/dev/null \
  && ok "DB credentials stored in Vault" \
  || warn "vault-init container may have already done this (OK)"

docker exec finshield-vault vault kv put secret/finshield/api-keys \
  fraud_api_key=local-dev-fraud-key jwt_secret=local-dev-jwt-secret 2>/dev/null \
  && ok "API keys stored in Vault" || warn "Already present (OK)"

hr
log "Step 6/6 — Running automated test suite..."
if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
fi
"$PROJECT_ROOT/.venv/bin/pip" install -q \
  pytest httpx fastapi pydantic python-dotenv uvicorn hvac pytest-asyncio 2>/dev/null
"$PROJECT_ROOT/.venv/bin/python" -m pytest "$PROJECT_ROOT/app/tests/" -v --tb=short \
  && ok "All tests passed ✅"

echo ""
hr
echo -e "${GREEN}"
cat << 'SUCCESS'
  ╔═══════════════════════════════════════════════════════════════╗
  ║   🎉  FinShield is LIVE!                                      ║
  ╠═══════════════════════════════════════════════════════════════╣
  ║  🌐 App Dashboard   →   http://localhost:8000                 ║
  ║  📖 API Docs        →   http://localhost:8000/docs            ║
  ║  🔐 Vault UI        →   http://localhost:8200/ui              ║
  ║     Vault Token     →   finshield-root-token                  ║
  ║  ⚙️  Jenkins         →   http://localhost:9090                 ║
  ║  📊 Kibana          →   http://localhost:5601                  ║
  ║  🔍 Elasticsearch   →   http://localhost:9200                  ║
  ╚═══════════════════════════════════════════════════════════════╝
SUCCESS
echo -e "${NC}"
echo "Stop everything:  docker compose -f $PROJECT_ROOT/docker-compose.yml down"
echo ""
