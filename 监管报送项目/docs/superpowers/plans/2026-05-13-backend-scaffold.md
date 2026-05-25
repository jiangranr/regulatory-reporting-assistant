# Backend Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Python backend scaffold for the regulatory reporting assistant.

**Architecture:** Create a FastAPI backend under `backend/` with SQLite persistence through SQLModel, focused service modules, and a small API workflow that supports document upload, task creation, rule extraction, impact analysis, and ticket draft generation. AI behavior is mocked through deterministic services for now so the project can run without an API key.

**Tech Stack:** Python 3.11, FastAPI, SQLModel, SQLite, Pydantic, PyMuPDF/pdfplumber placeholders, Jinja2, pytest, uv.

---

### Task 1: Project Skeleton And Tests

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/README.md`
- Create: `backend/.env.example`
- Create: `backend/tests/test_health.py`
- Create: `backend/tests/test_services.py`
- Create: `backend/tests/test_api_workflow.py`

- [ ] Create Python project metadata and test files first.
- [ ] Run `cd backend && uv sync && uv run pytest -q`.
- [ ] Expected initial result: tests fail because `app` modules do not exist yet.

### Task 2: Core Backend Application

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/models/enums.py`
- Create: `backend/app/models/db_models.py`
- Create: `backend/app/models/schemas.py`

- [ ] Implement app settings, SQLite engine, DB initialization, enums, database models, and Pydantic schemas.
- [ ] Run `cd backend && uv run pytest backend/tests/test_health.py -q`.
- [ ] Expected result: health test passes.

### Task 3: Service Layer

**Files:**
- Create: `backend/app/services/document_parser.py`
- Create: `backend/app/services/rule_extractor.py`
- Create: `backend/app/services/impact_analyzer.py`
- Create: `backend/app/services/ticket_generator.py`

- [ ] Implement deterministic service functions that can be replaced later by real AI orchestration.
- [ ] Run `cd backend && uv run pytest backend/tests/test_services.py -q`.
- [ ] Expected result: service tests pass.

### Task 4: API Routes

**Files:**
- Create: `backend/app/api/routes_health.py`
- Create: `backend/app/api/routes_documents.py`
- Create: `backend/app/api/routes_tasks.py`
- Modify: `backend/app/main.py`

- [ ] Implement health, document, and task workflow APIs.
- [ ] Run `cd backend && uv run pytest -q`.
- [ ] Expected result: all tests pass.

### Task 5: Verification And Handoff

**Files:**
- Modify: `backend/README.md`

- [ ] Document startup commands.
- [ ] Run `cd backend && uv run pytest -q`.
- [ ] Run `cd backend && uv run python -m app.main`.
- [ ] Report created files and next frontend integration boundary.
