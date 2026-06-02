# Hallucination Governance P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add measurable, reviewable hallucination controls for document change signals without disrupting existing profile consumers.

**Architecture:** Keep document profiling responsible for extracting signals, and add a focused `hallucination_guard` service for grounding classification, metrics aggregation, downstream eligibility, reviews, and audit logging. Preserve `evidence_verified` for compatibility while adding graded grounding fields. Expose document-level metrics and review APIs, then surface the result in `PortraitView`.

**Tech Stack:** FastAPI, SQLModel, Pydantic, Vue 3, TypeScript, Vitest, Pytest.

---

### Task 1: Grounding Classification

**Files:**
- Create: `backend/app/services/hallucination_guard.py`
- Modify: `backend/app/services/document_profiler.py`
- Test: `backend/tests/test_hallucination_guard.py`

- [ ] Write failing tests for `VERIFIED`, `PARTIAL`, `UNVERIFIED`, and `RULE_BASED`.
- [ ] Run `uv run pytest tests/test_hallucination_guard.py -q` and verify failure.
- [ ] Implement normalized evidence coverage and compatibility fields.
- [ ] Run `uv run pytest tests/test_hallucination_guard.py -q` and verify pass.

### Task 2: Review Persistence And Metrics API

**Files:**
- Modify: `backend/app/models/db_models.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/routes_documents.py`
- Test: `backend/tests/test_hallucination_guard_api.py`

- [ ] Write failing API tests for metrics aggregation and signal review.
- [ ] Run `uv run pytest tests/test_hallucination_guard_api.py -q` and verify failure.
- [ ] Add `RegSignalReview`, metrics response schemas, review payload schema, API handlers, and `AuditLog` writes.
- [ ] Run `uv run pytest tests/test_hallucination_guard_api.py -q` and verify pass.

### Task 3: Downstream Isolation

**Files:**
- Modify: `backend/app/services/reporting_change_extractor.py`
- Test: `backend/tests/test_reporting_services.py`

- [ ] Write a failing test proving `UNVERIFIED` LLM signals do not become downstream changes.
- [ ] Run the targeted test and verify failure.
- [ ] Filter only isolated LLM signals while preserving rule-based signals and compatibility with historical rows.
- [ ] Run the targeted test and verify pass.

### Task 4: Portrait Trust Visualization

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/PortraitView.vue`
- Modify: `frontend/src/views/PortraitView.test.ts`

- [ ] Write failing Vitest coverage for trust metrics, graded status chips, and review actions.
- [ ] Run `npm test -- --run src/views/PortraitView.test.ts` and verify failure.
- [ ] Add the trust summary, graded chips, review buttons, and metrics refresh behavior.
- [ ] Run `npm test -- --run src/views/PortraitView.test.ts` and verify pass.

### Task 5: Verification

- [ ] Run targeted backend tests.
- [ ] Run `uv run pytest -q`.
- [ ] Run `npm test -- --run`.
- [ ] Run `npm run build`.
- [ ] Run `uv run ruff check app tests scripts` and report any pre-existing or remaining issues separately.
