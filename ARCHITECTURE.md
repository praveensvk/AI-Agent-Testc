# AI-Agent UI Testing Platform — Architecture & Technical Reference

> A comprehensive guide to the system architecture, technology choices, AI agents, and end-to-end setup instructions.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [High-Level Architecture](#2-high-level-architecture)
3. [System Components](#3-system-components)
4. [AI Agents & LLM Strategy](#4-ai-agents--llm-strategy)
5. [Technology Stack & Rationale](#5-technology-stack--rationale)
6. [Database Design](#6-database-design)
7. [API Reference](#7-api-reference)
8. [Frontend Application](#8-frontend-application)
9. [Sample E-Commerce Target App](#9-sample-e-commerce-target-app)
10. [Infrastructure & DevOps](#10-infrastructure--devops)
11. [End-to-End Setup Guide](#11-end-to-end-setup-guide)
12. [Project Status & Roadmap](#12-project-status--roadmap)

---

## 1. Project Overview

The **AI-Agent UI Testing Platform** is an intelligent, LLM-driven system that automatically generates and executes UI test cases against web applications. Instead of manually scripting Playwright tests, the platform uses AI agents to:

1. **Analyze** a target web application's pages and behavior
2. **Generate** structured test cases following IEEE 829 standards
3. **Produce** executable Playwright test steps with real CSS/XPath selectors
4. **Execute** those tests in a headless browser, collecting screenshots, videos, and pass/fail results
5. **Report** results through a React dashboard with real-time updates

The platform ships with a **Sample E-Commerce App ("TechStore")** as a built-in target for demonstration and validation.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER / BROWSER                               │
└───────────────┬──────────────────────────────────┬───────────────────┘
                │                                  │
                ▼                                  ▼
┌───────────────────────────┐    ┌──────────────────────────────────┐
│   AI Testing Platform     │    │  Sample E-Commerce App           │
│   React Frontend          │    │  (Target Under Test)             │
│   Port 3000 (Vite)        │    │  React Frontend — Port 3000*    │
│                           │    │  Express Backend — Port 5000     │
│  ┌─────────────────────┐  │    └──────────────────────────────────┘
│  │ Dashboard            │  │                 ▲
│  │ Test Suites Manager  │  │                 │  Playwright browses
│  │ Test Cases Manager   │  │                 │  the target app
│  │ Execution Viewer     │  │                 │
│  └─────────┬───────────┘  │    ┌─────────────┴──────────────────┐
│            │ REST API      │    │                                 │
└────────────┼───────────────┘    │   Playwright Browser Engine     │
             │                    │   (Headless Chrome/Firefox)     │
             ▼                    │                                 │
┌────────────────────────────┐    └─────────────┬─────────────────┘
│   FastAPI Backend          │                  │
│   Port 8000                │◄─────────────────┘
│                            │    Captures screenshots, videos,
│  ┌──────────────────────┐  │    assertions, execution results
│  │ Routers (API Layer)   │  │
│  │   /test-suites        │  │
│  │   /test-cases         │  │
│  │   /test-steps         │  │
│  │   /execution          │  │
│  │   /generate-tests     │  │
│  │   /health             │  │
│  └──────────┬───────────┘  │
│             │               │
│  ┌──────────▼───────────┐  │    ┌──────────────────────────────┐
│  │ Services Layer        │──┼──►│  Ollama LLM Service          │
│  │   Test Generation     │  │   │  (LLaMA 2 Model)             │
│  │   Test Execution      │  │   │  Port 11434 (Docker)         │
│  │   Artifact Management │  │   └──────────────────────────────┘
│  └──────────┬───────────┘  │
│             │               │
│  ┌──────────▼───────────┐  │
│  │ Database Layer        │  │
│  │   SQLAlchemy ORM      │  │
│  │   SQLite (dev)        │  │
│  │   PostgreSQL (prod)   │  │
│  └──────────────────────┘  │
└────────────────────────────┘

* Note: The sample ecommerce frontend runs on port 3000 by default.
  When running both, change one of the frontend ports.
```

### Data Flow

```
User creates Test Suite (base_url → target app)
        │
        ▼
User creates Test Cases (paths like /login, /cart)
        │
        ▼
LLM Agent analyzes page + context  ──►  Ollama LLaMA 2
        │                                     │
        ▼                                     ▼
Generates TestSteps (navigate, click, fill, assert)
        │
        ▼
Playwright executes steps against target app
        │
        ▼
Results (pass/fail, screenshots, videos, logs) ──► stored in DB + artifacts/
        │
        ▼
Dashboard shows results to user
```

---

## 3. System Components

### 3.1 Backend — FastAPI Application (`backend/`)

| File / Directory | Purpose |
|---|---|
| `app/main.py` | FastAPI app initialization, CORS middleware, router registration, startup/shutdown hooks |
| `app/config.py` | Pydantic Settings — DB URL, Ollama config, Playwright settings, loaded from `.env` |
| `app/database.py` | SQLAlchemy engine (SQLite with StaticPool / PostgreSQL with NullPool), session factory, `get_db()` dependency |
| `app/models/` | SQLAlchemy ORM models — TestSuite, TestCase, TestStep, ExecutionResult |
| `app/schemas/` | Pydantic request/response schemas for validation and serialization |
| `app/routers/` | FastAPI routers defining all REST API endpoints |
| `app/services/` | Business logic layer — LLM integration, test execution orchestration (to be implemented) |
| `app/runners/` | Playwright test execution engines (to be implemented) |
| `app/utils/logger.py` | Centralized Python logging configuration |
| `scripts/init_db.py` | Database initialization + seed data (sample login test suite) |
| `artifacts/` | Runtime directory for execution artifacts — screenshots, videos, traces |
| `generated-tests/` | Runtime directory for LLM-generated Playwright test scripts |

### 3.2 Frontend — React SPA (`frontend/`)

| File / Directory | Purpose |
|---|---|
| `src/App.jsx` | Root component with React Router — 4 routes (Dashboard, Suites, Cases, Execute) |
| `src/main.jsx` | Application entry point, mounts React to DOM |
| `src/components/Navbar.jsx` | Sticky navigation bar with active route highlighting |
| `src/pages/Dashboard.jsx` | System overview — stats, health check, getting-started guide |
| `src/pages/TestSuites.jsx` | CRUD for test suites — list, create, delete |
| `src/pages/TestCases.jsx` | CRUD for test cases — list (filterable by suite), create, delete, view steps |
| `src/pages/Execute.jsx` | Test execution UI — select suite/case, run tests, view pass/fail results |
| `src/services/api.js` | Axios HTTP client — all API modules (suites, cases, steps, execution, health) |
| `src/styles/index.css` | Complete design system — purple gradient theme, cards, buttons, grids |

### 3.3 Sample E-Commerce App (`sample-ecommerce/`)

A fully functional "TechStore" app serving as the **target application under test**. See [Section 9](#9-sample-e-commerce-target-app) for details.

---

## 4. AI Agents & LLM Strategy

### 4.1 LLM Provider: Ollama with LLaMA 2

**Why Ollama + LLaMA 2?**

| Reason | Explanation |
|---|---|
| **Local / Self-hosted** | Runs entirely on your machine via Docker — no API keys, no cloud costs, no data leaving your network |
| **Privacy** | Web page content and test logic stay on-premise; ideal for testing internal/private apps |
| **Cost-Effective** | Zero per-token cost after initial model download, unlike OpenAI GPT-4 or Claude |
| **Offline-Capable** | Works without internet after model is cached locally |
| **Customizable** | LLaMA 2 can be fine-tuned or swapped for other Ollama-supported models (Mistral, CodeLlama, etc.) |
| **Developer-Friendly** | Simple Python SDK (`ollama` package), Docker-based deployment |

### 4.2 Agent Architecture (Planned Pipeline)

The platform uses a **Plan-and-Execute multi-agent pipeline** where specialized agents handle different stages of test generation. The orchestration follows a LangGraph state machine pattern:

```
┌────────────────────────────────────────────────────────────────┐
│                    AGENT PIPELINE                              │
│                                                                │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐   │
│  │ Requirement  │───►│   Crawler    │───►│  Test Generator  │   │
│  │  Analyzer    │    │  (Playwright)│    │  (IEEE 829)      │   │
│  └─────────────┘    └─────────────┘    └────────┬─────────┘   │
│                                                  │              │
│       Decomposes NL       Extracts real          │              │
│       requirements        DOM structure    Produces structured  │
│       into sub-goals      and selectors    test cases           │
│                                                  │              │
│                                                  ▼              │
│  ┌──────────────┐    ┌─────────────┐    ┌──────────────────┐   │
│  │    Code       │◄───│   Step       │◄───│ Step Generator   │   │
│  │  Generator    │    │  Reviewer    │    │ (ReAct Pattern)  │   │
│  └──────────────┘    └─────────────┘    └──────────────────┘   │
│                                                                │
│  Produces final         Validates &          Converts test     │
│  Playwright .spec.ts    fixes selectors      cases to          │
│  files                  using real DOM       executable steps  │
└────────────────────────────────────────────────────────────────┘
```

### 4.3 Individual Agents

| Agent | Pattern | Role | Input | Output |
|---|---|---|---|---|
| **Requirement Analyzer** | Plan-and-Execute | Decomposes natural language test requirements into structured sub-goals, target pages, and assertions | User's NL description | `StructuredTestIntent` (goals, pages, assertions, edge cases) |
| **Crawler** | Tool-based | Uses Playwright to navigate the target app and extract live DOM structure, available selectors, and page metadata | Target URL | DOM tree, CSS selectors, page structure |
| **Test Generator** | Prompted LLM | Generates IEEE 829-compliant test cases from intent + real DOM context | `StructuredTestIntent` + DOM | `IEEE829TestCase[]` (tc_id, title, category, priority, steps, expected results) |
| **Step Generator** | ReAct (Reason + Act) | Converts high-level test cases into concrete, executable Playwright actions | IEEE 829 test cases + DOM | `GeneratedTestStep[]` (navigate, click, type, fill, verify_text, verify_element, wait, screenshot) |
| **Step Reviewer** | Validation Loop | Reviews generated steps for executability, fixes hallucinated selectors by cross-referencing real DOM | Steps + DOM | `StepReviewResult` (approved, fixed_steps, issues, confidence) |
| **Code Generator** | Template-based | Converts reviewed steps into runnable Playwright `.spec.ts` test files | Reviewed steps | `GeneratedTest` (file_name, code_content) |

### 4.4 Why These Agent Patterns?

| Pattern | Used By | Why |
|---|---|---|
| **Plan-and-Execute** | Requirement Analyzer | Complex NL requires decomposition before acting; separates planning from execution |
| **ReAct (Reason+Act)** | Step Generator | Needs to reason about which Playwright action fits, then produce it — iterative chain-of-thought |
| **Validation Loop** | Step Reviewer | LLMs hallucinate selectors; a review loop with real DOM grounding catches and fixes errors before execution |
| **LangGraph State Machine** | Workflow Orchestrator | Enables conditional transitions, retry loops (e.g., re-review failed steps), and clean separation of agent concerns |

### 4.5 Why a Multi-Agent Approach (vs Single Prompt)?

1. **Separation of Concerns** — Each agent has a focused, well-defined task with a tailored prompt
2. **Grounding in Real DOM** — The Crawler provides actual page structure so the LLM doesn't guess selectors
3. **Quality Control** — The Step Reviewer catches LLM mistakes before code generation
4. **Retry Logic** — Failed reviews loop back to step generation with feedback, improving outputs iteratively
5. **Modularity** — Each agent can be independently tested, improved, or swapped to a different model

---

## 5. Technology Stack & Rationale

### 5.1 Backend

| Technology | Version | Purpose | Why This Choice |
|---|---|---|---|
| **Python** | 3.11+ | Backend language | Best ecosystem for AI/ML/LLM tooling (LangChain, Playwright, Ollama SDK) |
| **FastAPI** | ≥0.104.0 | Web framework | Async-native, auto-generated OpenAPI docs, Pydantic integration, excellent performance |
| **SQLAlchemy** | ≥2.0.48 | ORM | Industry-standard Python ORM; supports SQLite + PostgreSQL; declarative models |
| **Pydantic** | ≥2.5.0 | Data validation | Type-safe request/response schemas; deep FastAPI integration; Settings management |
| **Pydantic-Settings** | ≥2.0.0 | Configuration | Loads config from environment variables and `.env` files with type validation |
| **Uvicorn** | ≥0.24.0 | ASGI server | High-performance async server; hot-reload for development |
| **Playwright** | ≥1.40.0 | Browser automation | Cross-browser support (Chromium/Firefox/WebKit); reliable selectors; built-in video/screenshots; async API |
| **Ollama Python SDK** | ≥0.6.0 | LLM client | Native Python client for the local Ollama LLM service |
| **HTTPX** | ≥0.27.0 | Async HTTP | Modern async HTTP client for internal service-to-service calls (e.g., calling Ollama API) |
| **Requests** | ≥2.32.5 | Sync HTTP | Fallback synchronous HTTP client for simple calls |
| **Aiofiles** | ≥23.2.1 | Async file I/O | Non-blocking file operations for artifact storage (screenshots, videos) |
| **python-dotenv** | 1.0.0 | Env management | Loads `.env` files into environment variables |

### 5.2 Frontend

| Technology | Version | Purpose | Why This Choice |
|---|---|---|---|
| **React** | 18.2.0 | UI framework | Component-based architecture; hooks for state management; massive ecosystem |
| **React Router DOM** | 6.20.0 | Client routing | Declarative routing in React SPA; supports query parameters for filtering |
| **Axios** | 1.6.0 | HTTP client | Promise-based HTTP with interceptors; cleaner API than native fetch |
| **Vite** | 5.0.0 | Build tool | 10-100x faster than Webpack; native ES module support; instant HMR |
| **CSS3** (Custom) | — | Styling | Custom design system; no heavy UI library dependency; full control over look & feel |

### 5.3 Sample E-Commerce App

| Technology | Version | Purpose | Why This Choice |
|---|---|---|---|
| **Express.js** | 4.18.2 | Backend framework | Minimal, fast Node.js server; quick to set up a realistic REST API |
| **JWT** (jsonwebtoken) | 9.0.2 | Authentication | Stateless token auth, realistic login/register flow for test scenarios |
| **In-Memory DB** | Custom | Data store | Zero setup; pre-loaded with sample products/users; perfect for demo |
| **React** | 18.2.0 | Frontend | Same framework as main platform, consistent development experience |
| **React Router** | 6.18.0 | Routing | Multi-page navigation for rich test scenarios |
| **React Scripts** | 5.0.1 | Build tool | Create React App standard; rapid prototyping for the demo app |

### 5.4 Infrastructure

| Technology | Purpose | Why This Choice |
|---|---|---|
| **Docker Compose** | Service orchestration | Single command to spin up Ollama LLM + optional PostgreSQL |
| **Ollama (Docker)** | Local LLM serving | Runs LLaMA 2 in a container; GPU passthrough support; persistent model cache |
| **SQLite** | Dev database | Zero config, file-based, ships with Python; perfect for local development |
| **PostgreSQL 16** | Prod database | ACID-compliant, production-grade RDBMS; optional via Docker Compose |

---

## 6. Database Design

### Entity Relationship Diagram

```
┌──────────────────┐       ┌──────────────────┐
│    TestSuite     │       │    TestCase       │
├──────────────────┤       ├──────────────────┤
│ id (PK)          │──────►│ id (PK)          │
│ name             │  1:N  │ suite_id (FK)    │
│ base_url         │       │ path             │
│ description      │       │ name             │
│ created_at       │       │ description      │
│ updated_at       │       │ created_at       │
└──────────────────┘       │ updated_at       │
                           └────┬────────┬────┘
                                │        │
                    1:N         │        │  1:N
                 ┌──────────────┘        └──────────────┐
                 ▼                                      ▼
┌──────────────────────┐            ┌──────────────────────────┐
│     TestStep         │            │   ExecutionResult        │
├──────────────────────┤            ├──────────────────────────┤
│ id (PK)              │            │ id (PK)                  │
│ case_id (FK)         │            │ case_id (FK)             │
│ action_type (Enum)   │            │ status (Enum)            │
│ target_selector      │            │ output (Text)            │
│ value                │            │ screenshots_path (JSON)  │
│ expected_result      │            │ execution_time (Float)   │
│ order (Integer)      │            │ step_results (JSON)      │
│ description          │            │ created_at               │
│ created_at           │            └──────────────────────────┘
│ updated_at           │
└──────────────────────┘
```

### Action Types (TestStep.action_type)

| Action | Description |
|---|---|
| `NAVIGATE` | Navigate browser to a URL |
| `CLICK` | Click on an element |
| `FILL` | Type text into a form field |
| `ASSERT` | Verify a condition (URL, text, element) |
| `SCREENSHOT` | Capture page screenshot |
| `WAIT` | Wait for an element or a duration |
| `SELECT` | Select a dropdown option |
| `HOVER` | Hover over an element |
| `KEY_PRESS` | Press a keyboard key |
| `SCROLL` | Scroll the page |

### Execution Statuses

| Status | Meaning |
|---|---|
| `PASSED` | All assertions succeeded |
| `FAILED` | One or more assertions failed |
| `ERROR` | Runtime error (e.g., element not found, timeout) |
| `RUNNING` | Currently executing |
| `SKIPPED` | Test was skipped |

---

## 7. API Reference

**Base URL:** `http://localhost:8000/api`

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Platform health check |
| `GET` | `/health/ollama` | Ollama LLM service health (planned) |

### Test Suites

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/test-suites` | Create a new test suite |
| `GET` | `/test-suites` | List all test suites (paginated) |
| `GET` | `/test-suites/{id}` | Get suite with its test cases |
| `PUT` | `/test-suites/{id}` | Update a test suite |
| `DELETE` | `/test-suites/{id}` | Delete suite and all its cases (cascade) |

### Test Cases

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/test-cases` | Create a new test case |
| `GET` | `/test-cases` | List test cases (optional `?suite_id=` filter) |
| `GET` | `/test-cases/{id}` | Get case with steps and execution results |
| `PUT` | `/test-cases/{id}` | Update a test case |
| `DELETE` | `/test-cases/{id}` | Delete case and all its steps (cascade) |

### Test Steps

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/test-steps` | Create a new test step |
| `GET` | `/test-steps` | List test steps (optional `?case_id=` filter) |
| `GET` | `/test-steps/{id}` | Get step details |
| `PUT` | `/test-steps/{id}` | Update a test step |
| `DELETE` | `/test-steps/{id}` | Delete a test step |

### Test Generation (LLM)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/generate-tests` | Generate test cases using LLM from URL + context |

**Request Body:**
```json
{
  "suite_id": 1,
  "target_url": "http://localhost:3000/login",
  "page_context": "Login page with email and password fields",
  "expected_behavior": "User can log in with valid credentials",
  "additional_instructions": "Test both success and failure cases"
}
```

### Test Execution

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/execution/test-cases/{id}/run` | Execute a single test case with Playwright |
| `POST` | `/execution/test-suites/{id}/run` | Execute all cases in a suite |
| `GET` | `/execution/results/{id}` | Retrieve execution results |

### Interactive API Docs

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 8. Frontend Application

### Pages & User Workflows

| Page | Route | Functionality |
|---|---|---|
| **Dashboard** | `/` | System health overview, stats (total suites, cases), API health indicator, quick-start guide |
| **Test Suites** | `/test-suites` | Create/view/delete test suites; each suite has a base URL pointing to the target app |
| **Test Cases** | `/test-cases` | Create/view/delete test cases; filter by suite; expand to view individual test steps |
| **Execute** | `/execute` | Select a suite or case → run tests → view pass/fail results with output logs and execution time |

### Frontend ↔ Backend Communication

- **Protocol:** REST over HTTP (Axios)
- **Base URL:** `http://localhost:8000/api`
- **No authentication** (internal tool)
- **No state management library** — React hooks (`useState`, `useEffect`) are sufficient for this scale

### Design System

- **Color Palette:** Purple gradient theme (`#667eea` → `#764ba2`)
- **Layout:** Card-based UI with responsive CSS Grid
- **Components:** Styled buttons (primary/success/danger), form controls, alert boxes, step lists

---

## 9. Sample E-Commerce Target App

### What Is It?

**TechStore** is a complete e-commerce web application that ships with the platform as a ready-to-test target. It provides realistic user workflows — browsing products, logging in, adding items to cart, checking out, and viewing orders — giving the AI testing agents meaningful scenarios to generate tests against.

### Pages & Test Scenarios

| Page | Route | Key Test Scenarios |
|---|---|---|
| **Home** | `/` | Product grid display, category filtering, product search |
| **Login** | `/login` | Successful login, failed login, redirect after auth |
| **Register** | `/register` | User signup, auto-login after registration |
| **Product Detail** | `/product/:id` | Product info display, quantity selector, add-to-cart |
| **Shopping Cart** | `/cart` | Add/remove items, quantity changes, price calculation |
| **Checkout** | `/checkout` | Shipping form, payment fields, order placement |
| **Order History** | `/orders` | View past orders, order details, status tracking |

### Test Credentials

| Field | Value |
|---|---|
| Email | `test@example.com` |
| Password | `password123` |
| Name | John Doe |
| Address | 123 Main St, New York, NY 10001 |

### Sample Product Inventory

| Product | Price | Category |
|---|---|---|
| Wireless Headphones | $79.99 | Electronics |
| USB-C Cable | $12.99 | Accessories |
| Phone Case | $19.99 | Accessories |
| Portable Charger | $34.99 | Electronics |
| Screen Protector | $9.99 | Accessories |
| Smart Watch | $199.99 | Electronics |

### E-Commerce API (20 Endpoints)

| Group | Endpoints |
|---|---|
| **Auth** | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/profile` |
| **Products** | `GET /api/products`, `GET /api/products/:id`, `GET /api/products/category/:cat` |
| **Cart** | `GET /api/cart`, `POST /api/cart/add`, `POST /api/cart/remove`, `POST /api/cart/clear` |
| **Orders** | `POST /api/orders`, `GET /api/orders`, `GET /api/orders/:id` |
| **Health** | `GET /health`, `GET /api/health` |

---

## 10. Infrastructure & DevOps

### Docker Compose Services

```yaml
# docker-compose.yml
services:
  ollama:              # Ollama LLM Service
    image: ollama/ollama:latest
    port: 11434
    volume: ollama_data (persistent model cache)

  # postgres (optional, commented by default):
  #   image: postgres:16-alpine
  #   port: 5432
```

### Port Map

| Service | Port | Description |
|---|---|---|
| **FastAPI Backend** | 8000 | AI Testing Platform API + Swagger docs |
| **React Frontend** | 3000 | AI Testing Platform Dashboard (Vite dev server) |
| **E-Commerce Backend** | 5000 | TechStore Express.js API |
| **E-Commerce Frontend** | 3000 | TechStore React App (change port if running alongside platform frontend) |
| **Ollama LLM** | 11434 | LLaMA 2 model serving |
| **PostgreSQL** | 5432 | Production database (optional) |

### Directory Layout

```
AI-Agent-Testc/
├── backend/                     # FastAPI Backend (Python)
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Pydantic Settings (env-based config)
│   │   ├── database.py          # SQLAlchemy engine + session factory
│   │   ├── models/              # ORM models (TestSuite, TestCase, TestStep, ExecutionResult)
│   │   ├── schemas/             # Pydantic validation schemas
│   │   ├── routers/             # API endpoint handlers
│   │   ├── services/            # Business logic (LLM, execution, artifacts)
│   │   ├── runners/             # Playwright test execution engines
│   │   └── utils/               # Logger and utilities
│   ├── scripts/init_db.py       # Database init + seed script
│   ├── artifacts/               # Execution outputs (screenshots, videos)
│   ├── generated-tests/         # LLM-generated Playwright test files
│   └── requirements.txt         # Python dependencies
│
├── frontend/                    # React Frontend (Vite)
│   ├── src/
│   │   ├── App.jsx              # Root component + routing
│   │   ├── pages/               # Dashboard, TestSuites, TestCases, Execute
│   │   ├── components/          # Navbar
│   │   ├── services/api.js      # Axios API client
│   │   └── styles/index.css     # Design system
│   ├── package.json
│   └── vite.config.js
│
├── sample-ecommerce/            # Target E-Commerce App
│   ├── backend/                 # Express.js API (in-memory DB)
│   ├── frontend/                # React UI (Create React App)
│   ├── start-app.bat            # Windows startup script
│   ├── start-app.sh             # Linux/Mac startup script
│   └── QUICKSTART.md
│
├── docker-compose.yml           # Ollama + PostgreSQL services
├── README.md                    # Project overview
└── ARCHITECTURE.md              # This file
```

---

## 11. End-to-End Setup Guide

### Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 18+ | Frontend + sample e-commerce app |
| **npm** | 9+ | Package management |
| **Docker** | 20+ | Ollama LLM service (optional for generation features) |
| **Docker Compose** | 2.0+ | Service orchestration |
| **Git** | Any | Clone the repository |

### Step 1 — Clone the Repository

```bash
git clone https://github.com/<your-username>/AI-Agent-Testc.git
cd AI-Agent-Testc
```

### Step 2 — Start the Sample E-Commerce App (Target Under Test)

This is the application the AI platform will generate tests for.

**Windows:**
```bash
cd sample-ecommerce
start-app.bat
```

**Linux / Mac:**
```bash
cd sample-ecommerce
chmod +x start-app.sh
./start-app.sh
```

**Manual (any OS):**
```bash
# Terminal 1 — E-Commerce Backend
cd sample-ecommerce/backend
npm install
npm start
# Runs on http://localhost:5000

# Terminal 2 — E-Commerce Frontend
cd sample-ecommerce/frontend
npm install
npm start
# Runs on http://localhost:3000
```

**Verify:** Open `http://localhost:3000` — you should see the TechStore with products listed.

### Step 3 — Start the Ollama LLM Service (for AI Test Generation)

```bash
# From the project root
docker-compose up -d ollama

# Wait for the container to start, then download the LLaMA 2 model
docker exec ai-test-ollama ollama pull llama2
```

**Verify:** Run `curl http://localhost:11434/api/tags` — you should see `llama2` in the model list.

> **Note:** The initial model download (~4GB) may take several minutes depending on your connection.

### Step 4 — Set Up the FastAPI Backend

```bash
# Terminal 3 — From the project root
cd backend

# Create and activate a Python virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers (one-time)
playwright install

# (Optional) Create a .env file for custom configuration
# cp .env.example .env

# Initialize the database with seed data
python scripts/init_db.py

# Start the FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Or on Windows, use the batch file:**
```bash
cd backend
run_server.bat
```

**Verify:**
- API Root: `http://localhost:8000` — Welcome message
- Swagger Docs: `http://localhost:8000/docs` — Interactive API documentation
- Health Check: `http://localhost:8000/api/health` — `{"status": "ok"}`

### Step 5 — Start the React Frontend (Testing Dashboard)

```bash
# Terminal 4 — From the project root
cd frontend
npm install
npm run dev
```

**Or on Windows, use the batch file:**
```bash
cd frontend
start.bat
```

**Verify:** Open `http://localhost:3000` (or the port shown by Vite) — you should see the AI Testing Platform Dashboard.

> **Port Conflict:** If the e-commerce frontend is already on port 3000, Vite will auto-select another port (usually 3001). Check the terminal output for the actual URL.

### Step 6 — Create Your First Test Suite

1. Open the AI Testing Platform frontend
2. Navigate to **Test Suites**
3. Click **Create New Suite**:
   - **Name:** `E-Commerce Login Tests`
   - **Base URL:** `http://localhost:3000`
   - **Description:** `Test cases for TechStore login functionality`
4. Navigate to **Test Cases**
5. Click **Create New Case**:
   - **Suite:** Select the suite you just created
   - **Name:** `Successful Login`
   - **Path:** `/login`
   - **Description:** `Test logging in with valid credentials`

### Step 7 — Generate Tests with AI (When Implemented)

Use the API to generate test cases:
```bash
curl -X POST http://localhost:8000/api/generate-tests \
  -H "Content-Type: application/json" \
  -d '{
    "suite_id": 1,
    "target_url": "http://localhost:3000/login",
    "page_context": "Login page with email and password fields, submit button",
    "expected_behavior": "User can log in with test@example.com / password123"
  }'
```

### Step 8 — Execute Tests (When Implemented)

```bash
# Run a single test case
curl -X POST http://localhost:8000/api/execution/test-cases/1/run

# Run an entire suite
curl -X POST http://localhost:8000/api/execution/test-suites/1/run

# Check results
curl http://localhost:8000/api/execution/results/1
```

Or use the **Execute** page in the dashboard to run tests visually and see results.

### Quick Reference — All Services Running

| Service | URL | Status Check |
|---|---|---|
| E-Commerce Frontend | http://localhost:3000 | Browse TechStore |
| E-Commerce Backend | http://localhost:5000/health | `{"status": "ok"}` |
| AI Platform Backend | http://localhost:8000/api/health | `{"status": "ok"}` |
| AI Platform Frontend | http://localhost:3000 (or 3001) | Dashboard loads |
| AI Platform Docs | http://localhost:8000/docs | Swagger UI |
| Ollama LLM | http://localhost:11434/api/tags | Model list |

### Stopping Everything

```bash
# Stop Docker services (Ollama)
docker-compose down

# Stop the Python backend: Ctrl+C in Terminal 3
# Stop the React frontend: Ctrl+C in Terminal 4
# Stop e-commerce app: Ctrl+C in Terminals 1 & 2 (or close terminal windows)
```

---

## 12. Project Status & Roadmap

### Current Status

| Layer | Component | Status |
|---|---|---|
| **Database** | Models, migrations, seed script | ✅ Complete |
| **API** | Full CRUD (suites, cases, steps) | ✅ Complete |
| **API** | Test generation endpoint | ⚠️ Endpoint exists, LLM integration pending |
| **API** | Test execution endpoints | ⚠️ Endpoints exist, Playwright runner pending |
| **Frontend** | Dashboard, Suites, Cases pages | ✅ Complete |
| **Frontend** | Execution UI | ✅ Complete |
| **Infrastructure** | Docker Compose (Ollama) | ✅ Complete |
| **Target App** | Sample E-Commerce (TechStore) | ✅ Complete |
| **AI Agents** | Requirement Analyzer | 🔲 Planned |
| **AI Agents** | Page Crawler | 🔲 Planned |
| **AI Agents** | Test Generator | 🔲 Planned |
| **AI Agents** | Step Generator | 🔲 Planned |
| **AI Agents** | Step Reviewer | 🔲 Planned |
| **AI Agents** | Code Generator | 🔲 Planned |
| **Services** | Playwright test execution engine | 🔲 Planned |
| **Services** | Artifact management (screenshots/videos) | 🔲 Planned |

### Planned Enhancements

- **Agent Pipeline Implementation** — Full LangGraph workflow with the 6-agent pipeline
- **Real-time WebSocket Updates** — Live test execution progress in the dashboard
- **Artifact Viewer** — Screenshots, videos, and trace files displayed in the UI
- **PostgreSQL Migration** — Alembic migrations for production database
- **CI/CD Integration** — GitHub Actions for automated test execution
- **Multi-browser Support** — Chromium, Firefox, and WebKit testing
- **Test Report Export** — PDF/HTML test reports with coverage metrics

---

*Last updated: March 2026*
