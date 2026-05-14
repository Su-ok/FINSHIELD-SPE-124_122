#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
#  FinShield — Kubernetes Deploy Script
#  Builds, tags, and applies K8s manifests with correct image tag.
#
#  Usage:
#    bash scripts/k8s-deploy.sh <dockerhub-user> [image-tag]
#
#  Examples:
#    bash scripts/k8s-deploy.sh myuser            # uses 'latest' tag
#    bash scripts/k8s-deploy.sh myuser 42         # uses build tag '42'
#    DOCKERHUB_USER=myuser bash scripts/k8s-deploy.sh
# ══════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CYAN='\033[0;36m'; GREEN='\033[0;32m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${CYAN}►${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── Resolve args ──────────────────────────────────────────────────
DOCKERHUB_USER="${1:-${DOCKERHUB_USER:-}}"
IMAGE_TAG="${2:-${IMAGE_TAG:-latest}}"

if [[ -z "$DOCKERHUB_USER" ]]; then
  error "Usage: $0 <dockerhub-user> [image-tag]  OR set DOCKERHUB_USER env var"
fi

DOCKER_IMAGE="${DOCKERHUB_USER}/finshield-api"
K8S_DIR="$PROJECT_ROOT/devops/kubernetes"
TMP_DIR=$(mktemp -d)

echo ""
log "FinShield Kubernetes Deploy"
log "  Image : ${DOCKER_IMAGE}:${IMAGE_TAG}"
log "  K8s manifests: $K8S_DIR"
echo ""

# ── Step 1: Build Docker image ────────────────────────────────────
log "Building Docker image..."
docker build \
  --build-arg APP_VERSION="${IMAGE_TAG}" \
  -t "${DOCKER_IMAGE}:${IMAGE_TAG}" \
  -t "${DOCKER_IMAGE}:latest" \
  "$PROJECT_ROOT/app/backend/"
ok "Image built: ${DOCKER_IMAGE}:${IMAGE_TAG}"

# ── Step 2: Push to Docker Hub (optional) ─────────────────────────
if [[ "${PUSH:-false}" == "true" ]]; then
  log "Pushing to Docker Hub..."
  docker push "${DOCKER_IMAGE}:${IMAGE_TAG}"
  docker push "${DOCKER_IMAGE}:latest"
  ok "Pushed to Docker Hub"
else
  log "Skipping push (set PUSH=true to push to Docker Hub)"
  log "For minikube: loading image directly into cluster..."
  minikube image load "${DOCKER_IMAGE}:${IMAGE_TAG}" 2>/dev/null || true
fi

# ── Step 3: Substitute placeholders in manifests ─────────────────
log "Substituting image tag in manifests..."
cp "$K8S_DIR/deployment.yaml" "$TMP_DIR/deployment.yaml"
cp "$K8S_DIR/service.yaml"    "$TMP_DIR/service.yaml"
cp "$K8S_DIR/hpa.yaml"        "$TMP_DIR/hpa.yaml"

sed -i \
  -e "s|YOUR_DOCKERHUB_USER|${DOCKERHUB_USER}|g" \
  -e "s|IMAGE_TAG|${IMAGE_TAG}|g" \
  "$TMP_DIR/deployment.yaml"

ok "Manifests rendered to: $TMP_DIR"

# ── Step 4: Apply manifests ───────────────────────────────────────
log "Applying Kubernetes manifests..."
kubectl apply -f "$TMP_DIR/deployment.yaml"
kubectl apply -f "$TMP_DIR/service.yaml"
kubectl apply -f "$TMP_DIR/hpa.yaml"
ok "Manifests applied"

# ── Step 5: Wait for rollout ──────────────────────────────────────
log "Waiting for rollout to complete..."
kubectl rollout status deployment/finshield-api \
  --namespace finshield \
  --timeout=120s
ok "Rollout complete!"

# ── Step 6: Show status ───────────────────────────────────────────
echo ""
log "Pod status:"
kubectl get pods -n finshield -l app=finshield-api
echo ""
log "HPA status:"
kubectl get hpa -n finshield
echo ""
log "Service:"
kubectl get svc -n finshield
echo ""

ok "FinShield is live on Kubernetes! Build tag: ${IMAGE_TAG}"
echo ""
echo "  Access via:  kubectl port-forward svc/finshield-api-service 8000:80 -n finshield"
echo "  Then open:   http://localhost:8000"
echo ""

# Cleanup temp dir
rm -rf "$TMP_DIR"
