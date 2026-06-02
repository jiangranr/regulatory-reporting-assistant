# Indicator QA Conversation Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the form-oriented indicator QA page with the conversation workspace from `指标问答-对话.html` while preserving the current backend API and SSE contract.

**Architecture:** Render indicator QA as an immersive page outside the workflow shell. Keep page state local to `IndicatorQAView.vue`: session rail, locked indicator context, message history, evidence cards, suggested follow-ups, quote state, and stream assembly. Keep visual rules in a dedicated prefixed stylesheet.

**Tech Stack:** Vue 3, TypeScript, lucide-vue-next, Vitest, Vue Test Utils, Vite.

---

### Task 1: Add Conversation Workspace Regression Tests

**Files:**
- Create: `frontend/src/views/IndicatorQAView.test.ts`

- [ ] Assert that the view renders a conversation rail, locked context bar, message thread, and docked composer.
- [ ] Assert that creating a new conversation reveals the empty-state prompt.
- [ ] Assert that an SSE response is appended to the conversation after the user sends a question.
- [ ] Run `npm test -- IndicatorQAView.test.ts` and confirm the old form page fails the new expectations.

### Task 2: Build The Immersive Conversation View

**Files:**
- Modify: `frontend/src/views/IndicatorQAView.vue`
- Create: `frontend/src/views/indicator-qa.css`

- [ ] Replace the form layout with the approved two-column workspace.
- [ ] Preserve `GET /api/indicator-qa/items`, `POST /api/indicator-qa/ask/stream`, and `POST /api/reporting/bootstrap-all`.
- [ ] Assemble SSE `meta`, `token`, `keypoints`, `hypotheses`, `lineage`, `done`, and `error` events into assistant messages.
- [ ] Add locked-context switching, new-conversation empty state, session search, quote follow-up, evidence expansion, copy, feedback, and suggested follow-up actions.
- [ ] Run `npm test -- IndicatorQAView.test.ts` and confirm the view regression tests pass.

### Task 3: Enter Immersive Mode From The Application

**Files:**
- Modify: `frontend/src/App.vue`

- [ ] Render `IndicatorQAView` outside `AppShell` when `activePage === "indicator-qa"`.
- [ ] Wire the conversation page breadcrumb back to the dashboard.
- [ ] Run `npm test` and confirm the frontend regression suite passes.
- [ ] Run `npm run build` and confirm TypeScript and Vite production build pass.

### Task 4: Verify The Rendered Page

**Files:**
- No source edits expected.

- [ ] Start the frontend development server.
- [ ] Open `http://127.0.0.1:5173/?page=indicator-qa`.
- [ ] Verify the session rail, context bar, seeded conversation, evidence cards, and composer visually.
- [ ] Click `新建对话` and verify the empty state appears.

