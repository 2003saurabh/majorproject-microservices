# Orders Service

FastAPI microservice for order management with **real-time WebSocket push notifications** on every status transition. Runs on port `8002`, shares Postgres with the `orders` schema.

---

## Features

| Feature | Details |
|---|---|
| Full order CRUD | Create, list, get, status-update, delete |
| Status lifecycle | `pending → confirmed → processing → shipped → delivered \| cancelled` |
| Status history | Immutable audit trail on every transition |
| Real-time WS | Push notifications to order owner + all superusers |
| JWT auth | Shared secret with Auth service — no extra network hop |
| Admin endpoints | `/admin/orders` and `/admin/ws/stats` for superusers |

---

## Status transition rules

```
pending    → confirmed | cancelled
confirmed  → processing | cancelled
processing → shipped | cancelled
shipped    → delivered
delivered  → (terminal)
cancelled  → (terminal)
```

Regular users can only **cancel** their own orders.  
Superusers can advance to any allowed next status.

---

## WebSocket

Connect: `ws://host:8002/ws/orders?token=<access_token>`

**Server → Client events:**
```json
{"event": "connected",       "user_id": 1, "message": "Listening..."}
{"event": "order_created",   "order_id": 5, "status": "pending", "total_price": "129.97"}
{"event": "status_changed",  "order_id": 5, "status": "confirmed", "note": "Payment ok"}
{"event": "order_cancelled", "order_id": 5, "status": "cancelled"}
{"event": "ping"}
```

**Client → Server:**
```json
{"event": "pong"}
```

- The server pings every 25s; client must respond with `pong` or the connection is cleaned up.
- Superusers receive all events across all users.
- Auto-reconnect is implemented in the frontend with a 5s backoff.

---

## Setup

```bash
# From project root (all services + DB)
docker-compose -f orders_service/docker-compose.full.yml up --build

# Orders service standalone
cd orders_service
pip install -r requirements.txt
cp .env.example .env
uvicorn orders_app.main:app --reload --port 8002
```

**Important:** `JWT_SECRET` must be the same value in both the Auth service and Orders service `.env` files.

---

## Run tests

```bash
cd orders_service
pip install pytest httpx
pytest tests/ -v
```

---

## API summary

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/orders` | User | Create order |
| `GET`  | `/orders` | User | List own orders (superuser sees all) |
| `GET`  | `/orders/{id}` | User | Get order (own only) |
| `PATCH`| `/orders/{id}/status` | User/Admin | Advance status |
| `DELETE`| `/orders/{id}` | User | Delete pending order |
| `GET`  | `/admin/orders` | Superuser | All orders |
| `GET`  | `/admin/ws/stats` | Superuser | WS connection stats |
| `WS`   | `/ws/orders?token=...` | User | Real-time stream |

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | Postgres host |
| `JWT_SECRET` | _(change this)_ | Must match Auth service |
| `ITEMS_SERVICE_URL` | `http://localhost:8000` | Items service base URL |
| `AUTH_SERVICE_URL`  | `http://localhost:8001` | Auth service base URL |
