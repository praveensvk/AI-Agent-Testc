# AI Agent Test Platform

An intelligent, multi-agent LLM-powered platform that converts **natural-language test descriptions** into fully executable **Playwright + TypeScript** browser tests. Describe what you want to test in plain English — the platform's 7-agent AI pipeline analyzes your requirements, crawls the target application, generates IEEE 829-compliant test cases, produces Playwright code, and runs it across multiple browsers with real-time progress updates.

## Key Features

- **Natural Language → Executable Tests** — Write test cases in plain English; the AI pipeline handles the rest
- **7-Agent LLM Pipeline** — Orchestrator, DOM Analyst, Test Generator, Test Case Reviewer, Step Generator, Step Reviewer, and Code Generator working in concert
- **Real DOM Grounding** — Playwright-based crawler extracts actual page structure so generated selectors target real elements
- **IEEE 829 Test Standard** — Generated test cases follow the IEEE 829 format (ID, title, category, priority, steps, expected results)
- **Multi-Browser Support** — Run tests on Chromium, Firefox, or WebKit
- **Headed & Headless Modes** — Debug visually with headed mode or run headless for CI/CD
- **Live WebSocket Updates** — Real-time step-by-step execution progress with screenshots
- **Artifact Collection** — Automatic capture of screenshots, videos, execution traces, and logs
- **Site Crawl (Auto-Gen)** — Pre-crawl your application to provide richer context for test generation
- **Protected App Support** — Optional suite-level authentication for login-protected applications
- **MCP Browser Enrichment** — Playwright MCP provides accessibility tree data for better element discovery

## Architecture

```
┌──────────────────┐        ┌──────────────────┐        ┌──────────────┐
│  React 19        │  REST  │  FastAPI          │        │  PostgreSQL  │
│  Vite + TS       │◄──────►│  Python 3.13      │◄──────►│  18          │
│  Port 5173       │   WS   │  Port 8000        │        │  Port 5432   │
└──────────────────┘        └──────────────────┘        └──────────────┘
     Frontend                  Backend / Agents              Database

                          ┌──────────────────────┐
                          │  LLM Provider         │
                          │  Groq (cloud) or      │
                          │  Ollama (local)        │
                          └──────────────────────┘

                          ┌──────────────────────┐
                          │  Playwright Runner    │
                          │  .spec.ts execution   │
                          │  via npx playwright   │
                          └──────────────────────┘
```

| Layer      | Stack                                                              |
| ---------- | ------------------------------------------------------------------ |
| Frontend   | React 19, Vite 8, TypeScript, Tailwind CSS 4, React Router 7      |
| Backend    | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic             |
| AI/Agents  | LangChain, LangGraph, Groq (llama-3.3-70b) or Ollama (local)     |
| Browser    | Playwright (Python crawling + TypeScript test execution)           |
| Database   | PostgreSQL 18 (asyncpg driver)                                    |
| Realtime   | WebSocket (live test run progress, site crawl updates)             |

## How It Works

```
  User writes test case in plain English
                    │
                    ▼
  ┌─────────────────────────────────┐
  │  1. Orchestrator (Plan-and-Execute)       │──► Decomposes NL into goals, pages, assertions
  │  2. Snapshot Loader                       │──► Loads pre-crawled DOM or live crawls target app
  │  3. DOM Analyst                           │──► Identifies semantic UI groups & stable selectors
  │  4. Test Generator                        │──► Produces IEEE 829 test cases from plan + DOM
  │  5. Test Case Reviewer (Loop A)           │──► Validates coverage; re-runs #4 if needed
  │  6. Step Generator (ReAct)                │──► Converts test cases → Playwright action steps
  │  7. Step Reviewer (Loop B)                │──► Validates executability; fixes selectors from real DOM
  │  8. Code Generator                        │──► Produces final .spec.ts TypeScript file
  └─────────────────────────────────┘
                    │
                    ▼
  Executable Playwright test stored in DB + filesystem
                    │
                    ▼
  User clicks "Run Test" → npx playwright test
                    │
                    ▼
  Live WebSocket progress + screenshots/videos/traces
```

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, WebSocket endpoints, static mounts
│   │   ├── config.py          # Pydantic Settings (all env vars)
│   │   ├── database.py        # Async SQLAlchemy engine & session
│   │   ├── models/            # ORM models (TestSuite, TestCase, TestStep, TestRun, Artifact)
│   │   ├── schemas/           # Pydantic request/response DTOs + agent schemas
│   │   ├── routers/           # API endpoints (suites, cases, runs, generation, site_crawl)
│   │   ├── services/          # Business logic (test generation, execution, crawling, artifacts)
│   │   ├── agents/            # LLM agents (orchestrator, DOM analyst, generators, reviewers, workflow)
│   │   └── utils/
│   ├── migrations/            # Alembic database migrations
│   ├── generated-tests/       # Generated .spec.ts files (per suite)
│   ├── artifacts/             # Test run artifacts (screenshots, videos, traces, logs)
│   ├── requirements.txt
│   └── .env                   # Environment configuration (create from template below)
├── frontend/
│   ├── src/
│   │   ├── App.tsx            # React Router route definitions
│   │   ├── pages/             # Page components (Dashboard, Suites, Cases, Runs, Reports, Settings)
│   │   ├── components/        # Shared UI components
│   │   ├── hooks/             # Custom React hooks (WebSocket, API)
│   │   ├── services/          # API client modules & WebSocket client
│   │   └── types/             # TypeScript domain types
│   └── package.json
├── ARCHITECTURE.md            # Detailed architecture documentation
└── plan.md                    # Full project roadmap
```

## Prerequisites

- **Python 3.13+**
- **Node.js 20+** and npm
- **PostgreSQL 18** installed and running
- **Groq API key** (free at [console.groq.com](https://console.groq.com)) — or **Ollama** for local LLM inference

## Getting Started

### 1. Database Setup

```bash
psql -U postgres
```

```sql
CREATE DATABASE ai_agent_test;
\q
```

### 2. Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install

# Create .env file (see Environment Variables section below)

# Run database migrations
alembic upgrade head

# Start the backend server
python start.py
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**. Health check: `GET /health`

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the Vite dev server
npm run dev
```

The frontend will be available at **http://localhost:5173**.

### 4. Install Playwright Test Runner (for test execution)

```bash
cd backend/generated-tests

# Install Node.js test dependencies
npm install

# Install browser binaries for the test runner
npx playwright install
```

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/ai_agent_test
DATABASE_URL_SYNC=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/ai_agent_test

# App
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true

# LLM Provider — "groq" (cloud) or "ollama" (local)
LLM_PROVIDER=groq

# Groq (required if LLM_PROVIDER=groq)
GROQ_API_KEY=gsk_your_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# Ollama (required if LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:7b

# LLM
LLM_TEMPERATURE=0.2

# Artifacts & generated tests
ARTIFACTS_DIR=./artifacts
GENERATED_TESTS_DIR=./generated-tests

# Agent settings
MAX_REVERIFICATION_ATTEMPTS=3
CRAWLER_TIMEOUT_MS=30000

# Playwright MCP (optional — enriches DOM with accessibility tree)
PLAYWRIGHT_MCP_COMMAND=npx @playwright/mcp
MCP_ENRICHMENT_ENABLED=true

# Execution timeouts
STEP_TIMEOUT_MS=15000
NAVIGATION_TIMEOUT_MS=30000
EXECUTION_TIMEOUT_S=300
```

## API Endpoints

### Test Suites

| Method   | Endpoint                        | Description                    |
| -------- | ------------------------------- | ------------------------------ |
| `POST`   | `/test-suites`                  | Create a test suite            |
| `GET`    | `/test-suites`                  | List all test suites           |
| `GET`    | `/test-suites/{id}`             | Get suite with test cases      |
| `PATCH`  | `/test-suites/{id}`             | Update a test suite            |
| `DELETE` | `/test-suites/{id}`             | Delete a test suite            |

### Test Cases

| Method   | Endpoint                              | Description                        |
| -------- | ------------------------------------- | ---------------------------------- |
| `POST`   | `/test-suites/{id}/test-cases`        | Create a test case in a suite      |
| `GET`    | `/test-suites/{id}/test-cases`        | List test cases for a suite        |
| `GET`    | `/test-cases/{id}`                    | Get test case with steps           |
| `DELETE` | `/test-cases/{id}`                    | Delete a test case                 |
| `PUT`    | `/test-cases/{id}/steps`              | Update test steps                  |

### AI Test Generation

| Method   | Endpoint                              | Description                        |
| -------- | ------------------------------------- | ---------------------------------- |
| `POST`   | `/test-cases/{id}/generate`           | Trigger AI test generation         |
| `GET`    | `/test-cases/{id}/generate/status`    | Get generation progress            |
| `GET`    | `/test-cases/{id}/code`               | Get generated .spec.ts code        |
| `POST`   | `/test-cases/{id}/code/generate`      | Regenerate code from existing steps|

### Test Execution

| Method   | Endpoint                                              | Description                |
| -------- | ----------------------------------------------------- | -------------------------- |
| `POST`   | `/test-runs`                                          | Create and start a test run|
| `GET`    | `/test-runs`                                          | List test runs             |
| `GET`    | `/test-runs/{id}`                                     | Get run details + artifacts|
| `DELETE` | `/test-runs/{id}`                                     | Delete a test run          |
| `GET`    | `/test-runs/{run_id}/artifacts/{artifact_id}/download` | Download an artifact file |

### Site Crawl

| Method   | Endpoint                                    | Description                    |
| -------- | ------------------------------------------- | ------------------------------ |
| `POST`   | `/test-suites/{id}/crawl`                   | Trigger site-wide BFS crawl    |
| `GET`    | `/test-suites/{id}/crawl/status`            | Get crawl progress             |
| `GET`    | `/test-suites/{id}/crawl/results`           | Get crawl manifest (summary)   |
| `GET`    | `/test-suites/{id}/crawl/pages/{index}`     | Get full DOM data for one page |

### WebSocket

| Endpoint                      | Description                        |
| ----------------------------- | ---------------------------------- |
| `WS /ws/test-runs/{run_id}`   | Live test execution progress       |
| `WS /ws/crawl/{suite_id}`     | Live site crawl progress           |

### System

| Method | Endpoint         | Description                              |
| ------ | ---------------- | ---------------------------------------- |
| `GET`  | `/health`        | Health check                             |
| `GET`  | `/api/settings`  | App configuration (LLM model, timeouts)  |

## Frontend Pages

| Route                              | Description                                             |
| ---------------------------------- | ------------------------------------------------------- |
| `/dashboard`                       | Dashboard — test suite overview, quick stats            |
| `/suites`                          | Test suites list                                        |
| `/suites/:suiteId`                 | Suite detail — test cases, generate, crawl site         |
| `/suites/:suiteId/cases/:caseId`   | Case detail — generated steps, run on any browser       |
| `/runs`                            | All test runs table with status filters                 |
| `/runs/:runId`                     | Run detail — live progress, errors, artifact downloads  |
| `/reports`                         | Test reports and analytics                              |
| `/settings`                        | Application settings                                    |

## Development

```bash
# Backend — auto-reloads on file changes
cd backend
venv\Scripts\activate
uvicorn app.main:app --reload

# Frontend — Vite HMR, auto-reloads on file changes
cd frontend
npm run dev

# Build frontend for production
cd frontend
npm run build
npm run preview
```

## Roadmap

See [plan.md](plan.md) for the full implementation roadmap. See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

- **Phase 1** ✅ Foundation — DB schema, REST API, frontend scaffold
- **Phase 2** ✅ LLM Agents — LangChain/LangGraph pipeline, page crawler, requirement analyzer
- **Phase 3** ✅ Code Generation — Test generator agent, Playwright .spec.ts output
- **Phase 4** ✅ Test Execution — Playwright test runner via `npx playwright test`, artifact capture
- **Phase 5** ✅ Frontend — All pages, components, hooks, WebSocket client
- **Phase 7** ✅ Runner Overhaul — Code executor, MCP crawler enrichment, DOM analyst agent