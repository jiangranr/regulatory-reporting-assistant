# Word Revision Hover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render Word tracked changes inline in the portrait signal detail panel with hover metadata.

**Architecture:** Preserve the existing business analysis flow and add a display-only `revision_spans` contract. The backend extracts ordered Word XML spans and attaches matching spans to signal evidence; the frontend renders those spans before falling back to legacy evidence text.

**Tech Stack:** Python, Pydantic, FastAPI schemas, Vue 3, Vitest, `@vue/test-utils`.

---

### Task 1: Backend Word Span Extraction

**Files:**
- Modify: `backend/app/services/instruction_parser.py`
- Test: `backend/tests/test_instruction_parser.py`

- [ ] Add dataclass `RevisionSpan(type, text, author, date, action)`.
- [ ] Add `revision_spans` to `InstructionParseResult`.
- [ ] Write a failing test that builds a minimal docx XML with normal text, historical revisions, latest insertions, and latest deletions.
- [ ] Implement `_extract_docx_revision_spans(docx_content)` by traversing `word/document.xml` paragraph children in order.
- [ ] Apply latest-year behavior: historical INSERT becomes TEXT, historical DELETE is skipped, latest INSERT/DELETE stays marked.
- [ ] Run `uv run pytest backend/tests/test_instruction_parser.py`.

### Task 2: Profile Signal Span Attachment

**Files:**
- Modify: `backend/app/services/document_profiler.py`
- Modify: `backend/app/models/schemas.py`
- Modify: `backend/app/api/routes_documents.py`
- Test: `backend/tests/test_services.py`

- [ ] Add `revision_spans` to `TableChangeSignal` and `TableChangeSignalRead`.
- [ ] Parse a `## 当前版本原位修订片段` block from `document.parsed_text`.
- [ ] Attach matching spans to item definition signals in `_ensure_current_revision_item_definition_signals`.
- [ ] Merge and candidate-source preserve `revision_spans`.
- [ ] Add a test asserting G01 item definition signals include ordered INSERT and DELETE spans.
- [ ] Run `uv run pytest backend/tests/test_services.py`.

### Task 3: Frontend Inline Renderer

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/views/PortraitView.vue`
- Test: `frontend/src/views/PortraitView.test.ts`

- [ ] Add `RevisionSpan` type and `revision_spans?: RevisionSpan[]`.
- [ ] Change detail evidence rendering to use `detailEvidenceSegments(source.signal)` from `revision_spans` first.
- [ ] Render `TEXT` as normal, `INSERT` as blue inline mark, `DELETE` as red deletion mark.
- [ ] Add hover `title` with operation, author, date, and text.
- [ ] Remove the visible “Word 修订动作” action list from details.
- [ ] Add/adjust Vitest cases for inline insertions and deletions.
- [ ] Run `npm test -- --run src/views/PortraitView.test.ts`.

### Task 4: Verification

**Files:**
- No source edits expected.

- [ ] Run backend targeted tests for parser and profiler.
- [ ] Run frontend targeted test.
- [ ] Run frontend build.
- [ ] Re-profile the existing G01 document or inspect current API response after re-scan.
- [ ] Open the local page and verify the detail panel shows inline insertion and deletion hover markers.
