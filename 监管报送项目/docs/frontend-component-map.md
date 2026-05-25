# 前端工程与流程设计

> 更新日期：2026-05-14  
> 文档定位：记录 Vue 前端当前页面、核心流程页设计和 API 契约主线。更细的流程化加工与影响判定设计见 `docs/regulatory-workflow-implementation.md`。

## 1. 技术栈

首期前端采用 **Vue 3 + Vite + TypeScript**。

选择 Vue 的原因：

- 更贴合国内银行内部后台系统常见技术生态。
- 对 Java / Spring / 企业后台开发人员更友好。
- 当前页面以表格、表单、状态标签、任务详情为主，适合用 Vue 单文件组件组织。
- 后续如接入 Element Plus、Ant Design Vue 或内部组件库，迁移成本较低。

## 2. 页面定位

前端页面按“入口、主流程、资产沉淀”组织。

| 页面 | 组件文件 | 定位 |
|---|---|---|
| 工作台 | `frontend/src/views/DashboardView.vue` | 查看任务总览、风险提醒和待处理事项 |
| 发文任务 | `frontend/src/views/DocumentsView.vue` | 上传监管发文、查看发文列表、创建规则加工任务 |
| 任务详情流程页 | `frontend/src/views/TaskDetailView.vue` | 核心页面，按五步展示监管发文加工链路 |
| 规则资产 | `frontend/src/views/RuleLibraryView.vue` | 查看已沉淀规则卡片、条款证据和规则引用 |
| 数据模型与映射 | `frontend/src/views/MetadataMappingView.vue` | 查看 1104 报表对象、指标字段、数据字段血缘和责任团队映射 |
| 复核工单 | `frontend/src/views/ReviewTicketView.vue` | 查看待复核项、退回项和工单草稿 |

建议菜单收敛为：

```text
工作台
发文任务
规则资产
数据模型与映射
复核工单
```

## 3. 核心流程页

`TaskDetailView.vue` 是后续前端改造重点。用户进入某个任务后，应看到五步流程：

```text
上传发文 -> 条款证据 -> 语义识别 -> 影响分析 -> 规则与工单
```

页面建议结构：

```text
顶部：任务摘要
  - 发文标题
  - 当前步骤
  - 风险等级
  - 处理进度

中部：五步流程条
  上传发文 -> 条款证据 -> 语义识别 -> 影响分析 -> 规则与工单

主体：步骤内容区
  - 上传发文：文件信息、解析状态、文本摘要、文档级任务画像
  - 条款证据：入选条款编号、原文、来源位置、入选原因、证据状态
  - 语义识别：主体、业务、动作、约束、风险点
  - 影响分析：影响对象、系统、字段、流程、风险等级、影响理由
  - 规则与工单：规则卡片草稿、校验规则候选、工单草稿、复核状态

侧边：证据链与操作区
  - 当前依据
  - 识别理由
  - 待复核项
  - 下一步操作
```

## 4. 前端主流程

当前已跑通的旧闭环可作为技术基础，但不再作为目标用户流程：

```text
上传发文 -> 创建任务 -> 抽取规则 -> 影响分析 -> 生成工单草稿
```

后续调整为更清晰的用户侧主流程：

```text
上传发文 -> 条款证据 -> 语义识别 -> 影响分析 -> 规则与工单
```

前端不再把多个“库”作为主操作路径，而是以任务流程呈现。首期页面重点突出影响分析，规则卡片和工单草稿作为“规则与工单”步骤中的沉淀与落地辅助输出。底层制度库、条款证据库、监管语义库、监管数据模型库、校验规则库和规则卡片库作为过程资产支撑。

上传发文步骤只展示文档级初筛结果，不展示最终影响结论。建议展示：

| 字段 | 说明 |
|---|---|
| 监管制度记录 | 文件标题、发文机构、文号、发布日期、来源、解析状态 |
| 解析文本摘要 | 正文摘要、页数、段落数、表格数量、解析质量 |
| 加工任务状态 | 任务编号、当前步骤、处理状态、复核状态 |
| 文档级任务画像 | 文件类型、候选领域、疑似数据治理影响方向、建议处理路线、初步判断依据 |

前端文案需要明确：任务画像是系统初筛，不是最终影响判断。最终是否影响数据治理在“影响分析”步骤确认。

条款证据步骤展示的是“入选条款证据”，不是监管全文的全部条款。监管全文在上传发文步骤的解析文本中展示，条款证据只展示被系统初步判定可能有业务处理价值的原文片段，并标明入选原因和复核状态。

## 5. 当前 API 契约

前端 API client：

```text
frontend/src/api/client.ts
```

当前已对接接口：

| 前端方法 | 后端接口 | 用途 |
|---|---|---|
| `listDocuments()` | `GET /api/documents` | 查询监管发文列表 |
| `uploadDocument(file)` | `POST /api/documents/upload` | 上传监管发文 |
| `listTasks()` | `GET /api/tasks` | 查询任务列表 |
| `createTaskFromDocument(documentId)` | `POST /api/tasks/from-document/{document_id}` | 从发文创建监管报送影响分析任务 |
| `getTaskWorkflow(taskId)` | `GET /api/tasks/{task_id}/workflow` | 查询五步流程页聚合数据 |
| `seedReportingCatalog()` | `POST /api/reporting/seed-1104` | 初始化 1104 资金同业报表目录、指标字段、数据字段和血缘样板 |
| `listReportingObjects()` | `GET /api/reporting/objects?reporting_system_code=1104` | 查询 1104 报表对象 |
| `listReportingItems()` | `GET /api/reporting/items?reporting_system_code=1104` | 查询 1104 指标字段 |
| `getReportingItemLineage(itemCode)` | `GET /api/reporting/items/{item_code}/lineage` | 查询报送指标到报送字段、源字段、维度字段的血缘 |

## 6. 流程聚合 API

为了支撑五步流程页，前端优先使用任务聚合接口：

```text
GET /api/tasks/{task_id}/workflow
```

用途：

| 数据 | 用途 |
|---|---|
| `task` | 展示任务标题、状态、风险等级 |
| `document` | 展示发文信息和解析摘要 |
| `steps` | 驱动五步流程条状态 |
| `clauses` | 展示入选条款证据 |
| `semantic_items` | 展示监管语义 |
| `reporting_candidates` | 展示命中的报送体系、报表对象、指标字段、变更类型和证据 |
| `lineage_candidates` | 展示命中的报送字段、源系统字段、维度字段和血缘角色 |
| `impact_items` | 展示影响指标、报送字段、源字段、血缘角色、建议动作和风险等级 |
| `rule_cards` | 展示规则卡片草稿 |
| `ticket_drafts` | 展示工单草稿 |

后续可按需要补充：

| 接口 | 用途 |
|---|---|
| `POST /api/tasks/{task_id}/run-step/{step_code}` | 统一触发条款切分、语义识别、影响分析、规则与工单生成 |
| `PATCH /api/reporting/impact-items/{impact_item_id}/review` | 复核报送影响项 |
| `GET /api/tasks/{task_id}/ticket-drafts` | 查询任务下工单草稿 |

## 7. 首期改造重点

| 优先级 | 改造项 | 说明 |
|---|---|---|
| P0 | 改造 `TaskDetailView.vue` | 将任务详情页改成五步流程页 |
| P0 | 增加流程 Mock 数据 | 后端聚合接口完成前，保证页面可演示 |
| P0 | 展示语义识别结果 | 主体、业务、动作、约束、风险点 |
| P0 | 展示影响分析结果 | 明确影响、可能影响、仅作参考、不相关，并展示影响范围 |
| P0 | 展示规则与工单草稿 | 规则卡片草稿、工单草稿和复核状态 |
| P1 | 增加 `workflow` API client | 对接后端聚合接口 |
| P1 | 调整菜单命名 | 将用户入口收敛为工作台、发文任务、规则资产、数据模型与映射、复核工单 |

## 8. 当前边界

- 当前后端 AI 能力仍是确定性 Mock。
- 当前页面可优先请求后端接口；后端未启动时可降级展示本地样例数据。
- 首期前端重点是把主流程讲清楚，不做复杂规则引擎配置界面。
