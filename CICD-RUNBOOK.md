# CI/CD Pipeline Runbook

This document explains the complete CI/CD (Continuous Integration / Continuous Deployment) pipeline for the Majorproject Microservices application. It is written for anyone — even if you have zero knowledge of CI/CD.

---

## What is CI/CD?

**CI (Continuous Integration)** means every time a developer pushes code, it is automatically compiled, tested, and checked for issues. If anything fails, the team knows immediately.

**CD (Continuous Deployment)** means once the code passes all checks, it is automatically deployed to the server so users can access the latest version.

Think of it like a factory assembly line:
- Raw code goes in one end
- It gets checked, tested, scanned, and packaged
- A working application comes out the other end — deployed and running

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CI PIPELINE (dev branch)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   compile ──→ lint ──→ test ──┐                                             │
│         ↘                     ├──→ trivy ──→ sonarqube ──→ docker build     │
│          gitleaks ───────────┘                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CD PIPELINE (main branch or manual)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Deploy to EC2 via AWS SSM (pull Docker images + docker compose up)        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## CI Pipeline — Job by Job

### 1. Compile (`compile`)

**What it does:** Checks that all Python files can be compiled without syntax errors.

**Why:** If a developer accidentally writes invalid Python (missing colon, wrong indentation, typo in keyword), this catches it immediately — before wasting time on later stages.

**Command:**
```bash
python -m compileall -f .
```
This compiles every `.py` file into bytecode. If any file has a syntax error, the build fails.

---

### 2. Lint (`lint`)

**What it does:** Checks code style and catches common programming mistakes.

**Why:** Linting enforces consistent code quality across the team. It catches bugs like:
- Using an undefined variable
- Importing a module that doesn't exist
- Overly complex functions that are hard to maintain

**Tool used:** [Flake8](https://flake8.pycqa.org/)

**What Flake8 checks:**
| Check | Meaning |
|-------|---------|
| E9 | Runtime errors (syntax errors, IO errors) |
| F63 | Invalid `assert` statements |
| F7 | Syntax issues in statements |
| F82 | Undefined names (using variables that don't exist) |

**Runs after:** `compile` passes

---

### 3. Test (`test`)

**What it does:** Runs all automated unit tests to verify the application works correctly.

**Why:** Tests catch bugs before they reach production. If a developer changes the login logic and accidentally breaks it, the tests will fail and block the deployment.

**Tool used:** [Pytest](https://pytest.org/)

**What is tested:**
- All API endpoints (Items, Auth, Orders services)
- Authentication flows (register, login, token refresh, OTP)
- Order lifecycle (create, status transitions, cancellation)
- Permission checks (users can't see other users' data)
- Health endpoints

**Command:**
```bash
pytest project/tests -v
```

**Runs after:** `lint` passes

---

### 4. Gitleaks (`gitleaks`)

**What it does:** Scans the entire git history for accidentally committed secrets (passwords, API keys, tokens).

**Why:** Developers sometimes accidentally commit secrets like:
- Database passwords
- JWT secret keys
- API tokens
- AWS credentials

Even if you delete the secret in a later commit, it remains in git history forever. Gitleaks finds these and blocks the pipeline.

**Tool used:** [Gitleaks](https://github.com/gitleaks/gitleaks)

**Command:**
```bash
gitleaks detect --source . --verbose --redact --exit-code 1
```

| Flag | Meaning |
|------|---------|
| `--source .` | Scan this repository |
| `--verbose` | Show details of findings |
| `--redact` | Hide the actual secret values in logs |
| `--exit-code 1` | Fail the pipeline if secrets are found |

**Allowlisting known findings:** If Gitleaks flags old/dummy secrets that are safe, add their fingerprints to `.gitleaksignore`.

**Runs after:** `compile` passes (in parallel with `lint`)

---

### 5. Trivy (`trivy`)

**What it does:** Scans all project dependencies for known security vulnerabilities (CVEs).

**Why:** Your application depends on third-party libraries (FastAPI, SQLAlchemy, etc.). These libraries sometimes have security bugs discovered after release. Trivy checks if any of your dependencies have known vulnerabilities with published fixes.

**Example finding:**
```
python-jose 3.3.0 → CVE-2024-33663 (CRITICAL)
Fix: upgrade to 3.4.0
```

**Tool used:** [Trivy by Aqua Security](https://trivy.dev/)

**Command:**
```bash
trivy fs . --severity HIGH,CRITICAL --exit-code 1
```

| Flag | Meaning |
|------|---------|
| `fs .` | Filesystem scan (scans requirements.txt files) |
| `--severity HIGH,CRITICAL` | Only fail on serious vulnerabilities |
| `--exit-code 1` | Fail the pipeline if vulnerabilities found |

**How to fix findings:** Update the vulnerable package version in the relevant `requirements.txt` file.

**Runs after:** Both `test` and `gitleaks` pass

---

### 6. SonarQube (`sonarqube`)

**What it does:** Performs deep static code analysis — finds code smells, bugs, security hotspots, and measures code quality metrics.

**Why:** SonarQube goes beyond basic linting. It:
- Detects potential bugs (null dereferences, resource leaks)
- Identifies security hotspots (hardcoded credentials, SQL injection risks)
- Measures code duplication
- Tracks technical debt
- Provides a quality gate (pass/fail based on metrics)

**Tool used:** [SonarQube](https://www.sonarsource.com/products/sonarqube/) (self-hosted on our server)

**Configuration:** `sonar-project.properties` in the repo root defines what to scan.

**Dashboard:** After the scan, results are visible at the SonarQube server URL where you can browse issues, view metrics, and track quality over time.

**Runs after:** `trivy` passes

---

### 7. Docker Build & Push (`docker`)

**What it does:** Builds Docker images for all 3 microservices and pushes them to Docker Hub.

**Why:** Docker packages the application with all its dependencies into a portable image. This image is the same whether it runs on your laptop, a test server, or production — no "works on my machine" problems.

**Images built:**
| Service | Image Name | Dockerfile |
|---------|-----------|------------|
| Items | `<username>/items:latest` | `project/microservice/Dockerfile` |
| Auth | `<username>/auth:latest` | `project/auth_service/Dockerfile` |
| Orders | `<username>/orders:latest` | `project/orders_service/Dockerfile` |

**Tagging strategy:**
- `latest` — always the most recent build
- `<commit-sha>` — unique tag for every commit (for rollbacks)

**Runs after:** `sonarqube` passes

---

## CD Pipeline — Deployment

### Deploy via AWS SSM

**What it does:** Pulls the latest Docker images onto the EC2 production server and restarts the services.

**Why:** Instead of SSH-ing into the server manually, we use AWS Systems Manager (SSM) to send commands remotely. This is more secure (no SSH keys needed) and auditable.

**Triggers:**
- Automatically on push to `main` branch (after merging dev)
- Manually via GitHub Actions "Run workflow" button

**Deployment steps (executed on EC2):**
1. Clone the latest repo (to get updated `docker-compose.yml`)
2. Login to Docker Hub
3. Pull latest images
4. Run `docker compose up -d` (starts/updates services)
5. Prune old unused images (saves disk space)

**What is AWS SSM?**
AWS Systems Manager lets you run commands on EC2 instances without SSH. The instance has an SSM Agent installed, and AWS handles the secure communication. Commands are sent via `aws ssm send-command` and results are retrieved with `aws ssm get-command-invocation`.

---

## Secrets & Variables

These are configured in GitHub repository settings:

### Secrets (sensitive, never shown in logs)

| Name | Purpose |
|------|---------|
| `DOCKERHUB_TOKEN` | Authentication token for Docker Hub push/pull |
| `SONAR_TOKEN` | Authentication for SonarQube server |
| `SONAR_HOST_URL` | URL of the SonarQube server |
| `AWS_ROLE_ARN` | IAM role ARN for AWS authentication (CD) |
| `EC2_INSTANCE_ID` | Target EC2 instance for deployment |

### Variables (non-sensitive)

| Name | Purpose |
|------|---------|
| `DOCKERHUB_USERNAME` | Docker Hub username for image naming |

---

## Workflow: Developer's Day-to-Day

### Normal development flow:

1. **Developer pushes code to `dev` branch**
2. CI pipeline triggers automatically
3. If all jobs pass (green checkmark) → code is safe
4. If any job fails (red X) → developer fixes the issue and pushes again
5. Once ready for production → **merge `dev` into `main`**
6. CD pipeline triggers → application is deployed

### If a job fails:

| Failed Job | What to do |
|------------|-----------|
| Compile | Fix the Python syntax error shown in logs |
| Lint | Fix the code style issue (undefined variable, etc.) |
| Test | Fix the broken test or the bug that caused it to fail |
| Gitleaks | Remove the secret from code, rotate the credential, add to `.gitleaksignore` if false positive |
| Trivy | Upgrade the vulnerable package version in `requirements.txt` |
| SonarQube | Fix the code quality issue in the SonarQube dashboard |
| Docker | Check Dockerfile for errors, verify Docker Hub credentials |
| Deploy (CD) | Check SSM command output, verify EC2 instance is running, check AWS credentials |

---

## File Locations

| File | Purpose |
|------|---------|
| `.github/workflows/python-package.yml` | CI pipeline definition |
| `.github/workflows/CD.yaml` | CD pipeline definition |
| `.gitleaksignore` | Allowlisted Gitleaks findings (false positives) |
| `sonar-project.properties` | SonarQube scan configuration |
| `project/docker-compose.yml` | Production deployment configuration |
| `project/*/Dockerfile` | Docker build instructions per service |
| `project/*/requirements.txt` | Python dependencies per service |

---

## Tools Summary

| Tool | Category | What it does |
|------|----------|-------------|
| **Python compileall** | Build | Validates Python syntax |
| **Flake8** | Code Quality | Lints code for style and errors |
| **Pytest** | Testing | Runs automated tests |
| **Gitleaks** | Security | Detects leaked secrets in git history |
| **Trivy** | Security | Finds vulnerable dependencies (CVEs) |
| **SonarQube** | Code Quality | Deep static analysis, quality metrics |
| **Docker** | Packaging | Builds portable application images |
| **AWS SSM** | Deployment | Executes commands on EC2 remotely |

---

## Architecture Diagram

```
Developer
    │
    ▼ (git push to dev)
┌──────────────────────────────────────────────┐
│              GitHub Actions (CI)              │
│                                              │
│  ┌─────────┐   ┌──────┐   ┌──────┐         │
│  │ Compile │──▶│ Lint │──▶│ Test │──┐       │
│  └────┬────┘   └──────┘   └──────┘  │       │
│       │                              ▼       │
│       └──▶┌──────────┐      ┌───────────┐   │
│           │ Gitleaks │─────▶│   Trivy   │   │
│           └──────────┘      └─────┬─────┘   │
│                                   ▼         │
│                           ┌─────────────┐    │
│                           │  SonarQube  │    │
│                           └──────┬──────┘    │
│                                  ▼           │
│                          ┌──────────────┐    │
│                          │ Docker Build │    │
│                          │   & Push     │    │
│                          └──────┬───────┘    │
└─────────────────────────────────┼────────────┘
                                  ▼
                          ┌──────────────┐
                          │  Docker Hub  │
                          │  (Registry)  │
                          └──────┬───────┘
                                 │
    Merge dev → main             │
         │                       │
         ▼                       ▼ (docker pull)
┌──────────────────────────────────────────────┐
│              GitHub Actions (CD)              │
│                                              │
│         AWS SSM → EC2 Instance               │
│         docker compose up -d                 │
│                                              │
└──────────────────────────────────────────────┘
                    │
                    ▼
         ┌───────────────────┐
         │  Production EC2   │
         │                   │
         │  items    :8000   │
         │  auth     :8001   │
         │  orders   :8002   │
         │  postgres :5432   │
         └───────────────────┘
```

---

## FAQ

**Q: What happens if I push directly to `main`?**
A: Only the CD pipeline runs (deployment). CI does not run on `main`. Always push to `dev` first.

**Q: Can I deploy manually without merging?**
A: Yes. Go to GitHub → Actions → "CD - Deploy to EC2 via SSM" → "Run workflow" button.

**Q: What if Trivy finds a vulnerability but there's no fix available?**
A: If the fix version doesn't exist yet, you can temporarily change the severity filter or add a `.trivyignore` file to suppress known unfixable CVEs.

**Q: Where do I see SonarQube results?**
A: Open the SonarQube server URL (configured in `SONAR_HOST_URL` secret) in your browser. Find the project "majorproject-microservices".

**Q: How do I add a new secret?**
A: GitHub → Repository → Settings → Secrets and Variables → Actions → New repository secret.

**Q: How do I rollback to a previous version?**
A: Each Docker image is tagged with the git commit SHA. To rollback:
```bash
docker compose pull  # with DOCKERHUB_USERNAME/service:<old-commit-sha>
docker compose up -d
```

---

## Maintenance

- **Keep dependencies updated** — Run Trivy locally (`trivy fs .`) before pushing to catch issues early
- **Review SonarQube dashboard weekly** — Fix code smells before they accumulate
- **Rotate secrets periodically** — Update `DOCKERHUB_TOKEN`, `SONAR_TOKEN`, etc.
- **Monitor the self-hosted runner** — `Agent-1` needs to stay online for CI to run
