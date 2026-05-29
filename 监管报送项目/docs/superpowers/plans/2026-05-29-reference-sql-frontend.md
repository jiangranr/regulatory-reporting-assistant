# Reference SQL Frontend — Codex Tasks (Q6 / Q7 / Q8)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans，逐 Task 用 checkbox 跟踪。
> **设计依据**：`2026-05-29-reference-sql-generator.md`（后端 Q1-Q5/Q9/Q10 已落地）。

**Goal:** 在每张「系统子单」卡片底部加一个「参考 SQL」区块（`ReferenceSqlCard.vue`），用 monaco editor 展示/编辑 AI 生成的 SQL，支持生成 / 重新生成 / 复制 / 编辑保存 / 反馈，并诚实处理 NOT_APPLICABLE 空态。后端 API 已就绪，按契约对接即可。

**Tech Stack:** Vue 3 `<script setup lang="ts">`、TypeScript strict、`@guolao/vue-monaco-editor`、lucide-vue-next、vitest + @vue/test-utils。

---

## Scope Boundary

**In scope（Codex）:**
- Q6 `ReferenceSqlCard.vue` 新组件 + monaco editor 集成
- Q7 集成进 `ReviewTicketView.vue` 的系统子单卡片
- Q8 fixture + vitest

**Out of scope（不要碰）:**
- 任何 `backend/` 文件——后端 5 个 API 已完成
- `ExecutionPlanCard.vue` / `ImpactScopeReview.vue` 的现有逻辑

---

## API 契约（已实现，前端按此对接）

所有路径前缀 `/api/tickets/{ticket_id}`。

### GET `/reference-sql` — 读当前状态
```json
{
  "ticket_id": 101,
  "status": "NOT_GENERATED",   // NOT_GENERATED / READY / DEGRADED / EDITED_BY_USER / STALE / NOT_APPLICABLE
  "ability": "",               // CAN_GENERATE / PARTIAL / VALIDATION_ONLY / NOT_APPLICABLE
  "reference_sql": "",
  "sql_dialect": "ANSI",
  "confidence": 0.0,
  "explanation": "",
  "assumptions": [],
  "warnings": [],
  "not_applicable_reason": "",
  "generated_at": null,
  "generated_by": ""
}
```

### POST `/reference-sql/generate` — 生成/重新生成（同步，可能 5-30 秒）
返回同 GET 结构。注意 `explanation` 和 `assumptions` 只在本次 POST 响应里有，GET 不持久化返回。

NOT_APPLICABLE 时立即返回（不调 LLM），`status` 与 `ability` 均为 `NOT_APPLICABLE`，`not_applicable_reason` 为人话说明。

### PUT `/reference-sql` — 保存人工编辑
请求体 `{ "reference_sql": "...", "comment": "" }`，返回同 GET 结构，`status` 变 `EDITED_BY_USER`。

### POST `/reference-sql/feedback`
请求体 `{ "thumbs": "up" | "down", "comment": "" }`，返回 `{ "ok": true }`。

### POST `/reference-sql/mark-stale`
无 body，把 status 置 STALE（业务复核更新后调用）。返回同 GET 结构。

### warning 项结构
```json
{
  "type": "FIELD_NOT_IN_SCOPE | TABLE_NOT_IN_CATALOG | SYNTAX_ERROR | LLM_FAILED",
  "message": "字段 xxx 未在业务勾选清单内…",
  "field_code": "xxx",
  "severity": "ERROR | WARNING | INFO"
}
```

---

## Task Q6: ReferenceSqlCard.vue

**Files:**
- Modify `frontend/src/types/api.ts`
- Modify `frontend/package.json`（加 `@guolao/vue-monaco-editor` + `monaco-editor`）
- Create `frontend/src/components/ReferenceSqlCard.vue`
- Create `frontend/src/components/__tests__/ReferenceSqlCard.test.ts`

### Q6.1 TypeScript 类型
- [ ] 加 `SqlWarning`、`ReferenceSqlResponse` 类型，字面量联合：`status` / `ability` / `severity`。导出。

### Q6.2 monaco 依赖
- [ ] `npm i @guolao/vue-monaco-editor monaco-editor`
- [ ] 全局或局部注册 monaco loader（CDN 或 vite worker 均可；优先 vite 本地 worker 避免离线环境断网）。

### Q6.3 组件 props
```ts
defineProps<{
  ticketId: number
  initial?: ReferenceSqlResponse | null
}>()
```
- [ ] mount 时若无 `initial` 则 GET 拉取。

### Q6.4 按状态渲染（6 态，全部显式处理）
- [ ] **NOT_GENERATED**：占位文案 + `[🤖 AI 生成]` 按钮
- [ ] **NOT_APPLICABLE**：⚪ 灰色块 + `not_applicable_reason`，**不显示编辑器、不显示生成按钮**（见设计稿 §3.6）
- [ ] **READY**：SQL 高亮（monaco 只读态）+ `confidence` 百分比 + `[♻️ 重新生成][📋 复制][✏️ 编辑][👍/👎]` + warnings 列表 + explanation/assumptions（折叠）
- [ ] **DEGRADED**：同 READY，顶部红色横幅"AI 生成参考 SQL 已降级，请人工审核"（语法错或 LLM 失败时）
- [ ] **EDITED_BY_USER**：同 READY，标"已人工编辑"
- [ ] **STALE**：顶部蓝色横幅"影响范围已更新，建议重新生成"
- [ ] 生成中：monaco 区域显示 skeleton/进度，按钮禁用

### Q6.5 VALIDATION_ONLY 文案
- [ ] `ability === "VALIDATION_ONLY"` 时，标题"对账校验 SQL"，顶部一行说明"本 SQL 用于核对两侧口径一致性（差异比对），非取数逻辑"。

### Q6.6 warnings 渲染
- [ ] 按 severity 着色：ERROR 红 / WARNING 黄 / INFO 灰。
- [ ] `FIELD_NOT_IN_SCOPE` / `TABLE_NOT_IN_CATALOG` 显示 `field_code` 高亮，文案提示"AI 可能写错或需补充勾选"。

### Q6.7 编辑态
- [ ] 点 `[✏️ 编辑]` → monaco 切到可编辑，出现 `[取消][💾 保存]`。
- [ ] 保存调 PUT，成功后回只读态，状态变 EDITED_BY_USER。

### Q6.8 顶部红色横幅（始终存在）
- [ ] READY/DEGRADED/EDITED 态顶部恒显"⚠️ AI 参考 SQL，必须人工审核后才能用于生产"，**不提供"一键执行"按钮**。

### Q6.9 重新生成二次确认
- [ ] `[♻️ 重新生成]` 弹确认框（"会覆盖当前 SQL 含人工编辑"），确认后调 POST generate。

### Q6.10 vitest
- [ ] 覆盖 6 态渲染 + 生成/编辑/反馈三个 POST/PUT 调用断言（mock fetch）。

---

## Task Q7: 集成进 ReviewTicketView

**Files:** Modify `frontend/src/views/ReviewTicketView.vue`

- [ ] 在「系统子单」详情卡片底部（业务备注区下方）插入 `<ReferenceSqlCard :ticket-id="child.id" />`。
- [ ] 仅当 `child.id` 有效时渲染。
- [ ] 不新增 emit，组件自洽。
- [ ] 业务复核「确认并重新生成工单」后，旧子单被替换，无需手动 mark-stale（新子单 status 自然是 NOT_GENERATED）。若实现了"业务改影响范围但不重新生成工单"的路径，再对存量子单调 mark-stale。

---

## Task Q8: fixture + 联调

**Files:** Create `frontend/src/fixtures/referenceSql.ts`

- [ ] 4 个 fixture：`SQL_NOT_GENERATED`、`SQL_READY`（含 2 条 warning）、`SQL_NOT_APPLICABLE`、`SQL_DEGRADED`。
- [ ] vitest 用 fixture 驱动，不依赖真实后端。
- [ ] 顶部注释指向后端 `app/models/schemas.py::ReferenceSqlResponse`，强调前后端形状同步。

---

## Definition of Done
- [ ] `npm run typecheck` 通过
- [ ] `ReferenceSqlCard.test.ts` 全过
- [ ] 集成后旧功能不退化（点一遍工单切换 / 执行规划卡 / 业务复核）
- [ ] 不改任何 backend 文件
- [ ] commit：`feat(sql): Q6-Q8 ReferenceSqlCard.vue + monaco 集成`

## Open Questions（遇到先停下来问）
1. monaco 在当前 vite 配置下 worker 打包是否顺利？若卡 worker 配置先停。
2. `child.id` 在现有 ticket 数据结构里的确切字段名（是 `id` 还是 `ticket_id`）。
3. 现有卡片样式系统（tv2-*）与 monaco 默认主题是否冲突。
