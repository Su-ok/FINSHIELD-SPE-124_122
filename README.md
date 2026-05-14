# 🛡️ FinShield — DevSecOps SDLC Pipeline



---

## 🏗️ Architecture

```
GitHub Push
    │
    ▼
Jenkins (CI/CD)  ◄──── GitHub Hook Trigger (GITScm Polling)
    │
    ├── 1. Checkout code
    ├── 2. Pull secrets from HashiCorp Vault
    ├── 3. Run pytest automated tests
    ├── 4. Build Docker image
    ├── 5. Trivy security scan (DevSecOps)
    ├── 6. Push to Docker Hub
    ├── 7. Ansible deploy (roles: vault_setup, deploy)
    └── 8. kubectl rolling deploy → Kubernetes (HPA enabled)
                                          │
                          ┌───────────────┘
                          ▼
               FinShield FastAPI App (2–10 pods, HPA)
                          │
              ┌───────────┴──────────┐
              ▼                      ▼
         PostgreSQL            JSON Logs → Logstash → Elasticsearch → Kibana
              │
         HashiCorp Vault (DB creds, API keys, JWT secrets)
```

---

## 📁 Project Structure

```
finshield-devsecops/
├── app/
│   ├── backend/
│   │   ├── Dockerfile              # Multi-stage secure build
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py             # FastAPI app + modern dashboard UI
│   │       ├── models/
│   │       │   └── transaction.py  # Pydantic models
│   │       ├── routes/
│   │       │   └── transactions.py # CRUD transaction API
│   │       ├── services/
│   │       │   └── fraud_detection.py  # Multi-rule fraud engine
│   │       └── utils/
│   │           ├── logger.py       # ELK-compatible JSON logger
│   │           └── vault_client.py # Vault secret fetcher
│   └── tests/
│       └── test_transactions.py    # Pytest suite (6 test cases)
├── devops/
│   ├── ansible/
│   │   ├── inventory/
│   │   │   ├── hosts.yml
│   │   │   └── group_vars/all.yml
│   │   ├── playbooks/
│   │   │   └── deploy.yml          # Main playbook
│   │   └── roles/
│   │       ├── deploy/             # Docker pull + compose role
│   │       └── vault_setup/        # Vault secret bootstrap role
│   ├── docker-compose/
│   │   └── docker-compose.yml      # Full stack (App+Vault+PG+ELK+Jenkins)
│   ├── jenkins/
│   │   └── Jenkinsfile             # 8-stage pipeline
│   └── kubernetes/
│       ├── deployment.yaml         # Rolling update deployment
│       ├── service.yaml            # LoadBalancer + Ingress
│       └── hpa.yaml                # Horizontal Pod Autoscaler (2–10 pods)
├── monitoring/
│   └── elk/
│       └── logstash.conf           # Transaction log enrichment pipeline
└── scripts/
    ├── setup.sh                    # One-shot full setup
    └── init_vault.sh               # Interactive Vault bootstrapper
```

---

## 🚀 Quick Start (One Command)

```bash
# Clone and run everything
git clone <your-repo-url>
cd finshield-devsecops
bash scripts/setup.sh
```

---

## 🔧 Step-by-Step Commands

### 1. Build & Run (Docker Compose)

```bash
cd devops/docker-compose
docker compose up -d --build

# Check all services are up
docker compose ps
```

### 2. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| 🌐 App Dashboard | http://localhost:8000 | — |
| 📖 API Docs (Swagger) | http://localhost:8000/docs | — |
| 🔐 Vault UI | http://localhost:8200/ui | Token: `finshield-root-token` |
| ⚙️ Jenkins | http://localhost:8080 | Setup on first run |
| 📊 Kibana | http://localhost:5601 | — |
| 🔍 Elasticsearch | http://localhost:9200 | — |

### 3. Initialize Vault Secrets

```bash
# Automatic (uses defaults for local dev)
docker exec finshield-vault vault kv put secret/finshield/database \
  host=postgres port=5432 name=finshield user=finshield password=finshield_secret

docker exec finshield-vault vault kv put secret/finshield/api-keys \
  fraud_api_key=local-dev-fraud-key jwt_secret=local-dev-jwt-secret

# Interactive (prompts for Docker Hub creds)
bash scripts/init_vault.sh
```

### 4. Run Automated Tests

```bash
pip install pytest httpx fastapi pydantic python-dotenv
python -m pytest app/tests/ -v
```

### 5. Test the API manually

```bash
# Health check
curl http://localhost:8000/health

# Create a transaction
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -d '{"sender_account":"ACC-001","receiver_account":"ACC-002","amount":500,"transaction_type":"transfer"}'

# List transactions
curl http://localhost:8000/api/v1/transactions/

# Test fraud detection (high value = flagged)
curl -X POST http://localhost:8000/api/v1/transactions/ \
  -H "Content-Type: application/json" \
  -d '{"sender_account":"ACC-001","receiver_account":"ACC-002","amount":999999,"transaction_type":"withdrawal"}'
```

### 6. Ansible Deploy

```bash
cd devops/ansible
# Edit inventory/hosts.yml with your server IP first
ansible-playbook -i inventory/hosts.yml playbooks/deploy.yml \
  --extra-vars "docker_tag=latest"
```

### 7. Kubernetes Deploy

```bash
cd devops/kubernetes

# Apply all manifests
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f hpa.yaml

# Watch pods scale
kubectl get pods -n finshield -w

# Watch HPA scaling
kubectl get hpa -n finshield -w

# Check rollout
kubectl rollout status deployment/finshield-api -n finshield
```

### 8. Jenkins Setup

1. Open http://localhost:8080
2. Get initial password: `docker exec finshield-jenkins cat /var/jenkins_home/secrets/initialAdminPassword`
3. Install suggested plugins + **Git**, **Docker**, **Kubernetes CLI**, **Pipeline** plugins
4. Create credentials:
   - `vault-root-token` → Secret text: `finshield-root-token`
   - `dockerhub-credentials` → Username + Password (your Docker Hub)
   - `kubeconfig` → Secret file (your `~/.kube/config`)
5. Create Pipeline job → SCM: Git → Jenkinsfile path: `devops/jenkins/Jenkinsfile`
6. Enable **GitHub hook trigger for GITScm polling**
7. In GitHub repo → Settings → Webhooks → `http://<jenkins-ip>:8080/github-webhook/`

### 9. Kibana Dashboard Setup

1. Open http://localhost:5601
2. Go to **Stack Management → Index Patterns**
3. Create pattern: `finshield-*`
4. Set `@timestamp` as time field
5. Go to **Discover** → Filter by `finshield-transactions-*`
6. Create visualizations:
   - Bar chart: transactions by `transaction_type`
   - Gauge: average `fraud_score`
   - Line chart: transactions over time

### 10. Stop Everything

```bash
cd devops/docker-compose
docker compose down -v    # Remove volumes too
# or
docker compose down       # Keep data
```

---


---

## 🔐 Security Features (DevSecOps)

- **Vault**: All credentials (DB, API keys, JWT, Docker Hub) stored in HashiCorp Vault — never in env files or code
- **Non-root Docker**: App runs as `finshield` user in container
- **Multi-stage build**: Lean final image without build tools
- **Trivy scan**: Image vulnerability scanning in Jenkins pipeline
- **K8s Secrets**: Vault tokens injected via K8s Secrets (not env literals)
- **Live Patching**: Rolling update strategy with `maxUnavailable: 0` = zero downtime

---

*FinShield — Built for CSE 816 Final Project | Finance Domain DevSecOps*
