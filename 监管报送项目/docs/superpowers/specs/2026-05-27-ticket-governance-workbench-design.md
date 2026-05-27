# 工单治理工作台改造设计

> 日期：2026-05-27  
> 项目：监管报送变更影响分析与工单助手  
> 范围：工单生成、工单展示、职责拆分、数据治理资产沉淀  
> 状态：待用户复核  

## 1. 结论

本次改造不把目标定义为“让 AI 写出更长、更完整的工单正文”，而是把工单模块升级为“监管变更落地任务编排与数据治理资产沉淀”。

现有逻辑不推倒重来。保留当前母子单、`ticket_drafts.content`、`generate-ticket` 接口、`workflow` 聚合接口和旧 Markdown 输出作为兼容回退；新增结构化工单字段、触发器驱动拆单、系统责任分组、证据折叠展示、历史相似案例和质量评分。新逻辑采用兼容扩展方式接入，避免破坏已有流程。

## 2. 背景问题

当前工单功能已经具备母单、子单、A/R 责任、规则卡片和血缘引用，但实际生成结果存在以下问题：

| 问题 | 表现 | 后果 |
|---|---|---|
| 文本过长 | 每个子单重复影响范围、规则卡片、待确认问题和验收标准 | 用户难以快速抓住重点 |
| 拆单偏固定矩阵 | 子单主要按母单类型和严重等级展开 | 不能精确体现每个影响项真正触发了什么职责 |
| 系统边界不清 | 只展示业务、数据治理、源系统、数据开发等角色 | 看不出报送系统、治理平台、数据集市、源系统、质量平台各自要改什么 |
| 数据治理主线弱 | 工单正文更像泛化实施建议 | 没有突出元数据、血缘、口径、规则、质量、历史经验沉淀 |
| 前端有固定附加内容 | 所有工单都展示同一套建议动作、SQL 和验收标准 | 不同子单看起来像同一种开发工单 |
| 规则卡片使用过重 | 每个子单正文都附完整规则卡片 | 证据价值被噪声稀释 |

## 3. 设计目标

本次改造要让系统稳定回答五个问题：

| 问题 | 输出 |
|---|---|
| 监管变了什么 | 变更证据、报表、指标、口径、频度、校验 |
| 影响哪些资产 | 报送项、报送字段、源字段、加工任务、校验规则、概念、规则卡片 |
| 哪些系统要处理 | 报送系统、数据治理平台、数据集市、源系统、质量校验、测试验收、知识归档 |
| 谁负责什么 | A/R 责任、输入、输出、验收、阻塞点 |
| 经验如何复用 | 最终口径、字段映射、规则卡片、历史工单、人工确认结论 |

## 4. 非目标和硬约束

### 4.1 非目标

- 不建设完整工单流转系统。
- 不对接外部工单平台。
- 不在首期建设复杂知识图谱。
- 不强制引入 embedding 召回。
- 不删除当前 Markdown 工单正文。

### 4.2 硬约束

- 不破坏当前 `POST /api/tasks/{task_id}/generate-ticket` 调用方式。
- 不破坏当前 `GET /api/tasks/{task_id}/workflow` 返回主结构。
- 不删除 `ticket_drafts.content`，旧前端或旧数据仍可使用。
- 不修改已有影响分析主流程的语义判断入口。
- 新字段必须可为空或有默认值，旧数据可以正常读取。
- 前端必须兼容旧工单：没有结构化字段时回退展示 `content`。
- 实现阶段不得改动与本次工单工作台无关的存量逻辑。

## 5. 总体方案

采用“结构化工单卡片 + 触发器驱动拆单 + 系统责任分组 + 治理资产闭环”的方案。

```text
文档画像
  -> 变更信号 change_signals
  -> 影响分析 impact_items
  -> 触发器判定 ticket_triggers
  -> 系统责任聚合 system_task_groups
  -> 结构化任务卡 ticket_cards
  -> 工单质量检查 quality_check
  -> 工单落库 ticket_drafts
  -> 前端卡片展示
  -> 人工确认 / 编辑 / 关闭
  -> 治理资产回写
  -> 历史案例复用
```

旧逻辑保留：

```text
classification + impacts -> build_ticket_plan -> TicketDraft.content
```

新逻辑增强：

```text
classification + impacts -> ticket_trigger_engine -> ticket_card_builder
  -> TicketDraft 结构化字段 + 兼容 Markdown content
```

## 6. 后端模型设计

### 6.1 TicketDraft 兼容扩展

在现有 `TicketDraft` 上新增结构化字段。所有字段均允许为空，历史数据不需要迁移内容。

| 字段 | 类型 | 说明 |
|---|---|---|
| `summary` | Text | 一句话说明本工单目标 |
| `responsible_system` | VARCHAR | 主责任系统 |
| `affected_systems` | Text(JSON) | 受影响系统列表 |
| `affected_assets` | Text(JSON) | 报送项、报送字段、源字段、规则、调度、概念 |
| `must_do` | Text(JSON) | 必须完成动作，默认 3 到 5 条 |
| `must_confirm` | Text(JSON) | 待确认问题 |
| `output_artifacts` | Text(JSON) | 完成后沉淀的治理资产 |
| `acceptance_criteria_structured` | Text(JSON) | 结构化验收标准 |
| `blockers` | Text(JSON) | 缺血缘、缺字段、缺业务确认等阻塞点 |
| `evidence_refs` | Text(JSON) | 原文证据、规则卡片、历史案例引用 |
| `historical_cases` | Text(JSON) | 历史相似案例摘要 |
| `quality_score` | INTEGER | 工单可执行性评分 |
| `quality_flags` | Text(JSON) | 内容过长、缺责任系统、缺验收标准等提示 |

注意：`acceptance_criteria_structured` 使用新字段名，避免与当前 `content` 中的“验收标准”文案产生混淆。

### 6.2 ResponsibleSystem 枚举

新增责任系统枚举，不替代现有 `ResponsibleRole`。

| 枚举 | 中文 | 典型产出 |
|---|---|---|
| `REG_REPORTING_SYSTEM` | 监管报送系统 | 报表版本、报送字段、任务配置 |
| `DATA_GOVERNANCE_PLATFORM` | 数据治理平台 | 元数据、血缘、字段映射、口径版本 |
| `DATA_MART_ETL` | 数据集市 / ETL | SQL、汇总逻辑、调度依赖 |
| `SOURCE_SYSTEM` | 源系统 | 采集字段、码值、接口 |
| `DATA_QUALITY_PLATFORM` | 数据质量平台 | 校验规则、阈值、异常解释 |
| `TEST_ACCEPTANCE` | 测试验收 | 样例、回归、差异分析 |
| `KNOWLEDGE_ARCHIVE` | 归档知识库 | 历史案例、规则卡片、确认结论 |

### 6.3 内部任务卡结构

新增内部结构 `TicketTaskCard`，作为生成阶段中间产物。

```python
class TicketTaskCard(BaseModel):
    action_type: ActionTicketType
    owner_role: ResponsibleRole
    executor_role: ResponsibleRole
    responsible_system: ResponsibleSystem
    summary: str
    affected_assets: dict
    must_do: list[str]
    must_confirm: list[str]
    output_artifacts: list[str]
    acceptance_criteria: list[str]
    blockers: list[str]
    evidence_refs: list[dict]
    historical_cases: list[dict] = []
```

生成顺序为：先构造 `TicketTaskCard`，再落成 `TicketDraft`，最后渲染兼容 Markdown。

## 7. 拆单策略设计

### 7.1 从固定矩阵改为触发器优先

当前固定矩阵保留为兜底。新增触发器优先级：

```text
影响项事实
  -> 触发器判定
  -> 子单候选
  -> 按系统和动作合并
  -> 生成任务卡
  -> 质量检查
  -> 落库
```

### 7.2 触发器规则

| 触发条件 | 子单 | 责任系统 |
|---|---|---|
| 命中报送项且口径变化 | 口径确认 | `REG_REPORTING_SYSTEM` |
| 命中 `REPORT_FIELD`、`SOURCE_FIELD` | 数据映射 | `DATA_GOVERNANCE_PLATFORM` |
| 命中 `DIMENSION_FIELD` 或 `FILTER_FIELD` | 数据映射 + 校验复核 | `DATA_GOVERNANCE_PLATFORM` / `DATA_QUALITY_PLATFORM` |
| 没有源字段命中 | 血缘建链或源系统确认 | `DATA_GOVERNANCE_PLATFORM` / `SOURCE_SYSTEM` |
| 原文出现“新增字段、采集、接口、码值” | 源系统改造 | `SOURCE_SYSTEM` |
| 原文出现“加工逻辑、汇总、调整内部数据加工” | 报送加工 | `DATA_MART_ETL` |
| 原文出现“校验、勾稽、一致性、差异超过” | 校验规则 | `DATA_QUALITY_PLATFORM` |
| 原文出现“追溯、补报、重算、首次按新口径报送” | 历史数据处理 | `REG_REPORTING_SYSTEM` + `DATA_MART_ETL` |
| 影响跨 G24/G31 或跨报送对象 | 跨表一致性校验 | `DATA_QUALITY_PLATFORM` |
| 工单关闭 | 归档复盘 | `KNOWLEDGE_ARCHIVE` |

### 7.3 合并规则

- 同一 `action_type + responsible_system` 合并为一个子单。
- 同一子单下的影响项按 `reporting_item_code` 去重。
- 规则卡片不进入正文主体，只进入 `evidence_refs`。
- 源字段超过 5 个时默认折叠，前端可展开。
- 无源字段命中的影响项必须进入 `blockers`。

## 8. 工单内容设计

### 8.1 母单

母单承载全局信息：

- 监管背景和变更摘要。
- 影响报表、指标、字段、系统统计。
- 严重等级和打分依据。
- 子单分组概览。
- 总体阻塞点。
- 跨系统依赖关系。

母单不承载每个系统的细节动作。

### 8.2 子单

子单默认展示短卡片：

```text
目标：确认 G31 修正久期字段的数据治理映射。
责任系统：数据治理平台
A/R：数据治理 / 数据治理
受影响资产：
- 报送项：G31.PART_I.1_0.C_修正久期
- 报送字段：rpt_g31_part_i.modified_duration
- 源字段候选：dm_g31_risk.modified_duration
必须动作：
1. 确认修正久期取数来源。
2. 补齐字段血缘和转换表达式。
3. 标注字段角色和生效版本。
待确认：
- 是否按单券还是组合层级计算？
- 缺估值数据时是否允许为空？
验收：
- 血缘可查询。
- 业务确认字段语义。
- 报送加工子单可引用该映射。
```

### 8.3 字数和数量限制

| 内容 | 限制 |
|---|---|
| `summary` | 1 句话 |
| `must_do` | 最多 5 条 |
| `must_confirm` | 最多 5 条 |
| `acceptance_criteria` | 最多 5 条 |
| `affected_assets` | 默认展示核心 5 个，超出折叠 |
| 规则卡片 | 默认只显示数量和标题，正文折叠 |
| 历史案例 | 默认 Top 3 |

## 9. 前端工作台设计

### 9.1 页面结构

```text
顶部：变更总览
左侧：系统责任分组 + 工单列表
中间：任务卡详情
右侧/抽屉：证据、规则、血缘、历史案例
```

### 9.2 顶部总览

| 指标 | 示例 |
|---|---|
| 影响报表 | G24、G31 |
| 影响指标 | 7 个 |
| 缺源字段 | 1 个 |
| 涉及系统 | 数据治理、报送加工、源系统、质量校验 |
| 高优先级任务 | 3 个 |
| 待人工确认 | 5 个 |

### 9.3 左侧分组

第一分组：责任系统。

第二标签：动作类型。

示例：

```text
数据治理平台
  - 数据映射子单
  - 血缘建链子单
数据集市 / ETL
  - 报送加工子单
数据质量平台
  - 校验规则子单
测试验收
  - 测试验收子单
```

### 9.4 右侧抽屉

| Tab | 内容 |
|---|---|
| 监管证据 | 原文片段、表样差异、填报说明 |
| 血缘详情 | 报送字段、源字段、角色、转换表达式 |
| 规则卡片 | 相关 L1/L2/L3 规则 |
| 历史案例 | 相似历史工单和最终处理 |
| SQL/ETL | 仅报送加工、校验规则类子单展示 |

### 9.5 兼容旧数据

- 若结构化字段为空，显示旧 `content`。
- 若结构化字段存在，优先展示任务卡。
- “导出全部”继续可以导出 Markdown。
- 旧工单不会因为新增字段而无法查看。

## 10. 历史经验复用设计

新增 `decision_archive_service.py`，首期不强制新建大表。

查询逻辑：

```text
当前影响项
  -> reporting_item_code / concept_codes / rule_card_codes
  -> 查询历史 ticket_drafts + impact_items + rule_cards + audit_logs
  -> 返回 Top 3 历史相似处理案例
```

历史案例字段：

| 字段 | 说明 |
|---|---|
| `case_title` | 历史任务标题 |
| `matched_reason` | 为什么相似 |
| `decision_summary` | 最终处理结论 |
| `changed_assets` | 当时改过的字段、规则或口径 |
| `accepted_by` | 确认角色 |
| `reference_ticket_id` | 历史工单 ID |

首期历史案例只作为参考证据，不直接决定当前工单动作。

## 11. 工单质量评分

新增 `ticket_quality_checker.py`。

| 检查项 | 扣分条件 |
|---|---|
| 责任明确 | 缺 A/R 或责任系统 |
| 可执行 | `must_do` 为空或过于泛化 |
| 可验收 | 缺验收标准 |
| 证据充分 | 没有证据引用 |
| 治理闭环 | 缺 `output_artifacts` |
| 内容简洁 | 正文过长或重复规则卡片 |
| 系统边界 | 没有受影响系统 |
| 阻塞透明 | 缺源字段但未标注 blocker |

前端展示：

```text
工单质量：82 / 100
提示：
- 缺少历史相似案例
- 源字段未命中，需确认是否生成源系统子单
```

## 12. 实施分期

### P0：可读性和兼容结构

- 扩展 `TicketDraft` 和 schema。
- 新增结构化任务卡生成。
- 保留旧 Markdown。
- 删除前端固定建议动作、固定 SQL、固定验收标准。
- 规则卡片改为折叠引用。
- 旧数据回退展示 `content`。

验收：

- 子单默认视图不再是长 Markdown。
- 不同子单展示不同任务卡。
- 数据映射子单不展示无关 SQL。
- 旧工单仍可查看。

### P1：触发器驱动职责拆分

- 升级 `ticket_scope_classifier.py` 或新增 `ticket_trigger_engine.py`。
- 使用影响项事实决定子单生成。
- 按责任系统分组。
- 加入 `output_artifacts` 和 `blockers`。

验收：

- 缺源字段会明确标记 blocker。
- 校验类工单只在命中校验/勾稽/一致性时生成。
- 跨表公告能生成跨表一致性校验任务。
- G31 场景不再出现“资金同业、交易对手维度”等不贴合描述。

### P2：历史案例和质量评分

- 新增 `decision_archive_service.py`。
- 新增 `ticket_quality_checker.py`。
- 工单展示 Top 3 历史相似案例。
- 工单质量评分入库并展示。

验收：

- 工单能引用历史相似案例。
- 工单质量缺陷可见。
- 关闭后的确认结论可作为后续复用依据。

### P3：治理资产闭环

- 工单关闭时回写规则卡片、概念、血缘、历史案例。
- 建立复用统计。
- 为一表通/EAST/客户风险复用同一套工单编排框架。

验收：

- 下次类似发文可以召回历史处理经验。
- 规则卡片和概念库能从工单确认结果中更新。
- 多监管体系复用同一工作台。

## 13. 测试策略

### 后端测试

- 旧 `generate-ticket` 接口返回结构兼容。
- 旧 `workflow` 接口返回结构兼容。
- 旧工单无结构化字段时可正常序列化。
- 触发器根据影响项生成预期子单。
- 无源字段影响项会生成 blocker。
- 规则卡片进入 evidence refs，不进入正文主体。
- 工单质量评分能识别缺责任系统、缺验收、缺证据。

### 前端测试

- 旧工单回退展示 Markdown。
- 新工单展示结构化任务卡。
- 按责任系统分组正确。
- 抽屉能展示证据、血缘、规则卡片。
- 不同 `action_ticket_type` 不再共用固定 SQL。

### 样例验收

样例一：G31 修正久期和穿透余额。

- 生成数据治理、报送加工、测试验收子单。
- 修正久期任务能体现估值字段、风险指标字段和转换口径。
- 不出现 G24/G21/G25 固定 SQL。

样例二：G24/G31 跨表口径公告。

- 生成跨表一致性校验任务。
- 生成数据治理映射任务。
- 明确 G24 和 G31 之间的一致性校验关系。

## 14. 风险和应对

| 风险 | 应对 |
|---|---|
| 新字段影响旧数据 | 所有字段可为空，前端回退 `content` |
| 触发器误拆单 | 固定矩阵保留为兜底，质量评分提示低置信 |
| 页面改造过大 | 分 P0/P1/P2 逐步替换，旧 Markdown 保留 |
| 历史案例质量不足 | 首期只作为参考证据，不自动影响生成决策 |
| 工单过度拆分 | 合并规则按 `action_type + responsible_system` 聚合 |

## 15. 文件改造清单

### 优先改造

| 文件 | 改造 |
|---|---|
| `backend/app/models/db_models.py` | 扩展 `TicketDraft` 结构化字段 |
| `backend/app/models/schemas.py` | 扩展 `TicketDraftRead` |
| `backend/app/core/database.py` | 旧库补列 |
| `backend/app/services/reporting_ticket_generator.py` | 保留旧入口，改为生成结构化卡片和兼容 Markdown |
| `backend/app/services/ticket_scope_classifier.py` | 升级触发器规则 |
| `frontend/src/types/api.ts` | 增加结构化字段类型 |
| `frontend/src/views/ReviewTicketView.vue` | 改为系统分组 + 任务卡 + 折叠证据 |

### 新增文件

| 文件 | 用途 |
|---|---|
| `backend/app/services/ticket_card_builder.py` | 结构化任务卡生成 |
| `backend/app/services/ticket_trigger_engine.py` | 触发器判定 |
| `backend/app/services/ticket_quality_checker.py` | 工单质量评分 |
| `backend/app/services/decision_archive_service.py` | 历史相似案例召回 |

## 16. 用户确认点

本设计基于以下确认：

- 用户认可全部优化方向。
- 用户明确要求不要动到存量逻辑。
- 因此实现必须以兼容扩展为原则，旧接口、旧字段、旧 Markdown 和旧数据显示路径全部保留。

