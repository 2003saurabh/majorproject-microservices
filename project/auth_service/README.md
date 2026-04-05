# Users & Auth Service

FastAPI microservice handling **user registration, JWT auth, email verification, password reset, and passwordless OTP login**. Runs on port `8001`, shares the Postgres instance with the Items service using a dedicated `auth` schema.

---

## Features

| Feature | Endpoint(s) |
|---|---|
| Register | `POST /auth/register` |
| Login (password) | `POST /auth/login` |
| Token refresh | `POST /auth/refresh` |
| Token verify (inter-service) | `POST /auth/verify-token` |
| Email OTP verification | `POST /auth/otp/send-verification` · `POST /auth/otp/verify-email` |
| Forgot password | `POST /auth/otp/forgot-password` · `POST /auth/otp/reset-password` |
| Passwordless OTP login | `POST /auth/otp/send-login` · `POST /auth/otp/login` |
| Profile | `GET /users/me` · `PATCH /users/me` |
| Health | `GET /health/live` · `GET /health` · `GET /health/ready` |

---

## OTP flows at a glance

```
REGISTER FLOW
  POST /auth/register          → creates user (unverified), sends OTP email
  POST /auth/otp/verify-email  → validates OTP → returns tokens (user verified)

FORGOT PASSWORD FLOW
  POST /auth/otp/forgot-password  → sends reset OTP email
  POST /auth/otp/reset-password   → validates OTP + sets new password

PASSWORDLESS LOGIN FLOW
  POST /auth/otp/send-login  → sends magic login code
  POST /auth/otp/login       → validates code → returns tokens
```

---

## Setup

### 1. Configure email (Gmail App Password)

1. Enable 2-Step Verification on your Gmail account
2. Go to **Google Account → Security → App Passwords**
3. Create an App Password for "Mail"
4. Copy the generated 16-character code

```bash
cp .env.example .env
# Edit .env — fill in SMTP_USER, SMTP_PASSWORD, EMAIL_FROM
```

> **Never commit `.env` to version control.**

### 2. Run locally (with docker-compose)

```bash
# From the project root (where the updated docker-compose.yml lives)
docker-compose up --build

# Auth service: http://localhost:8001/docs
# Items service: http://localhost:8000/docs
```

### 3. Run auth service standalone

```bash
cd auth_service
pip install -r requirements.txt
cp .env.example .env  # fill in values
uvicorn auth_app.main:app --reload --port 8001
```

### 4. Run tests

```bash
cd auth_service
pip install pytest httpx
pytest tests/ -v
```

---

## How other services verify JWTs

Each request to the Orders / Items service should include:
```
Authorization: Bearer <access_token>
```

The receiving service can either:

**Option A — shared secret (lightweight):** Decode the JWT locally using the same `JWT_SECRET`. No network hop.

```python
from jose import jwt
payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
user_id = int(payload["sub"])
```

**Option B — verify-token endpoint (strict):** Call the Auth service:

```python
r = httpx.post("http://auth:8001/auth/verify-token", json={"refresh_token": token})
if r.json()["valid"]:
    user_id = r.json()["user_id"]
```

Option A is recommended for performance; Option B is useful when you need real-time revocation.

---

## Database schema

All tables live in the `auth` schema of the shared Postgres instance (`appdb`).

```
auth.users
  id, email, hashed_password, full_name, is_active, is_verified, is_superuser
  created_at, updated_at

auth.otp_codes
  id, user_id (FK), code, purpose (verify|reset|login)
  is_used, expires_at, created_at
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | Postgres host |
| `DB_NAME` | `appdb` | Database name |
| `DB_USER` | `postgres` | Postgres user |
| `DB_PASSWORD` | `postgres` | Postgres password |
| `JWT_SECRET` | _(change this)_ | Secret for signing JWTs |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `OTP_EXPIRE_MINUTES` | `10` | OTP validity window |
| `OTP_LENGTH` | `6` | OTP digit count |
| `SMTP_USER` | — | Gmail address |
| `SMTP_PASSWORD` | — | Gmail App Password (16 chars, no spaces) |
| `EMAIL_ENABLED` | `true` | Set `false` to skip emails in dev |
