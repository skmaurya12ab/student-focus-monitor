# Student Focus Monitor

> Also referred to as: **Student Distraction Detection System**

A privacy-first web application designed to help students maintain deep focus during study sessions. The eventual application will monitor focus in real-time using camera-based head pose, gaze, and posture telemetry, provide subtle distraction alerts, track historical session metrics, and progressively improve detection accuracy using anonymized numerical movement telemetry and machine learning.

---

## 📌 Project Status: Phase 1 — Project Bootstrap

> **Notice:** This repository is currently at **Phase 1 (Bootstrap & Development Environment)**.
> - **Live monitoring, camera feeds, MediaPipe/OpenCV, and ML models are NOT yet implemented.**
> - The reference detector script (`student_distraction_detector_v4.py`) remains untouched for refactoring in Phase 2.
> - No database tables, migrations, or authentication systems are active.
> - Phase 1 delivers a clean monorepo architecture, runnable FastAPI backend with health checking, React + Vite frontend bootstrap screen, PostgreSQL container configuration, automated tests, and GitHub Actions CI.

---

## 🏗️ Repository Architecture

The project is structured as a monorepo:

```text
student-focus-monitor/
│
├── frontend/                     # React + TypeScript + Vite application
│   ├── src/
│   │   ├── app/                  # Main App shell and bootstrap component
│   │   ├── components/           # Reusable UI components (Phase 3+)
│   │   ├── features/             # Feature slices (sessions, analytics, etc.)
│   │   ├── services/             # API clients and network services
│   │   ├── types/                # TypeScript interfaces and type definitions
│   │   ├── utils/                # Utility and helper functions
│   │   └── styles/               # CSS stylesheets and design tokens
│   ├── public/                   # Static public assets
│   ├── package.json              # Frontend dependencies and scripts
│   ├── tsconfig.json             # TypeScript configuration
│   └── vite.config.ts            # Vite configuration with Vitest
│
├── backend/                      # Python + FastAPI backend
│   ├── app/
│   │   ├── main.py               # Application entry point and CORS setup
│   │   ├── api/                  # API routers (health check, v1 endpoints)
│   │   ├── core/                 # Centralized configuration and settings
│   │   ├── db/                   # Database session and base (Phase 4)
│   │   ├── models/               # SQLAlchemy ORM models (Phase 4)
│   │   ├── schemas/              # Pydantic schemas for data validation
│   │   ├── services/             # Business logic and service layers
│   │   └── detection/            # Modularized detection engine (Phase 2)
│   ├── tests/                    # Pytest test suite
│   ├── pytest.ini                # Pytest configuration
│   └── requirements.txt          # Python backend dependencies
│
├── ml/                           # Machine learning workspace (Phases 11–14)
│   ├── data/                     # Anonymized numerical telemetry datasets
│   ├── notebooks/                # Exploratory notebooks
│   ├── src/                      # Feature extraction and training pipelines
│   ├── models/                   # Serialized model artifacts
│   ├── evaluation/               # Model evaluation scripts and benchmarks
│   ├── scripts/                  # Data curation scripts
│   └── README.md                 # ML pipeline documentation
│
├── docs/                         # Project documentation
│   ├── development.md            # Detailed local setup and workflow guide
│   └── roadmap.md                # 15-phase project roadmap
│
├── .github/                      # CI/CD workflows
│   └── workflows/
│       └── ci.yml                # Automated GitHub Actions test & build workflow
│
├── .env.example                  # Environment variable template
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # PostgreSQL development service
├── LICENSE                       # MIT License
└── student_distraction_detector_v4.py  # Reference rule-based detector (untouched)
```

---

## ⚙️ Prerequisites

- **Python**: `3.10+` (tested on Python 3.14.4)
- **Node.js**: `18.0.0+` (tested on Node.js v20.20.2)
- **npm**: `9.0.0+` (tested on npm 10.8.2)
- **Docker & Docker Compose**: Optional for Phase 1 (required to run PostgreSQL container)
- **Git**: Version control

---

## 🚀 Quickstart Guide

### 1. Environment Configuration

Copy the example configuration to `.env`:

```bash
cp .env.example .env
```

Key variables configured in `.env.example`:
- `APP_ENV`: `development`
- `BACKEND_HOST`: `0.0.0.0`
- `BACKEND_PORT`: `8000`
- `FRONTEND_ORIGIN`: `http://localhost:5173`
- `DATABASE_URL`: `postgresql://postgres:postgres@localhost:5432/student_focus_monitor`
- `VITE_API_BASE_URL`: `http://localhost:8000`

### 2. Start PostgreSQL (Docker Compose)

Start the PostgreSQL development container:

```bash
docker compose up -d postgres
```

> The database service will listen on port `5432`. Note that the backend health endpoint does not require PostgreSQL to be running during Phase 1.

### 3. Backend Setup & Startup

Install Python dependencies:

```bash
pip install -r backend/requirements.txt
```

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Access:
- **API Root**: [http://localhost:8000/](http://localhost:8000/)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
- **Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Frontend Setup & Startup

Install dependencies:

```bash
cd frontend
npm install
```

Start the development server:

```bash
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser. The bootstrap screen will immediately check backend health and display `Backend: Connected` or `Backend: Unavailable`.

---

## 🧪 Testing & Verification

### Run Backend Tests

```bash
cd backend
pytest
```

Expected output:
```text
tests/test_health.py .. [100%]
2 passed
```

### Run Frontend Tests

```bash
cd frontend
npm test
```

### Build Frontend for Production

```bash
cd frontend
npm run build
```

---

## 🗺️ Roadmap & Future Phases

- **Phase 0** — Architecture and specification
- **Phase 1** — Project bootstrap *(Current)*
- **Phase 2** — Detection engine refactor
- **Phase 3** — Figma frontend
- **Phase 4** — PostgreSQL schema
- **Phase 5** — Google authentication
- **Phase 6** — Study session lifecycle
- **Phase 7** — Camera and realtime transport
- **Phase 8** — Real monitoring
- **Phase 9** — Live dashboard integration
- **Phase 10** — Session history and analytics
- **Phase 11** — Telemetry and user feedback
- **Phase 12** — ML dataset pipeline
- **Phase 13** — First ML model
- **Phase 14** — ML shadow mode

For full details, see [docs/roadmap.md](file:///run/media/saurabh-kumar-maurya/D43C3FD33C3FAEFC/Student%20Focus%20Monitor%20%E2%80%94%20Dashboard/docs/roadmap.md).
