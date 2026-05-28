# Execution Planner Frontend — Codex Tasks (D5 / D6)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the frontend rendering surface (`ExecutionPlanCard.vue`) and shared test fixtures for Module D · AI 工单执行规划 (Ticket Execution Planner). Backend D1–D4 (prompt, service, DDL, API) is handled by Claude in parallel; this plan covers D5 (UI card) and D6 (mock fixtures both sides use).

**Architecture:** A new card surfaces inside `ReviewTicketView.vue` above the existing sub-tabs region. The card renders 4 sections — executive summary, phased task plan, critical risks, team coordination notes — driven by a stable JSON shape returned from `GET /api/tasks/{task_id}/execution-plan`. Empty / loading / error states all have explicit UI. No backend coupling beyond the API contract below.

**Tech Stack:** Vue 3 + `<script setup lang="ts">`, TypeScript strict, Tailwind via existing project utility classes, lucide-vue-next icons, vitest + @vue/test-utils.

---

## Scope Boundary

**In scope (Codex):**
- D5: New `ExecutionPlanCard.vue` component + integration into `ReviewTicketView.vue`.
- D6: Shared mock fixtures (TypeScript + Python) capturing 3 representative `ExecutionPlan` shapes.

**Out of scope (Claude is doing in parallel):**
- Backend service `ticket_execution_planner.py`.
- Prompt template `backend/app/prompts/execution_planner_v1.md`.
- DB table `RegTaskExecutionPlan` and DDL backfill.
- API endpoints (`POST /api/tasks/{task_id}/execution-plan`, `GET …`, `POST …/feedback`).

**Do not change** existing ticket workbench layout, severity signals row, sub-tabs nav, or `routes_tasks.py`. The card is **additive** — slots in above the sub-tabs region.

---

## API Contract (frozen)

The backend will expose:

```
GET /api/tasks/{task_id}/execution-plan
```

Response (200 OK, no plan yet):
```json
{ "status": "NOT_GENERATED", "plan": null }
```

Response (200 OK, plan exists):
```json
{
  "status": "READY",
  "plan": {
    "task_id": 123,
    "executive_summary": "本次 G24 同业融入口径调整涉及 3 个责任系统、4 个子单，预计 2–3 周完成；关键路径为源系统改造 → ETL 字段映射 → 报送系统回归。",
    "estimated_duration": "2-3 周",
    "execution_phases": [
      {
        "phase_name": "第 1 周（关键路径）",
        "tasks": [
          {
            "team": "SOURCE_SYSTEM",
            "team_zh": "源系统",
            "action": "在交易主表新增 borrow_party_type 字段并补 R01-R10 历史数据",
            "ticket_id": 5012,
            "is_blocker": true,
            "blocker_reason": "下游 ETL 依赖该字段"
          }
        ]
      }
    ],
    "critical_risks": [
      {
        "severity": "HIGH",
        "description": "境外法人机构口径在源系统未单独打标",
        "ticket_id_ref": 5012,
        "mitigation": "由数据治理平台先出口径解释表，再源系统改造"
      }
    ],
    "team_coordination": "建议每周三 16:00 由数据治理平台牵头召集 30 分钟同步会，跨系统口径分歧 24 小时内决策升级到 PMO。",
    "generated_at": "2026-05-28T10:32:00Z",
    "generated_by": "planner_v1@2026-05-28",
    "confidence": 0.82,
    "needs_human_review": false
  }
}
```

Response (200 OK, generation failed and fell back to skeleton):
```json
{
  "status": "DEGRADED",
  "plan": { /* same shape, confidence ≤ 0.4, needs_human_review: true */ },
  "warning": "LLM 调用 2 次失败，已返回骨架规划，请人工补充"
}
```

Field semantics:

| Field | Type | Notes |
|---|---|---|
| `status` | `"NOT_GENERATED" \| "READY" \| "DEGRADED" \| "STALE"` | `STALE` 表示工单已修改但规划未刷新 |
| `executive_summary` | string | ≤ 200 字 |
| `estimated_duration` | string | 形如 `"2-3 周"`，永远是区间 |
| `execution_phases[].phase_name` | string | 形如 `"第 1 周（关键路径）"` |
| `execution_phases[].tasks[].team` | enum string | 7 个责任系统枚举之一（见 `ResponsibleSystem`） |
| `execution_phases[].tasks[].team_zh` | string | 团队中文显示名 |
| `execution_phases[].tasks[].ticket_id` | number | 必须能在父任务的子单清单里找到 |
| `execution_phases[].tasks[].is_blocker` | boolean | 是否阻塞下一阶段 |
| `critical_risks[].severity` | `"HIGH" \| "MEDIUM" \| "LOW"` | |
| `critical_risks[].ticket_id_ref` | number \| null | 风险绑定到具体子单或 null |
| `confidence` | number | 0–1，前端显示百分比 |
| `needs_human_review` | boolean | true 时显示"待人工复核"徽章 |

There is **also**：

```
POST /api/tasks/{task_id}/execution-plan
```
Body: `{}`. Triggers (re)generation. Returns the same READY/DEGRADED shape.

```
POST /api/tasks/{task_id}/execution-plan/feedback
```
Body: `{ "thumbs": "up" | "down", "comment": "<optional>" }`. Returns `{ "ok": true }`.

---

## File Structure

### Frontend Files

- Modify `监管报送项目/frontend/src/types/api.ts`
  - Add `ExecutionPlan`, `ExecutionPhase`, `ExecutionTask`, `CriticalRisk`, `ExecutionPlanResponse` types.
- Create `监管报送项目/frontend/src/components/ExecutionPlanCard.vue`
  - Renders the 4 sections plus generate / regenerate / feedback controls.
- Modify `监管报送项目/frontend/src/views/ReviewTicketView.vue`
  - Slot `<ExecutionPlanCard>` between the severity signals row and the sub-tabs nav.
- Create `监管报送项目/frontend/src/components/__tests__/ExecutionPlanCard.test.ts`
  - Vitest suite covering empty / loading / READY / DEGRADED / error states.
- Create `监管报送项目/frontend/src/fixtures/executionPlan.ts`
  - 3 fixture exports: `EXECUTION_PLAN_HAPPY`, `EXECUTION_PLAN_DEGRADED`, `EXECUTION_PLAN_NOT_GENERATED`.

### Backend Fixture Files (shared with Claude's D2/D4)

- Create `监管报送项目/backend/tests/fixtures/execution_plan_samples.py`
  - Pydantic-validated dicts mirroring the 3 frontend fixtures one-for-one.

---

## Task 5: ExecutionPlanCard.vue (D5)

**Files:**
- Modify: `监管报送项目/frontend/src/types/api.ts`
- Create: `监管报送项目/frontend/src/components/ExecutionPlanCard.vue`
- Modify: `监管报送项目/frontend/src/views/ReviewTicketView.vue`
- Create: `监管报送项目/frontend/src/components/__tests__/ExecutionPlanCard.test.ts`

### Step 5.1: Add TypeScript types

- [ ] Add `ExecutionTask`, `ExecutionPhase`, `CriticalRisk`, `ExecutionPlan`, `ExecutionPlanResponse` to `frontend/src/types/api.ts` matching the JSON shape above. Use union literal types for `status` and `severity`. Export everything.

### Step 5.2: Render core component

- [ ] Create `ExecutionPlanCard.vue` as `<script setup lang="ts">` component. Props:
  ```ts
  defineProps<{
    taskId: number
    initial?: ExecutionPlanResponse | null
  }>()
  ```
- [ ] Fetch via `GET /api/tasks/{taskId}/execution-plan` on mount when `initial` not provided.
- [ ] States to render explicitly:
  - **NOT_GENERATED**: "尚未生成执行规划" 提示 + "AI 生成规划" 按钮（POST 触发，loading 时禁用 + spinner）。
  - **READY**: 4 sections (executive_summary / execution_phases / critical_risks / team_coordination) + "重新生成" 链接 + 👍/👎 反馈按钮。
  - **DEGRADED**: 同 READY，但顶部 amber 横幅显示 `warning` 文案 + "待人工复核" 徽章。
  - **STALE**: 顶部蓝色横幅 "工单已更新，规划可能过时，建议重新生成"。
- [ ] Loading skeleton during fetch + POST.
- [ ] Error toast (use existing project pattern) on network failure; retain last good state.

### Step 5.3: Detailed section rendering

- [ ] **Executive summary**: 单行 box，左侧大字 estimated_duration，右侧 paragraph。
- [ ] **Execution phases**: 折叠展开式，默认全部展开。每个 phase 是一个 table（team / action / ticket / blocker badge）。Blocker 用红色徽章。team_zh 加 team 枚举徽章（小字）。
- [ ] **Critical risks**: 列表卡片，severity 用颜色徽章（HIGH=红, MEDIUM=橙, LOW=灰）。点击 ticket_id_ref 应跳转到对应子单（暂时用 anchor `#ticket-${id}` 即可，路由后续接）。
- [ ] **Team coordination**: 简单 paragraph，pre-wrap。
- [ ] 顶部右侧显示 `confidence` 百分比 + `generated_by` 小字。

### Step 5.4: Generate / regenerate / feedback

- [ ] "AI 生成规划" / "重新生成" 都走 `POST /api/tasks/{taskId}/execution-plan`，等待响应后刷新视图。loading 期间禁用按钮。
- [ ] 反馈按钮调 `POST /api/tasks/{taskId}/execution-plan/feedback`，body `{ thumbs: "up" | "down" }`，成功后按钮变灰且显示"已反馈"。

### Step 5.5: Integrate into ReviewTicketView

- [ ] 在 `ReviewTicketView.vue` 中，把 `<ExecutionPlanCard :task-id="parentTicket.task_id" />` 插入到 `tv2-signals` 区块下方、`sub-tabs` 上方。
- [ ] 仅当存在 parent ticket 且 `parentTicket.task_id` 有效时渲染。
- [ ] 在 emit 列表里不要新增事件 —— 卡片自洽。

### Step 5.6: Vitest

- [ ] 5 个测试用例对应 5 个状态：NOT_GENERATED / READY / DEGRADED / STALE / 网络错误。
- [ ] mock `fetch` 用 `vi.fn`，用 fixture 数据。
- [ ] 断言：状态徽章正确显示 / 阶段数 / 风险数 / 反馈按钮调用了正确 endpoint。

### Step 5.7: Verification

- [ ] `cd 监管报送项目/frontend && npm run typecheck`
- [ ] `cd 监管报送项目/frontend && npm run test -- ExecutionPlanCard`
- [ ] 视觉冒烟（如果有 Storybook 直接看，没有就跑 dev server 手动塞 mock 数据看一眼）。

---

## Task 6: Shared Fixtures (D6)

**Files:**
- Create: `监管报送项目/frontend/src/fixtures/executionPlan.ts`
- Create: `监管报送项目/backend/tests/fixtures/execution_plan_samples.py`

### Step 6.1: Frontend fixtures

- [ ] `executionPlan.ts` exports 3 const fixtures matching `ExecutionPlanResponse`:
  - `EXECUTION_PLAN_HAPPY`: status=READY, 3 phases, 2 risks, confidence=0.82, needs_human_review=false. 取材："G24 同业融入口径调整"。
  - `EXECUTION_PLAN_DEGRADED`: status=DEGRADED, 1 phase（骨架）, 0 risks, confidence=0.35, needs_human_review=true, warning 文案。
  - `EXECUTION_PLAN_NOT_GENERATED`: status=NOT_GENERATED, plan=null。
- [ ] 确保所有 `ticket_id` 都引用 `5011 / 5012 / 5013 / 5014` 这 4 个虚拟子单 ID（Claude 在后端 fixture 里用同样的 ID）。
- [ ] 顶部加注释指向 `backend/tests/fixtures/execution_plan_samples.py`，强调"前后端形状必须同步"。

### Step 6.2: Backend fixtures

- [ ] `execution_plan_samples.py` 用 dict 字面量定义 3 个等价 fixtures（不引入 Pydantic 依赖以保持轻量），导出 `HAPPY_PLAN_DICT / DEGRADED_PLAN_DICT / NOT_GENERATED_DICT`。
- [ ] 同样的 ticket_id 引用。
- [ ] 顶部加注释指向前端文件，强调"前后端形状必须同步，改一边记得改另一边"。

### Step 6.3: Cross-check

- [ ] 手工 diff 两个文件确保结构 1:1 对齐：字段名一致、ticket_id 列表一致、severity 字面量一致。

---

## Definition of Done

- [ ] 前端 typecheck 通过
- [ ] `ExecutionPlanCard.test.ts` 5 个用例全过
- [ ] `ReviewTicketView.vue` 集成后旧功能不退化（手动点一遍工单切换 / 子标签）
- [ ] 两个 fixture 文件存在且字段 1:1 对齐
- [ ] 不修改 `routes_tasks.py`、`reporting_ticket_generator.py`、`ticket_card_builder.py` 或其他 Claude 在做的后端文件
- [ ] Commit message 格式：`feat(planner): D5 ExecutionPlanCard.vue / D6 fixtures（前后端 fixture 同步）`

---

## Open Questions for Codex

如果实施过程中遇到以下情况，**先暂停问 Claude/江秋萍**：

1. `ReviewTicketView.vue` 当前是 table v2 (`tv2-tbl`) 布局，插入位置如果对样式造成破坏，先停下来。
2. 如果发现 `parentTicket.task_id` 字段在现有 types 里不存在，先停下来核实数据流。
3. 反馈按钮的样式如果与 ImpactView 现有 thumbs 控件不一致，倾向于复用 ImpactView 的。
