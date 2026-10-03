# Development Guide

This guide covers prerequisites, setup steps, daily development workflows, and testing instructions for the Student Focus Monitor monorepo.

---

## 1. Prerequisites

- **Python**: `3.10+` (tested with Python 3.14.4)
- **Node.js**: `18.0.0+` (tested with Node.js v20.20.2)
- **npm**: `9.0.0+` (tested with npm 10.8.2)
- **Docker & Docker Compose**: Optional for Phase 1 (required for local PostgreSQL database service)
- **Git**: For version control

---

## 2. Environment Configuration

Copy the example environment configuration file to create your local `.env`:

```bash
cp .env.example .env
```

Review and adjust variables in `.env` as needed:
- `APP_ENV`: Application environment (`development`)
- `BACKEND_HOST`: Host for FastAPI server (`0.0.0.0`)
- `BACKEND_PORT`: Port for FastAPI server (`8000`)
- `FRONTEND_ORIGIN`: Allowed frontend origin for CORS (`http://localhost:5173`)
- `DATABASE_URL`: PostgreSQL connection string
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`: Database credentials for Docker Compose
- `VITE_API_BASE_URL`: Backend URL for frontend calls (`http://localhost:8000`)

---

## 3. PostgreSQL Database Setup (Docker Compose)

To start the PostgreSQL development service:

```bash
docker compose up -d postgres
```

To verify PostgreSQL is running:

```bash
docker compose ps
```

To stop PostgreSQL:

```bash
docker compose down
```

> **Note:** The backend health endpoint does NOT depend on PostgreSQL running. In Phase 1, no database models or migrations are executed.

---

## 4. Backend Setup & Startup

### Virtual Environment Creation

From the repository root or inside the `backend/` directory:

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate
```

### Install Dependencies

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Run Backend Server

From the repository root:

```bash
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Or from inside the `backend/` directory:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The backend will be available at:
- **Root**: `http://localhost:8000/`
- **Health Check**: `http://localhost:8000/api/health`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

## 5. Frontend Setup & Startup

### Install Dependencies

Navigate to the `frontend/` directory and install packages using npm:

```bash
cd frontend
npm install
```

### Run Frontend Development Server

```bash
npm run dev
```

The frontend will run at:
- **URL**: `http://localhost:5173`

The development screen will automatically query `GET http://localhost:8000/api/health` and report the backend connection status.

---

## 6. Testing & Build Commands

### Backend Tests

From the `backend/` directory:

```bash
cd backend
pytest
```

Or run pytest with verbose output:

```bash
pytest -v
```

### Frontend Tests

From the `frontend/` directory:

```bash
cd frontend
npm test
```

### Frontend Production Build

From the `frontend/` directory:

```bash
cd frontend
npm run build
```

---

## 7. Git Workflow

- **Branching**: Develop features on dedicated branches branched from `main`.
- **Commits**: Follow conventional commits (e.g. `feat: ...`, `fix: ...`, `chore: ...`).
- **Hygiene**:
  - Never commit `.env` or sensitive credentials.
  - Never commit `node_modules`, virtual environments, or compiled assets.
  - Ensure tests pass locally before committing and pushing.
