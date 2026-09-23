# CI/CD Pipeline Documentation

The CI/CD pipeline for the AI Research Agent is built on GitHub Actions and designed to enforce strict code quality, type safety, and security boundaries.

## Architecture

The pipeline consists of four main workflows located in `.github/workflows/`:

### 1. `ci.yml` (Continuous Integration)
**Triggers:** Push to `main`, PRs to `main`, `develop`, or `feature/*` branches.
**Jobs:**
- **Frontend Quality:** Runs `npm ci`, `npm run lint` (ESLint), and `npm run build` (Next.js build implicitly type checks and validates static assets).
- **Backend Quality:** Uses `ruff` for ultra-fast linting and formatting. Runs `pytest` across all 252+ tests (including End-to-End simulation) using a mocked LLM interface to avoid dependency on an external API or live Ollama instance. Generates a coverage XML report.

### 2. `security.yml` (Security Scanning)
**Triggers:** PRs to main branches, Weekly cron job.
**Jobs:**
- **Dependency Scanning:** Runs `npm audit` and `pip-audit` to detect known vulnerable versions of packages in `package-lock.json` and `requirements.txt`.
- **Trivy Repo Scan:** Uses Aqua Security's Trivy to scan the repository filesystem for leaked secrets, misconfigurations, and severe infrastructure vulnerabilities.

### 3. `docker.yml` (Docker Build & Publish)
**Triggers:** Push to `main`, matching tag `v*.*.*`.
**Jobs:**
- **Build & Push:** Uses Docker Buildx to build both the `backend` and `frontend` multi-stage container images.
- **Publish:** Tags the images immutably with the commit SHA, branch name, and semantic version, then pushes them to the GitHub Container Registry (`ghcr.io`).

### 4. `cd.yml` (Continuous Deployment Stub)
**Triggers:** Manual `workflow_dispatch`.
**Jobs:**
- **Deploy:** A skeleton workflow ready to pull the GHCR images and deploy them to the target environment (e.g. AWS EC2, VPS) via SSH. Requires configuring GitHub Secrets (`SSH_PRIVATE_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`).

## Security Model
- **Secrets Management:** No secrets (LLM keys, DB credentials) are stored in the repo. CI uses mock integrations. Deployment credentials must be added to GitHub Environment Secrets.
- **LLM Boundary:** The CI pipeline validates that the deterministic executor correctly handles malformed, dangerous, or missing LLM responses. The safety boundary is thoroughly tested.
- **Original Dataset Safety:** The pipeline guarantees that the initial dataset uploaded is strictly read-only and preserved immutably.

## Local Validation Commands

Before pushing, run these checks locally:

```bash
# 1. Backend Linting
cd backend
ruff check .

# 2. Backend Tests
python -m pytest ../tests/

# 3. Frontend Build/Lint
cd frontend
npm run lint
npm run build
```
