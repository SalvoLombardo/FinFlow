# FinFlow

Personal financial planner with AI — event-driven architecture on AWS.

## Architecture

```
WRITE PATH                          SCHEDULED PATH
FastAPI Lambda                      Celery Beat (EC2)
      │                                   │
SNS Topic (finflow-events)          Celery Workers
      ├─► SQS projections → Lambda projection-consumer
      ├─► SQS ai-analysis → Lambda ai-consumer
      └─► SQS notifications → Lambda notification-consumer

AUDIT LOG (separate)
Kafka Topic finflow.audit → consumer → S3 jsonl (cold storage)
```

## Stack

| Layer | Technology |
|---|---|
| Backend API | Python + FastAPI → AWS Lambda via API Gateway |
| Frontend | React + Vite + Tailwind CSS → S3 + CloudFront |
| Database | PostgreSQL on AWS RDS (db.t3.micro) |
| Messaging | SNS fan-out → 3 SQS queues → 3 Lambda consumers |
| Audit log | Kafka on EC2 t2.micro → S3 |
| Scheduled tasks | Celery + Redis on same EC2 |
| AI layer | Dual-mode: local Ollama or user-supplied API key |
| IaC | Terraform |
| CI/CD | GitHub Actions |

## Local development

### Prerequisites

- Docker + Docker Compose
- Python 3.12+
- `cp .env.example .env` and fill in the values

### Generate secrets

```bash
# SECRET_KEY
openssl rand -hex 32

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Start backend + database

```bash
docker compose up
```

Backend available at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

### Run database migrations

```bash
cd backend
alembic upgrade head
```

### Start workers (Celery + Kafka)

```bash
docker compose -f docker-compose.workers.yml up
```

### Run tests

```bash
cd backend
pip install -r requirements.txt
pytest --cov=app tests/
```

## API endpoints

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/me

GET    /api/v1/weeks
POST   /api/v1/weeks
GET    /api/v1/weeks/{week_id}
PUT    /api/v1/weeks/{week_id}

GET    /api/v1/transactions
POST   /api/v1/transactions
PUT    /api/v1/transactions/{id}
DELETE /api/v1/transactions/{id}

GET    /api/v1/goals
POST   /api/v1/goals
PUT    /api/v1/goals/{id}

GET    /api/v1/dashboard/summary

GET    /health
```

## Event routing — SNS filter policies

Each SQS queue subscribes to `finflow-events` with a filter policy on the `event_type` message attribute. Only matching event types are delivered to each queue. These policies are applied by Terraform in Phase 6; the reference file is [`infrastructure/sns_filter_policies.json`](infrastructure/sns_filter_policies.json).

| Queue | Triggered by |
|---|---|
| `projections-queue` | `budget.updated`, `week.closed` |
| `ai-analysis-queue` | `ai.analysis.requested`, `budget.updated` |
| `notifications-queue` | `goal.progress` |

**Events emitted by the API:**

| Endpoint | Event published |
|---|---|
| `POST /transactions` | `budget.updated` |
| `PUT /transactions/{id}` | `budget.updated` |
| `PUT /weeks/{id}` (with `closing_balance`) | `week.closed` |

In local mode (`AWS_SNS_TOPIC_ARN` empty) every write logs the event as structured JSON (`SNS_LOCAL event_type=...`) without contacting AWS.

## Architecture decisions

**Celery on EC2 vs EventBridge Scheduler:** Celery workers operate on all users in batch, access the DB directly, and can run for several minutes. Lambda has a 15-minute timeout and cold start. A persistent worker is better suited for batch processing with granular retries. The EC2 `t2.micro` is Free Tier eligible.

**Kafka for audit log:** Append-only topic by design — past events cannot be modified. The consumer writes to S3 in batches, reducing costs. In real fintech systems this pattern is standard for compliance.

**VPC Endpoints instead of NAT Gateway:** NAT Gateway costs ~$32/month. VPC Endpoints for SQS, SNS, SSM, and S3 are free and allow Lambda to reach AWS services from a private subnet.

**SSM Parameter Store instead of Secrets Manager:** Secrets Manager charges $0.40/secret/month. SSM SecureString with the default KMS key is free.

**RDS GP2 storage:** GP3 is not Free Tier eligible. GP2 20GB on db.t3.micro is Free Tier for 12 months.

## Cost estimate

| Service | Year 1 | Year 2+ |
|---|---|---|
| RDS db.t3.micro | €0 | ~€14/month |
| EC2 t2.micro | €0 | ~€8/month |
| Lambda (all) | €0 | €0 |
| SQS + SNS | €0 | €0 |
| S3 + CloudFront | €0 | <€1/month |
| **Total** | **€0** | **~€23/month** |

Post-Free Tier strategy: shut down RDS at night (−60% hours → ~€6) or migrate to Supabase free tier.

## Phase status

| # | Phase | Status |
|---|---|---|
| 1 | Scaffolding, data models, local Docker backend | Completed ✓ |
| 2 | Async layer: SNS fan-out + 3 Lambda consumers | Completed ✓ |
| 3 | Kafka audit log + Celery scheduled tasks | Not started |
| 4 | React frontend | Not started |
| 5 | AI layer (dual-mode) | Not started |
| 6 | Infrastructure as Code with Terraform | Not started |
| 7 | CI/CD with GitHub Actions | Not started |
