# Python Microservice — ECS EC2 + RDS

A production-ready Python microservice built with **FastAPI**, **SQLAlchemy**, and **PostgreSQL (RDS)**, deployed on **AWS ECS with EC2 launch type**. Comes pre-seeded with 50 dummy items.

---

## Project Structure

```
microservice/
├── app/
│   ├── main.py          # FastAPI app, routes, startup seeder
│   ├── database.py      # SQLAlchemy engine + session (RDS config)
│   ├── models.py        # ORM table definitions
│   ├── schemas.py       # Pydantic request/response models
│   ├── crud.py          # Database operations
│   └── seed.py          # 50 dummy items — auto-inserted on first startup
├── tests/
│   └── test_main.py     # Pytest test suite
├── deployment/
│   ├── ecs-task-definition.json   # ECS EC2 task definition template
│   └── deploy.sh                  # ECR push + ECS deploy script
├── Dockerfile           # Multi-stage, curl healthcheck for EC2
├── docker-compose.yml   # Local dev with Postgres
└── requirements.txt
```

---

## Local Development

```bash
# Start app + local Postgres (auto-seeds 50 items on first run)
docker-compose up --build

# Open API docs
open http://localhost:8000/docs

# Check seeded data
curl http://localhost:8000/items | python3 -m json.tool
```

---

## Health Endpoints

| Endpoint | Purpose | Use for |
|---|---|---|
| `GET /health/live` | Is the container alive? | ECS EC2 container `HEALTHCHECK` |
| `GET /health` | Uptime + version | General monitoring / CloudWatch |
| `GET /health/ready` | Can the app reach RDS? | ALB target group health check |

---

## Seed Data

On **first startup**, if the `items` table is empty, `seed.py` automatically inserts **50 dummy product entries** (tech hardware items with names, descriptions, and active status). Subsequent restarts skip seeding — it's idempotent.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root |
| `POST` | `/items` | Create item |
| `GET` | `/items` | List items (default limit 100) |
| `GET` | `/items/{id}` | Get item by ID |
| `PUT` | `/items/{id}` | Update item |
| `DELETE` | `/items/{id}` | Delete item |

Interactive docs: `http://localhost:8000/docs`

---

## Run Tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## AWS Deployment (ECS EC2)

### Prerequisites
- AWS CLI configured
- EC2-based ECS cluster running (with ECS-optimised AMI + ECS agent)
- ECR repository created
- RDS PostgreSQL in same VPC as EC2 instances
- DB credentials in **AWS Secrets Manager**
- IAM roles: `ecsTaskExecutionRole` (with SecretsManager read) + `ecsTaskRole`

### Steps

**1. Create ECR repository**
```bash
aws ecr create-repository --repository-name python-microservice --region us-east-1
```

**2. Edit deployment files** — open these and replace placeholder values:
- `deployment/ecs-task-definition.json`: `YOUR_ACCOUNT_ID`, `YOUR_REGION`, Secrets Manager ARNs
- `deployment/deploy.sh`: `AWS_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE`

**3. Deploy**
```bash
chmod +x deployment/deploy.sh
./deployment/deploy.sh
```

The script: builds image → pushes to ECR → registers new task definition → force-deploys the ECS service.

---

## Key Differences vs Fargate

| | EC2 | Fargate |
|---|---|---|
| `networkMode` | `bridge` | `awsvpc` |
| `hostPort` | `0` (dynamic) | same as containerPort |
| Instance management | You manage EC2s | AWS manages |
| Cost | Lower at scale | Higher but zero-ops |

---

## Environment Variables

| Variable | Description | Source |
|---|---|---|
| `DB_HOST` | RDS endpoint | Secrets Manager |
| `DB_PORT` | Port (default `5432`) | Task env |
| `DB_NAME` | Database name | Task env |
| `DB_USER` | DB username | Secrets Manager |
| `DB_PASSWORD` | DB password | Secrets Manager |
