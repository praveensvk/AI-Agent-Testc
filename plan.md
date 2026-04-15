# Plan: Test Generation Platform (AI-Agent-Test)

## Executive Summary

Build a multi-agent LLM-powered platform that converts natural-language test descriptions into executable Playwright test suites.

**Core workflow:** User describes a test case → backend agents analyze requirements, crawl the target app (via Playwright MCP), generate & review test steps → execute steps directly with playwright-python → user views live results, screenshots, videos via WebSocket.

**MVP scope:** Desktop browsers only (Chrome/Firefox/WebKit), single user, sequential test execution, no auth.

**Architecture:** FastAPI (Python agents + orchestration) + Next.js frontend (TypeScript) + PostgreSQL + local artifact storage + WebSocket for real-time updates.

**Current status:** Phases 1–5 complete. Phase 7 (test runner overhaul) in progress — replacing subprocess-based execution with direct Python Playwright and MCP-based crawling.

---

## Key Decisions (from alignment session)

| Decision | MVP Choice | Rationale |
|----------|-----------|-----------|
| Device Support | Desktop only | Simpler agent logic & Playwright setup; mobile in phase 2 |
| Real-time Feedback | WebSocket | Better UX for live agent progress & headed browser viewing |
| Playwright Execution | In-process FastAPI workers | Simpler deployment; artifact access; scale later with separate service |
| Artifact Storage | Local filesystem + DB refs | Good for MVP; cloud storage (S3) in phase 2 |
| Agent Visibility | Backend internal only | Clean API; agents not exposed as individual endpoints |
| Error Recovery | Auto-retry with re-verification loop | Max 3 attempts; improve quality without user intervention |
| Parallel Execution | Sequential MVP | Simplify orchestration; parallelization in post-launch phase |
| Multi-tenant Auth | Not in MVP | Single workspace focus; auth added later |
| TestStep Persistence | Stored in DB | Enable inspection, editing, re-generation workflows |
| Crawler Tool | Playwright MCP | Accessibility snapshot for richer element discovery; falls back to subprocess |
| Test Execution | playwright-python (direct) | Execute TestSteps via Python Playwright API; eliminates TypeScript/npm dependency |
| Test Case Editing | Enabled | Users can refine generated steps post-generation |

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1–2) ✅ COMPLETE
Database schema, ORM models, API scaffolding, basic agent structure.

#### Steps

1. **Set up project structure**
   - Backend: FastAPI app with `/app/models`, `/app/schemas`, `/app/services`, `/app/agents`, `/app/routers`
   - Frontend: Next.js project with `/app/pages`, `/app/components`, `/app/types`
   - Shared: Define TypeScript types for domain models

2. **Design and implement PostgreSQL schema**
   - Tables: `test_suites`, `test_cases`, `test_steps`, `test_runs`, `artifacts`
   - Include metadata (status, timestamps, configuration, FK relationships)
   - Migrations: Use Alembic for schema versioning

3. **Create SQLAlchemy 2.0 ORM models**
   - Map to domain concepts: `TestSuite`, `TestCase`, `TestStep`, `TestRun`, `Artifact`
   - Use relationships to enforce structure (suite → cases → steps, run → artifacts)

4. **Define Pydantic v2 schemas (DTOs)**
   - Request schemas: `CreateTestSuiteRequest`, `CreateTestCaseRequest`, `GenerateTestRequest`
   - Response schemas: `TestSuiteResponse`, `TestCaseResponse`, `TestRunResponse`
   - Nested schemas for TestSteps, Artifacts, run metadata

5. **Scaffold FastAPI routers**
   - `/test-suites`: POST (create), GET (list), GET by ID
   - `/test-suites/{id}/test-cases`: POST (create), GET (list)
   - `/test-cases/{id}/generate`: POST (trigger generation)
   - `/test-runs`: POST (trigger run), GET (list/filter by status/suite/date)
   - `/test-runs/{id}`: GET (status/artifacts), WebSocket endpoint for live updates
   - Placeholder handlers; no business logic yet

6. **Set up development environment**
   - Local PostgreSQL (Docker Compose for easy setup)
   - FastAPI + uvicorn for development
   - Next.js dev server
   - Playwright installed in backend virtualenv

**Completion criteria:**
- Database migrations run cleanly
- FastAPI server starts and returns 200 on health check
- Next.js frontend page renders
- TypeScript types compile without errors

---

### Phase 2: Test Requirement & Step Generation Agents (Weeks 3–4) ✅ COMPLETE

Implement core agent logic: analyze requirements, crawl the app, generate test steps.

#### Steps

7. **Create Test Requirement Analyzer Agent**
   - LangChain/LangGraph node
   - Input: natural-language test case description + TestSuite context (app description, base URL)
   - Output: Pydantic model `StructuredTestIntent` (goals, pages, preconditions, assertions, edge cases)
   - Prompt engineering: Use few-shot examples; emphasize clarity and specificity
   - Config: Store LLM model choice (e.g., GPT-4), temperature in env vars

8. **Implement Page Crawler using Playwright**
   - Utility module: crawl target URL, extract DOM structure and selectors
   - Start from base URL, capture:
     - Page title, URL, visual layout
     - Interactive elements: buttons, inputs, links (role-based + text-based selectors)
     - Form structures (fields, labels, validation hints)
   - Respect robots.txt and rate limits; timeout handling
   - Output: Pydantic `PageSnapshot` (page_url, raw_html, structured_elements)

9. **Create Step Generator Agent**
   - LangChain/LangGraph node
   - Input: `StructuredTestIntent` + list of `PageSnapshot` objects (from crawler)
   - Uses DOM info to map user intent → concrete Playwright actions
   - Output: list of `TestStep` objects:
     - `step_id`, `order`, `action` (click, type, navigate, wait, expect), `selector`, `value`, `expected_result`
   - Prompt: "Given the DOM of the app and the test intent, generate steps. Prefer stable selectors (role, test-id, accessible name)."

10. **Build Re-verification Agent & Loop**
    - Node in LangGraph that compares generated steps to original intent
    - Input: `StructuredTestIntent` vs. generated steps
    - Output: Pass/Fail + feedback for re-generation
    - Loop logic:
      - If steps are complete and aligned: return success
      - If gaps detected (missing pages, assertions, edge cases): recommend adjustments
      - Feed feedback back to Step Generator
      - Max 3 iterations; if still failing, return with confidence score and warning
    - Track iteration count and reasons for re-runs in logs

11. **Compose LangGraph workflow**
    - Analyzer → Crawler → StepGen → ReVerifier (loop)
    - Define graph structure with clear input/output ports
    - Handle failures gracefully: log detailed traces
    - Return workflow output: validated TestSteps or error with user-friendly message

12. **Create service layer for test generation**
    - File: `app/services/test_generation.py`
    - Function `generate_test_case_steps(suite_id, case_description)`:
      - Fetch TestSuite from DB
      - Run LangGraph workflow
      - Store generated TestSteps in DB with status/metadata
      - Return list of TestSteps
    - Error handling: database rollback, logging, user notifications

**Completion criteria:**
- LangGraph workflow compiles and executes
- Crawler successfully inspects a test app (e.g., sample e-commerce site)
- Step Generator produces valid Playwright action objects
- Re-verification loop respects max iteration count and returns meaningful feedback
- Generated TestSteps stored in DB with full traceability

---

### Phase 3: Test Code Generation & Playwright Integration (Weeks 5–6) ✅ COMPLETE

Convert TestSteps into executable Playwright + TypeScript tests.

#### Steps

13. **Create Test Generator Agent**
    - Converts validated `TestStep` list → Playwright + TypeScript test code
    - Generates:
      - Single spec file per TestCase: `{suite_id}_{case_id}.spec.ts`
      - Clear test.describe() groups by TestSuite
      - Readable test names
      - Helper functions for page interactions (Page Object Model patterns, if complex)
      - Proper assertions using expect()
    - Stability rules:
      - Default to role/aria label selectors; fallback to test-id
      - Generate waits (waitForSelector, waitForNavigation) where appropriate
      - Screenshot on failure; optional: all runs
    - Output: Pydantic `GeneratedTest` (file_path, code_content, imports, test_metadata)

14. **Implement test file output service**
    - File: `app/services/test_output.py`
    - Function `generate_and_save_test_code(case_id, test_steps)`:
      - Call Test Generator Agent
      - Write spec files to `/generated-tests/{suite_id}/{case_id}.spec.ts`
      - Store file paths + metadata in DB (Artifact records or similar)
      - Return paths for preview and execution

15. **Create Playwright configuration manager**
    - File: `app/services/playwright_config.py`
    - Generate `playwright.config.ts` dynamically with:
      - testDir: `/generated-tests`
      - Base URL from TestSuite
      - Desktop projects: chromium, firefox
      - Screenshot/video on failure (configurable)
      - Timeout and retry settings
    - Store config in persistent location accessible to test runner

16. **Integrate with test file generation workflow**
    - Update test generation service to:
      1. Generate steps
      2. Generate test code
      3. Validate syntax (TypeScript compile check)
      4. Report any code generation errors to user
    - Add error recovery: if code generation fails, return steps + advice for manual refinement

**Completion criteria:**
- Generated .spec.ts files are syntactically valid TypeScript
- Files use stable selectors and best Playwright practices
- Playwright.config can be generated and read by test runner
- Full test generation pipeline (from requirements → code) works end-to-end

---

### Phase 4: Test Execution & Orchestration (Weeks 7–8) ✅ COMPLETE (being overhauled in Phase 7)

Run tests, capture results, store artifacts.

#### Steps

17. **Create Test Execution & Orchestration Agent**
    - Manages Playwright test runs
    - Input: TestRun record (case_id, browser choice: chromium|firefox|webkit, headed/headless)
    - Process:
      - Create test result record in DB
      - Spin up Playwright runner (async subprocess or worker pool)
      - Capture stdout/stderr/test results
      - On failure: collect screenshot, trace
      - On completion: parse Playwright JSON report
      - Update TestRun status (pending → running → passed/failed)
    - Output: TestRun record + artifact paths

18. **Implement artifact capture & storage**
    - Directories: `/artifacts/{run_id}/` (screenshots, videos, traces, logs)
    - Service: `app/services/artifact_manager.py`
    - Functions:
      - `capture_artifacts(run_id)`: collect from Playwright run
      - `store_artifact_metadata(run_id, artifact_type, path)`: persist to DB
      - `get_artifacts_for_run(run_id)`: retrieve for UI display
    - Each Artifact record: type (screenshot|video|trace|log), run_id, file_path, mimetype

19. **Build API endpoint for test execution**
    - POST `/test-runs`: Create run and trigger execution
      - Body: { case_id, browser, headed (boolean) }
      - Response: { run_id, status: 'queued' }
    - GET `/test-runs/{id}`: Check status, return artifacts
    - Implement polling/WebSocket updates (below)

20. **Implement WebSocket for live updates**
    - Endpoint: `/ws/test-runs/{id}`
    - Sends updates during test execution:
      - { event: 'status_change', status: 'running|passed|failed', timestamp }
      - { event: 'test_step', step: 'Clicked button', screenshot_url: '...' }
      - { event: 'artifact_ready', artifact: { type, url } }
    - Frontend subscribes to WebSocket for real-time UI updates

21. **Create worker pool / async execution**
    - Option A (MVP): Use FastAPI background tasks + asyncio
    - Option B (future): Celery + Redis queue
    - For MVP: queue runs, execute sequentially/controlled concurrency
    - Track active runs in memory/cache; persist state to DB on start/stop

**Completion criteria:**
- Tests execute headless and headed (output visible/reported)
- Screenshots and videos captured on failure
- TestRun records updated with final status
- Artifacts stored and retrievable
- WebSocket sends live updates to connected clients

---

### Phase 5: Frontend UI & Integration (Weeks 9–10) ✅ COMPLETE

Next.js frontend for suite/case management, generation, and execution viewing.

#### Steps

22. **Design and implement pages/components**
    - **Dashboard/Home**: List TestSuites (cards with app name, base URL, case count)
    - **Suite Detail**: List TestCases under a suite, button to create new case
    - **Create Suite Modal**: Form for app description + base URL
    - **Create TestCase Modal**: Text area for natural-language test description; submit button
    - **Generation Progress**: Loading spinner + agent status updates (via WebSocket)
    - **Test Step Preview**: Table view of generated steps (readable action descriptions)
    - **Test Run List**: Filter/sort by suite, status, date; links to results
    - **Test Run Detail**: Live status during execution; display captured screenshots/videos in gallery; summary (passed/failed assertions)
    - **Code Preview**: Show generated `.spec.ts` file (read-only, syntax highlighted)

23. **Create React context/stores for state management**
    - Global state for current suite, case, run selections
    - API calls via custom hooks (useTestSuites, useTestRun, etc.)
    - Keep state minimal; fetch from API as primary source of truth

24. **Implement API client (Axios or fetch)**
    - Functions for each endpoint: createSuite, getTestRuns, triggerGeneration, etc.
    - Handle errors, loading states, retries

25. **Add WebSocket client**
    - Connect to `/ws/test-runs/{id}` when user views run details
    - Update UI in real-time as events arrive
    - Cleanup on component unmount

26. **Build styling**
    - Use Tailwind CSS (or preferred CSS framework)
    - Consistent design: cards, buttons, modals, alerts
    - Responsive layout for desktop (mobile in future phase)

**Completion criteria:**
- All major user flows work end-to-end
- UI updates in real-time during generation and test execution
- Users can create suites, add test cases, view results
- Code preview and artifact viewing functional

---

### Phase 6: Integration Testing, Polish & Documentation (Weeks 11–12)

End-to-end testing, refinement, and deployment prep.

#### Steps

27. **Write integration tests**
    - Backend: Test suite → case creation → generation → execution (full pipeline)
    - Playwright tests for frontend critical paths (create suite, run test, view results)
    - Use sample e-commerce app or simple test target

28. **Fix edge cases and error handling**
    - Network timeouts, malformed responses
    - Invalid selectors (crawler can't find elements)
    - Large test suites (pagination, performance)
    - Concurrent requests (rate limiting on LLM calls)

29. **Performance tuning**
    - Agent response times (cache prompts, optimize LLM calls)
    - Database query optimization (indexes on frequent queries)
    - Frontend bundle size and load times

30. **Documentation**
    - Backend API docs (FastAPI auto-generated + guides)
    - Frontend component storybook or style guide
    - Agent workflow diagrams and prompts
    - Setup instructions for local dev and deployment
    - Architecture decision records (ADRs)

31. **Deploy to staging environment**
    - Docker Compose or cloud setup (e.g., AWS ECS, Azure App Service, Render)
    - Environment variables for api keys, database, LLM config
    - Test against real target applications

**Completion criteria:**
- All major features tested and working
- Documentation complete
- Staging deployment successful
- Ready for MVP launch

---

### Phase 7: Test Runner Overhaul — MCP Crawler + Python Playwright Execution 🔄 IN PROGRESS

Fix critical frontend bug, replace subprocess-based crawler with Playwright MCP, replace npx subprocess test execution with direct playwright-python step execution.

#### Background / Motivation

The existing test runner (Phase 4) generates TypeScript `.spec.ts` files and executes them via `npx playwright test` subprocess. This adds complexity:
- Requires npm/npx, `@playwright/test` package, TypeScript compilation
- Generated per-run config files, spec file lookups, dependency installation
- Windows asyncio + subprocess compatibility issues
- Frontend runs page has an infinite re-render bug blocking the UI

**New approach:**
- **Crawler**: Use Playwright MCP server (`@playwright/mcp`) for accessibility-based element discovery during step generation
- **Execution**: Execute `TestStep` objects directly using `playwright` Python async API — no TypeScript, no npm, no subprocess
- **Code Export**: Keep code_generator.py as optional "Export to .spec.ts" feature

#### Steps

32. **Fix React infinite re-render bug**
    - File: `frontend/src/app/runs/[id]/page.tsx`
    - Bug: `refetch()` called directly in render body (not inside `useEffect`), causing infinite loop
    - Fix: Wrap in `useEffect` with `[run?.status, events]` dependencies

33. **Create Playwright MCP client wrapper**
    - New file: `backend/app/services/mcp_browser.py`
    - Start `@playwright/mcp` as subprocess via stdio transport
    - Async context manager for lifecycle management
    - Expose: `navigate(url)`, `snapshot()`, `screenshot()`, `click(ref)`, `type(ref, text)`
    - Add `playwright_mcp_command` setting to `backend/app/config.py`

34. **Update crawler to use Playwright MCP**
    - File: `backend/app/services/crawler.py`
    - Replace subprocess Playwright with MCP client
    - `crawl_page(url)` → MCP `browser_navigate(url)` + `browser_snapshot()`
    - Parse accessibility snapshot into existing `PageSnapshot` schema
    - Extract interactive elements with semantic roles + names
    - Fallback to current subprocess crawler if MCP unavailable

35. **Create Python Playwright step executor**
    - New file: `backend/app/services/step_executor.py`
    - `execute_steps(steps, browser, base_url, run_id, headed) → ExecutionResult`
    - Launch browser via `async_playwright().start()` → `browser_type.launch(headed=headed)`
    - Browser context with: video recording, tracing, screenshot-on-failure
    - Action mapping:
      - `navigate` → `page.goto(step.value or base_url)`
      - `click` → `page.locator(step.selector).click()`
      - `type` → `page.locator(step.selector).press_sequentially(step.value)`
      - `fill` → `page.locator(step.selector).fill(step.value)`
      - `verify_text` → `expect(page.locator(step.selector)).to_contain_text(step.expected_result)`
      - `verify_element` → `expect(page.locator(step.selector)).to_be_visible()`
      - `wait` → `page.wait_for_selector(step.selector)` or `page.wait_for_load_state(step.value)`
      - `screenshot` → `page.screenshot(path=artifact_dir/step.description.png)`
    - Per-step try/except, screenshot on failure, continue remaining steps
    - After all steps: stop tracing, close context (saves video), collect artifacts

36. **Replace subprocess execution with step executor**
    - File: `backend/app/services/test_execution.py`
    - Remove: `_find_spec_file()`, `_generate_run_config()`, `_ensure_playwright_deps()`, subprocess logic
    - New flow:
      1. Fetch `TestStep` objects from DB (ordered by `order`)
      2. Get suite's `base_url`
      3. Call `step_executor.execute_steps()`
      4. Broadcast step-by-step progress via WebSocket (each step result)
      5. Collect artifacts (screenshots, video, trace) from execution result
      6. Update TestRun record in DB
    - Keep: WebSocket broadcasting, artifact collection, DB update logic

37. **Auto-install Playwright browsers**
    - On first execution attempt, auto-run `playwright install chromium firefox webkit`
    - Similar to existing `_ensure_playwright_deps()` but for Python Playwright browsers

**Completion criteria:**
- [ ] Frontend `/runs/{id}` page loads without infinite re-render crash
- [ ] Crawler uses MCP accessibility snapshot for element discovery
- [ ] Test execution runs directly from TestStep objects via playwright-python
- [ ] No TypeScript/npm/subprocess dependency for test execution
- [ ] Screenshots, videos, and traces captured and displayed in UI
- [ ] WebSocket broadcasts step-by-step progress during execution
- [ ] All three browsers work (chromium, firefox, webkit)
- [ ] Headed mode works
- [ ] Code export (`.spec.ts`) still available as optional feature

---

## Agent Pipeline (Current Architecture)

The platform uses a 6-agent pipeline orchestrated by LangGraph:

```
NL Test Description
     │
     ▼
┌─────────────────────┐
│  1. Requirement      │  requirement_analyzer.py
│     Orchestrator     │  Decomposes NL → sub-goals, pages, assertions
│     (Plan-and-       │  Output: StructuredTestIntent
│      Execute)        │  LLM: Ollama (qwen2.5-coder:7b)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  2. Page Crawler     │  crawler.py (→ mcp_browser.py in Phase 7)
│     (Playwright MCP) │  Visit pages, extract DOM/accessibility snapshot
│                      │  Output: list[PageSnapshot]
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  3. Step Generator   │  step_generator.py
│     (ReAct)          │  Goals + DOM → executable Playwright actions
│                      │  Actions: navigate, click, type, fill, verify_text,
│                      │           verify_element, wait, screenshot
│                      │  Output: list[GeneratedTestStep]
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐     ┌──── If rejected & iteration < 3 ────┐
│  4. Step Reviewer    │     │     Feed back to Step Generator      │
│     (Reverifier)     │─────┘     with issues_found + fixes        │
│                      │◄──────────────────────────────────────────┘
│                      │  Validates selectors against real DOM
│                      │  Output: StepReviewResult (approved, fixed_steps,
│                      │          confidence)
└─────────┬───────────┘
          │ (approved)
          ▼
┌─────────────────────┐
│  5. Test Generator   │  test_generator.py
│     (IEEE 829)       │  Reviewed steps → structured test case docs
│                      │  Output: TestDesignOutput
│                      │  (TC-ID, Title, Category, Priority, Steps, Expected)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  6. Code Generator   │  code_generator.py  (OPTIONAL — export only)
│     (TypeScript)     │  Reviewed steps → Playwright .spec.ts file
│                      │  Output: GeneratedTest (file_name, code_content)
│                      │  Fallback: template-based if LLM fails
└─────────────────────┘
```

### Agent Files

| # | Agent | File | Input | Output |
|---|-------|------|-------|--------|
| 1 | Requirement Orchestrator | `backend/app/agents/requirement_analyzer.py` | NL description + app context | `StructuredTestIntent` (goals, pages, assertions, edge_cases) |
| 2 | Page Crawler | `backend/app/services/crawler.py` | base_url + page paths | `list[PageSnapshot]` (DOM, interactive elements, forms) |
| 3 | Step Generator (ReAct) | `backend/app/agents/step_generator.py` | `StructuredTestIntent` + `PageSnapshot` list | `list[GeneratedTestStep]` (action, selector, value, expected) |
| 4 | Step Reviewer | `backend/app/agents/reverifier.py` | Generated steps + page snapshots | `StepReviewResult` (approved, fixed_steps, confidence, issues) |
| 5 | Test Generator (IEEE 829) | `backend/app/agents/test_generator.py` | Approved steps + intent + snapshots | `TestDesignOutput` (IEEE 829 test cases) |
| 6 | Code Generator | `backend/app/agents/code_generator.py` | Reviewed `TestStep` list | `GeneratedTest` (file_name, code_content, imports) |

### Workflow Orchestration

- **File**: `backend/app/agents/workflow.py`
- **Engine**: LangGraph `StateGraph` with typed state
- **Flow**: Orchestrator → Crawler → StepGen → Reviewer → (loop up to 3×) → TestGen
- **Re-verification loop**: If reviewer rejects steps, feedback is fed back to StepGen (max 3 iterations)
- **Service layer**: `backend/app/services/test_generation.py` orchestrates the workflow + persists to DB

### Key Schemas (Pydantic)

| Schema | Module | Fields |
|--------|--------|--------|
| `StructuredTestIntent` | `schemas/agent.py` | goals, pages, preconditions, assertions, edge_cases |
| `PageSnapshot` | `schemas/agent.py` | page_url, raw_html, structured_elements |
| `GeneratedTestStep` | `schemas/agent.py` | order, action, selector, value, expected_result, description |
| `StepReviewResult` | `schemas/agent.py` | approved, fixed_steps, issues_found, selector_fixes, confidence |
| `IEEE829TestCase` | `schemas/agent.py` | tc_id, title, category, priority, test_steps, expected_results |
| `TestDesignOutput` | `schemas/agent.py` | Wrapper for `list[IEEE829TestCase]` |
| `GeneratedTest` | `schemas/agent.py` | file_name, code_content, imports, test_metadata |

---

## Critical Files to Create/Modify

### Backend (FastAPI + Python)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app, middleware, WebSocket setup
│   ├── config.py                         # Environment config, LLM setup, MCP settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── test_suite.py                 # SQLAlchemy ORM: TestSuite
│   │   ├── test_case.py                  # SQLAlchemy ORM: TestCase
│   │   ├── test_step.py                  # SQLAlchemy ORM: TestStep
│   │   ├── test_run.py                   # SQLAlchemy ORM: TestRun
│   │   └── artifact.py                   # SQLAlchemy ORM: Artifact
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── test_suite.py                 # Pydantic DTOs: CreateTestSuiteRequest, TestSuiteResponse
│   │   ├── test_case.py                  # Pydantic DTOs: CreateTestCaseRequest, TestCaseResponse
│   │   ├── test_run.py                   # Pydantic DTOs: TestRunResponse, RunStatusUpdate
│   │   └── agent.py                      # StructuredTestIntent, PageSnapshot, TestStep, IEEE829, etc.
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── test_suites.py                # Routes: POST/GET /test-suites, GET /test-suites/{id}
│   │   ├── test_cases.py                 # Routes: POST/GET /test-suites/{id}/test-cases
│   │   ├── test_runs.py                  # Routes: POST/GET /test-runs, GET /test-runs/{id}, WebSocket
│   │   └── generation.py                 # Routes: POST /test-cases/{id}/generate, GET status, code
│   ├── services/
│   │   ├── __init__.py
│   │   ├── test_generation.py            # Orchestrate workflow + persist to DB
│   │   ├── test_output.py                # Code generation and file output (.spec.ts)
│   │   ├── test_execution.py             # Test run orchestration (calls step_executor)
│   │   ├── step_executor.py              # NEW (Phase 7): Direct playwright-python step execution
│   │   ├── mcp_browser.py                # NEW (Phase 7): Playwright MCP client wrapper
│   │   ├── crawler.py                    # Page crawler (MCP-based, fallback to subprocess)
│   │   ├── artifact_manager.py           # Artifact capture and storage
│   │   ├── playwright_config.py          # Playwright config generation (legacy, for code export)
│   │   └── ws_manager.py                 # WebSocket connection manager
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── requirement_analyzer.py       # Agent 1: NL → StructuredTestIntent
│   │   ├── step_generator.py             # Agent 3: Intent + DOM → GeneratedTestSteps (ReAct)
│   │   ├── reverifier.py                 # Agent 4: Step Reviewer / Validator (loop)
│   │   ├── test_generator.py             # Agent 5: IEEE 829 Test Case Generator
│   │   ├── code_generator.py             # Agent 6: Steps → TypeScript .spec.ts (optional export)
│   │   └── workflow.py                   # LangGraph state machine (5-agent pipeline)
│   └── utils/
│       ├── __init__.py
│       └── output_parser.py              # Robust Pydantic LLM output parser
├── migrations/
│   └── versions/
│       ├── 001_initial_schema.py         # Alembic migration
│       └── (more migrations as needed)
├── tests/
│   ├── __init__.py
│   ├── test_agents.py                    # Agent unit tests
│   └── test_integration.py               # End-to-end integration tests
├── requirements.txt                       # Dependencies
├── .env.example                           # Environment template
└── pyproject.toml                         # Python project config (optional)
```

### Frontend (Next.js + TypeScript + React)

```
frontend/
├── app/
│   ├── page.tsx                          # Dashboard/Home (list suites)
│   ├── suites/
│   │   ├── page.tsx                      # Suite list page
│   │   └── [id]/
│   │       ├── page.tsx                  # Suite detail page
│   │       └── cases/
│   │           ├── page.tsx              # Test cases list
│   │           └── new/
│   │               └── page.tsx          # Create new test case
│   ├── runs/
│   │   ├── page.tsx                      # Test runs list
│   │   └── [id]/
│   │       └── page.tsx                  # Test run detail (live results)
│   ├── components/
│   │   ├── SuiteCard.tsx                 # Reusable suite card component
│   │   ├── TestStepTable.tsx             # Generated test steps view
│   │   ├── RunResults.tsx                # Run results and artifacts gallery
│   │   ├── CodePreview.tsx               # Syntax-highlighted code viewer
│   │   ├── WebSocketUpdater.tsx          # WebSocket client component
│   │   ├── CreateSuiteModal.tsx          # Modal for suite creation
│   │   ├── CreateCaseModal.tsx           # Modal for test case creation
│   │   └── LoadingSpinner.tsx            # Reusable spinner
│   ├── hooks/
│   │   ├── useTestSuites.ts              # Hook for suite CRUD operations
│   │   ├── useTestRun.ts                 # Hook for run fetching and monitoring
│   │   ├── useWebSocket.ts               # Hook for WebSocket connection
│   │   └── useApi.ts                     # Generic API hook with error handling
│   ├── services/
│   │   ├── api.ts                        # Axios/fetch API client
│   │   ├── ws.ts                         # WebSocket client and event emitter
│   │   └── types.ts                      # API response types
│   ├── types/
│   │   └── index.ts                      # Domain types (TestSuite, TestCase, TestRun, Artifact, etc.)
│   ├── lib/
│   │   ├── utils.ts                      # Utility functions
│   │   └── constants.ts                  # Constants and config
│   ├── styles/
│   │   ├── globals.css                   # Global styles
│   │   └── (Tailwind config in tailwind.config.js)
│   └── layout.tsx                        # Root layout
├── public/
│   └── (static assets)
├── tailwind.config.js                    # Tailwind CSS config
├── tsconfig.json                         # TypeScript config
├── next.config.js                        # Next.js config
├── package.json                          # Dependencies
└── .env.example                          # Environment template
```

### Database & Infrastructure

```
root/
├── docker-compose.yml                    # Local dev environment (PostgreSQL, backend, frontend)
├── .env.example                          # Environment template (API keys, DB creds, etc.)
├── generated-tests/                      # Directory for generated .spec.ts files
│   └── (auto-populated by backend)
├── artifacts/                            # Directory for test artifacts (screenshots, videos, logs)
│   └── (auto-populated by backend during test runs)
└── migrations/
    ├── env.py                            # Alembic config
    ├── script.py.mako                    # Alembic template
    ├── versions/
    │   ├── 001_initial_schema.py
    │   └── (more migrations as schema evolves)
    └── alembic.ini                       # Alembic config file
```

---

## Validation Checklist

### Phase 1: Foundation
- [x] Database migrations run cleanly with no errors
- [x] FastAPI server starts; health check returns HTTP 200
- [x] Next.js frontend dev server runs and renders a page
- [x] TypeScript types compile without `errors`
- [x] All models and schemas instantiate correctly

### Phase 2: Agent Development
- [x] Requirement Analyzer Agent produces valid `StructuredTestIntent` objects
- [x] Crawler successfully fetches and parses sample app (e.g., e-commerce site)
- [x] Step Generator produces ordered `TestStep` objects with valid action/selector pairs
- [x] Re-verification loop completes in ≤3 iterations for test cases
- [x] End-to-end test generation runs without errors; steps logged clearly

### Phase 3: Code Generation
- [x] Generated `.spec.ts` files have valid TypeScript syntax
- [x] Files import Playwright test utilities correctly
- [x] `playwright.config.ts` is generated with correct testDir, base URL, browser projects
- [x] `npx playwright test` can execute generated tests without syntax errors

### Phase 4: Test Execution
- [x] TestRun record creates in DB when execution triggered
- [x] Playwright tests execute in headless and headed modes
- [x] Screenshots/videos captured on failure; paths stored in DB
- [x] WebSocket sends at least 3 event types (status_change, test_step, artifact_ready)
- [x] TestRun status transitions: pending → running → passed/failed

### Phase 5: Frontend Integration
- [x] All pages load without JavaScript errors
- [x] Create suite form submits and creates DB record
- [x] Create test case form triggers generation; progress UI displays
- [x] WebSocket updates appear in real-time (no page refresh needed)
- [x] Test run results display screenshots/videos in gallery
- [x] Code preview shows generated .spec.ts with syntax highlighting

### Phase 6: End-to-End & Polish
- [ ] Full pipeline test (create suite → create case → generate → run → view results)
- [ ] Integration test suite passes
- [ ] Documentation complete and accurate
- [ ] No console errors or warnings in dev tools
- [ ] Staging deployment healthy and responsive

### Phase 7: Test Runner Overhaul
- [ ] React infinite re-render bug fixed on `/runs/{id}` page
- [ ] Playwright MCP client wrapper created and configured
- [ ] Crawler uses MCP accessibility snapshot (with subprocess fallback)
- [ ] Step executor directly executes TestSteps via playwright-python
- [ ] test_execution.py uses step_executor (no npx subprocess)
- [ ] Screenshots, videos, traces captured and visible in UI
- [ ] WebSocket broadcasts step-by-step progress
- [ ] All browsers work (chromium, firefox, webkit) + headed mode
- [ ] Code export `.spec.ts` still available via API

---

## Post-Launch Metrics

- Generated test pass rate: ≥95% (low flakiness)
- Generation time: <30 seconds per test case (average)
- Test execution time: <5 minutes per test run (average)
- API uptime: ≥99%
- WebSocket latency: <100ms for event delivery

---

## Architectural Decisions & Rationale

| Decision | Choice | Why |
|----------|--------|-----|
| **LLM Model** | Ollama (qwen2.5-coder:7b) | Local inference; no API costs; configurable model |
| **LangGraph Workflow** | Sequential agents with boundaries | Easy to debug, test, monitor; clear separation of concerns |
| **Re-verification Loop** | Structured feedback, max 3 iterations | Balance quality with UX; prevent infinite loops |
| **Playwright Execution** | Direct playwright-python from TestSteps | Eliminates TypeScript/npm/subprocess; steps already in DB |
| **Page Crawling** | Playwright MCP accessibility snapshot | Richer semantic data; fallback to subprocess Playwright |
| **Artifact Storage** | Local filesystem + DB references | Practical for MVP; S3/cloud integration in phase 2 |
| **Agent Visibility** | Backend internal only | Clean RESTful API; debugging endpoints added if needed in future |
| **Error Recovery Strategy** | Auto-retry with feedback loop | Improve quality without user manual rework (max 3 attempts) |
| **TestStep Persistence** | Store in DB | Enable post-generation inspection, editing, re-use, audit trails |
| **Crawler Technology** | Playwright MCP (fallback: subprocess) | Accessibility snapshot for better element discovery; semantic roles |
| **Test Case Editing** | Enable post-generation refinement | Better UX; users can fix unstable selectors or logic errors |
| **Real-time Updates** | WebSocket over polling/SSE | Best UX for live progress; headed browser viewing; event-driven |
| **Testing Framework** | playwright-python (execution) + Playwright TS (optional export) | Direct Python execution for reliability; TS export for CI/CD integration |

---

## Excluded from MVP (Deliberate Scope)

- [ ] Multi-user accounts and authentication
- [ ] Mobile device emulation (tablets, phones)
- [ ] Parallel test execution within a TestRun
- [ ] CI/CD pipeline integration (GitHub Actions, GitLab CI, etc.)
- [ ] Cloud artifact storage (AWS S3, Azure Blob)
- [ ] Custom agent prompt tuning UI
- [ ] Historical analytics and trend reporting
- [ ] Load testing or performance profiling
- [ ] Visual regression testing
- [ ] API test generation (only UI tests in MVP)

---

## Dependencies & Tech Stack

### Backend (Python)
- FastAPI, Uvicorn (web framework)
- SQLAlchemy 2.0 (ORM)
- Alembic (database migrations)
- Pydantic v2 (data validation)
- LangChain, LangGraph (agent orchestration)
- LangChain-Ollama (local LLM integration)
- Playwright (async, for crawling and execution)
- MCP SDK (Playwright MCP client for crawling)
- Ollama (local LLM — qwen2.5-coder:7b)
- python-dotenv (config management)
- httpx (async HTTP client)
- pytest (testing)

### Frontend (Next.js)
- Next.js 14+ (React framework)
- TypeScript (type safety)
- React hooks (state management)
- Tailwind CSS (styling)
- Axios or native fetch (HTTP client)
- WebSocket API (real-time updates)
- Syntax highlighter (code preview, e.g., Prism or highlight.js)

### Database
- PostgreSQL 14+ (relational database)
- Alembic (migrations)

### Infrastructure (Dev & Prod)
- Docker & Docker Compose (containerization, local dev)
- Git (version control)

---

## Further Considerations

### 1. LLM Cost & Budget Management
- OpenAI GPT-4 API calls will incur costs. Estimate usage by:
  - Requirement Analyzer: ~1 call per test case creation
  - Step Generator: ~1-2 calls per case (plus re-verification retries)
  - Test Code Generator: ~1 call per case
  - Total: ~3-5 calls per test case (with retries)
- Implement usage tracking and quotas in Phase 2.
- Consider fallback to GPT-3.5 Turbo for non-critical agents to reduce cost.
- Set per-user monthly limits if multi-tenant support added.

### 2. Generated Test Flakiness & Stability
- Dynamic element IDs and JavaScript-rendered content can cause selector instability.
- Plan for a feedback loop (Phase 2+):
  - Users report failed runs
  - Log which selectors failed
  - Provide UI for manual selector refinement
  - Allow user to re-run generation with refined selector hints
- Implement periodic "health checks": scheduled runs of past test cases to detect regression.

### 3. Sample Target Application
- Use the existing sample e-commerce app (in your `sample-ecommerce/` folder) for development and integration testing.
- Ensure the app is always available (Docker, background process, or public URL).
- Consider creating a minimal test landing page (form, buttons, links) for sanity checks.

### 4. Security & API Rate Limiting
- Rate limit API endpoints to prevent abuse (LLM API costs, database load).
- Use FastAPI's built-in rate limiting or a library like `slowapi`.
- Validate and sanitize user inputs (test descriptions, URLs).
- Never log sensitive data (API keys, user content).

### 5. Scalability Path (Post-MVP)
- **Parallel Execution:** Switch from sequential to async execution queue (Celery + Redis or RQ).
- **Multi-tenancy:** Add user accounts, workspace isolation, per-user quotas.
- **Cloud Artifacts:** Migrate to S3 or Azure Blob; keep DB references.
- **Distributed Agents:** Deploy agents on separate services if latency becomes an issue.
- **Caching:** Cache crawled pages and generated steps to reduce API calls.

### 6. Monitoring & Observability
- Log all agent execution steps (request → response) for debugging.
- Track API latencies and error rates.
- Monitor database query performance and connection pooling.
- Collect metrics: test pass rate, generation success rate, execution times.
- Use structured logging (JSON) for easier log parsing.

---

## Getting Started

1. **Confirm alignment:** Does this plan align with your vision? Any changes before implementation?
2. **Set up workspace:** Clone/fork the repo; initialize Python venv and Node environments.
3. **Phase 1:** Start with database schema and API scaffolding.
4. **Iterative delivery:** Complete one phase before moving to the next; validate at each stage.
5. **Feedback loop:** Test with real target applications early (Phase 3+).

---

**Last updated:** March 9, 2026
