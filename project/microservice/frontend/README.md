# Frontend — S3 Static Website

A single-page dashboard for the Python microservice. Zero build step — pure HTML/CSS/JS, host directly on S3.

## Features
- **Items table** — view all 50 seeded items with search, filter by status, pagination
- **Full CRUD** — create, edit, delete items via modal forms
- **Health page** — live checks against `/health/live`, `/health`, `/health/ready`
- **Sidebar status dots** — auto-polls API + DB health every 30 seconds
- **Configurable API URL** — set your ECS EC2 ALB endpoint in the UI, saved to localStorage

## Deploy to S3

### 1. Edit the deploy script
Open `deploy-frontend.sh` and set:
```bash
BUCKET_NAME="your-unique-bucket-name"
AWS_REGION="us-east-1"
```

### 2. Run it
```bash
chmod +x frontend/deploy-frontend.sh
./frontend/deploy-frontend.sh
```

### 3. Open the URL printed at the end
```
http://your-bucket-name.s3-website-us-east-1.amazonaws.com
```

### 4. Set your API URL
In the dashboard config bar, paste your ECS service URL:
```
http://your-alb-dns-name.us-east-1.elb.amazonaws.com
```
or your EC2 public IP:
```
http://1.2.3.4:8000
```

## CORS — Required on the API

The browser will call your API from the S3 domain, so you must enable CORS in FastAPI. Add this to `app/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://your-bucket.s3-website-us-east-1.amazonaws.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For development, use `allow_origins=["*"]`.

## Local preview

Just open the file in your browser — no server needed:
```bash
open frontend/index.html
```
