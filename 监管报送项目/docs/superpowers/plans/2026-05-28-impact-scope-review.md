# Impact Scope Review — 影响范围业务复核与按系统派单

> **更新日期**：2026-05-28
> **状态**：设计稿，待江秋萍确认；确认后切分给 Claude / Codex 实施。

---

## 1 · 背景与问题

### 当前形态
工单页 "影响范围" 区是 LLM 推断出的扁平资产清单：

| 资产类型 | 中文名称 | 技术编码 | 血缘角色 |
|---|---|---|---|
| 受影响报送项 | 名称待补充 | G31.PART_I.1_0.C_修正久期 | — |
| 报送字段 | 名称待补充 | rpt_g31_part_i.modified_duration | — |
| 源字段 | 名称待补充 | dm_g31_risk.modified_duration | — |
| … | | | |

下游"AI 生成工单"按**动作类型**（SCOPE_CONFIRM / DATA_MAPPING / SOURCE_SYSTEM_CHANGE / REPORT_PROCESSING / VALIDATION_RULE / TEST_ACCEPTANCE / ARCHIVE_REVIEW）展开 7 张子单，业务方读完仍要在群里口头确认"这些字段到底要不要做"。

### 痛点
- **可信度有缺口**：LLM 推断的源字段/系统可能多了（噪音）或少了（漏判），业务没有手段当场修正
- **派单粒度不对**：业务关心的是"哪个系统团队需要做什么"，不是"7 种动作类型"
- **缺业务上下文**：模型只看了监管发文，业务方知道的"现网背景"无法附加给下游

### 目标
1. **影响范围可视化重组**：从扁平表 → 三级折叠树（报送项 → 系统 → 源字段）
2. **业务可交互勾选**：勾选 / 取消 / 增字段 / 增系统
3. **业务可写备注**：每个系统子单留一段自由文本，传达"团队间默契"
4. **按系统派单**：业务确认后按"受影响系统"展开子单（每个系统一张），而不是按动作类型

---

## 2 · UI 设计

### 2.1 入口与状态机

在现有工单工作台「影响范围」区块上方加一个**模式开关**：

```
[AI 推荐视图]  [业务复核视图 ← 默认未确认时灰，可点击]
```

- **AI 推荐视图**（即当前的扁平表）：保持现状，作为"信息流第一眼可见"
- **业务复核视图**：新增的可勾选树。业务确认后，工单展开走新逻辑

状态机：
```
INITIAL（首次进入）
   ↓ 用户点"业务复核视图"
EDITING（编辑中，本地状态）
   ↓ 用户点"暂存"
SAVED（草稿落库，未生成工单）
   ↓ 用户点"确认并生成工单"
CONFIRMED（工单已生成，但仍可重新编辑回 EDITING）
```

### 2.2 三级折叠树形态

```
▼ G31.PART_I.1_0.C_修正久期  [4 个字段]            [⚙ 编辑 | 🗑 移除]
   ▼ DATA_MART_ETL · 数据集市/ETL  [选中 2/3]
      ☑ rpt_g31_part_i.modified_duration  [报送字段]
      ☑ dm_g31_risk.modified_duration      [中间层]
      ☐ legacy_dm.duration                  [中间层 · AI 推断 · 业务取消]
      [+ 添加字段]
   ▼ SOURCE_SYSTEM · 业务源系统  [选中 1/1 · 业务补充 1]
      ☑ bond_position.modified_duration     [源字段]
      ☑ ✏️ trading_book.duration             [源字段 · 业务新增]
      [+ 添加字段]
   [+ 添加系统]
   ─────────────────────────────────────
   📝 业务备注（可选）：
   ┌─────────────────────────────────────┐
   │ 修正久期口径调整请优先处理。     │
   │ 历史数据由 ETL 团队补录。           │
   └─────────────────────────────────────┘

▼ G31.PART_I.1_0.D_因持有非底层资产…  [3 个字段]
   ▶ DATA_MART_ETL  [选中 2/2]
   ▶ SOURCE_SYSTEM  [选中 1/1]
   📝 业务备注…

▼ G31.PART_I.1_0.单位_万元_E_穿透后_期末余额  [折叠中]

▼ G31.PART_I.1_0.COL_1  [折叠中]

────────────────────────────────────────
[暂存草稿]  [恢复 AI 推荐]  [✅ 确认并生成工单]
```

### 2.3 交互细节

| 操作 | 行为 |
|---|---|
| 点行首 `▼/▶` | 折叠 / 展开 |
| 点字段前 ☑ | 切换"是否纳入工单" |
| 点字段后 ✏️ 图标 | 编辑该字段的展示名 / 修正技术编码 |
| 点字段行右侧 🗑 | 软删除（标记 `removed=true`，仍可恢复） |
| 点"+ 添加字段" | 弹出输入框：技术编码（必填）+ 显示名（选填） |
| 点"+ 添加系统" | 下拉选 7 个责任系统枚举之一 |
| 点报送项行右侧 🗑 | 整个报送项不进任何子单（极端场景） |
| 备注框 | 单个报送项一段，限 500 字，自动保存 |
| 点"暂存草稿" | 落库 status=SAVED，不生成工单 |
| 点"确认并生成工单" | 走 §4 流程，生成 N 张子单（每个系统一张） |
| 点"恢复 AI 推荐" | 二次确认后重置为 LLM 原始推断 |

### 2.4 视觉标记

| 徽章 | 含义 |
|---|---|
| `AI` 浅紫 | LLM 推断 |
| `业务新增` 浅蓝 | 业务手动加的字段 / 系统 |
| `已修正` 浅黄 | LLM 推断后被业务编辑过 |
| `已取消` 灰删除线 | 取消勾选 / 软删除 |
| `必选` 红色 | 系统判定不能取消（例如该报送项本身的报送字段，取消会导致工单失去意义） |

---

## 3 · 数据模型

### 3.1 新表 · `reporting_impact_review`

承载"业务复核的完整状态"。一个 task 一条，整体序列化。

```sql
CREATE TABLE reporting_impact_review (
  id BIGINT PK AUTO_INCREMENT,
  task_id BIGINT UNIQUE,              -- 一任务一份复核结果
  status VARCHAR(20) DEFAULT 'EDITING', -- EDITING / SAVED / CONFIRMED
  review_content TEXT,                -- JSON：完整复核树（见下）
  ai_baseline_content TEXT,           -- JSON：首次进入时 AI 推荐的快照（用于"恢复"）
  confirmed_at DATETIME NULL,
  confirmed_by VARCHAR(64) DEFAULT '',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

`review_content` JSON 结构：

```json
{
  "version": "v1",
  "items": [
    {
      "reporting_item_code": "G31.PART_I.1_0.C_修正久期",
      "reporting_item_name": "修正久期",
      "removed": false,
      "business_note": "修正久期口径调整请优先处理。",
      "systems": [
        {
          "responsible_system": "DATA_MART_ETL",
          "responsible_system_zh": "数据集市/ETL",
          "fields": [
            {
              "field_code": "rpt_g31_part_i.modified_duration",
              "field_name": "修正久期（报送字段）",
              "lineage_role": "REPORT_FIELD",
              "source": "AI",          // AI / BUSINESS
              "selected": true,
              "edited": false,
              "removed": false,
              "is_required": true     // 必选不可取消
            },
            {
              "field_code": "dm_g31_risk.modified_duration",
              "field_name": "修正久期（集市层）",
              "lineage_role": "DERIVED_FIELD",
              "source": "AI",
              "selected": true
            },
            {
              "field_code": "legacy_dm.duration",
              "field_name": "",
              "lineage_role": "DERIVED_FIELD",
              "source": "AI",
              "selected": false       // 业务取消勾选
            }
          ]
        },
        {
          "responsible_system": "SOURCE_SYSTEM",
          "responsible_system_zh": "业务源系统",
          "fields": [
            {
              "field_code": "trading_book.duration",
              "field_name": "持仓久期",
              "lineage_role": "SOURCE_FIELD",
              "source": "BUSINESS",   // 业务新增
              "selected": true
            }
          ]
        }
      ]
    }
  ]
}
```

### 3.2 `ticket_drafts` 加 1 个字段

```sql
ALTER TABLE ticket_drafts ADD COLUMN business_note TEXT DEFAULT '';
```

`business_note` 承接复核里每个 reporting_item × system 维度的备注（合并写入对应系统子单）。

### 3.3 关系：复核结果 → 工单

复核确认后：
- `reporting_impact_review.review_content` 是权威源
- 工单生成函数 `build_ticket_plan_v2` 按此 JSON 重新展开（详见 §4）
- 旧 `ticket_drafts` 清除重写
- 复核记录的 `status=CONFIRMED` 不会被覆盖，业务再次"恢复编辑"会重置回 `EDITING`

---

## 4 · 工单生成新逻辑（v2）

### 4.1 旧逻辑（v1，保留兜底）
触发器引擎按 `action_type × responsible_system` 展开 → 7 张子单（SCOPE_CONFIRM、DATA_MAPPING、SOURCE_SYSTEM_CHANGE、REPORT_PROCESSING、VALIDATION_RULE、TEST_ACCEPTANCE、ARCHIVE_REVIEW）。

### 4.2 新逻辑（v2，业务确认后启用）

**核心变化**：从"按动作类型展开"切到"按受影响系统展开"。

**步骤**：
1. 读 `reporting_impact_review.review_content`，过滤 `selected=true && removed=false` 的字段
2. 按 `responsible_system` 聚合：每个系统一张子单
3. 每张子单的内容：
   - **title**：`{母单标题}｜{责任系统中文名}`
   - **responsible_system**：枚举值（与 ResponsibleSystem 对齐）
   - **affected_assets**：该系统下勾选的所有字段，按 reporting_item 分组
   - **summary**（LLM 个性化）：见 §4.3
   - **must_do**：根据该系统下字段的 `lineage_role` 推导动作类型（SOURCE_FIELD → 源系统改造 must_do；REPORT_FIELD/DERIVED_FIELD → ETL/映射 must_do），从 `_ACTION_CARD_SPECS` 选对应模板
   - **business_note**：合并该系统下所有 reporting_item 的 business_note（去重）
   - **quality_score**：仍然走 `ticket_quality_checker`
4. 系统枚举命中 ≥2 个 → 额外追加 1 张 `TEST_ACCEPTANCE` 验收子单 + 1 张 `ARCHIVE_REVIEW` 沉淀子单（与 v1 保持一致）

### 4.3 LLM 给每张系统子单写定制 summary（可选，演示亮点）

调一次 LLM，输入：
- 该系统涉及哪些 reporting_item（编码 + 名称）
- 该系统下勾选的字段（编码 + 名称 + 血缘角色）
- 业务备注

LLM 输出一段 1-2 句的定制 summary，例如：

> "DATA_MART_ETL 团队需要处理修正久期和因持有非底层资产的间接持有期末余额两项指标，涉及 4 个集市层字段，业务备注要求优先排产。"

落地到 `ticket_drafts.summary`。

这一步**与 Module D 共用 LLM client 与提示词版本管理**，提示词存 `app/prompts/system_ticket_summary_v1.md`。

### 4.4 兼容性
- 旧 task（没有 `reporting_impact_review` 记录）→ 走 v1 旧逻辑
- 新 task 业务未点"确认"前 → 仍走 v1
- 业务点"确认"后 → 切到 v2，旧 `ticket_drafts` 被替换

---

## 5 · API 契约

### 5.1 GET `/api/tasks/{task_id}/impact-review`

获取当前复核状态。若没有，从 `reporting_impact_items` 推算 AI baseline 后返回。

响应：
```json
{
  "status": "EDITING",
  "review": { /* review_content JSON */ },
  "ai_baseline": { /* 首次推算的 AI baseline 快照 */ },
  "stats": {
    "total_items": 4,
    "total_systems": 3,
    "selected_fields": 8,
    "business_added_fields": 2,
    "business_removed_fields": 1
  }
}
```

### 5.2 PUT `/api/tasks/{task_id}/impact-review`

保存草稿（暂存）。

请求体：完整 `review` JSON。
响应：`{ "ok": true, "updated_at": "..." }`

### 5.3 POST `/api/tasks/{task_id}/impact-review/confirm`

确认并触发工单生成。

请求体：可选 `review` JSON（不传则用最新草稿）。
响应：标准 `TicketPlanResponse`（与 `/generate-ticket` 同形）。

### 5.4 POST `/api/tasks/{task_id}/impact-review/reset`

恢复为 AI 推荐。

响应：刷新后的 `review` JSON。

---

## 6 · 工程拆分

| 任务 | 文件 | 工作量 | 谁做 |
|---|---|---|---|
| **R1** 数据库表 + DDL | `db_models.py`、`database.py` `_ensure_reporting_impact_review_columns` | 0.5d | Claude |
| **R2** baseline 推算 | `services/impact_review_service.py` 新增，从 `reporting_impact_items` + `reporting_item_lineage` 推算初始树 | 1d | Claude |
| **R3** 4 个 API 端点 | `routes_tasks.py` 追加 | 0.5d | Claude |
| **R4** `build_ticket_plan_v2` | `services/reporting_ticket_generator.py` 加新入口，按 review 展开 | 1d | Claude |
| **R5** 系统子单 LLM summary（可选） | `services/system_ticket_summarizer.py` + `prompts/system_ticket_summary_v1.md` | 1d | Claude |
| **R6** 前端三级折叠树组件 | `frontend/src/components/ImpactScopeReview.vue` | 1.5d | Codex |
| **R7** 集成到 ReviewTicketView | `ReviewTicketView.vue` 加模式开关 + 嵌入 R6 | 0.5d | Codex |
| **R8** 前端 fixture + vitest | `fixtures/impactReview.ts` + `__tests__/ImpactScopeReview.test.ts` | 0.5d | Codex |
| **R9** 后端 unit test + eval | `tests/test_impact_review_service.py`、`tests/test_ticket_plan_v2.py` | 1d | Claude |

**总计**：~7.5 人日，其中后端 4d / 前端 2.5d / LLM 增强 1d。

**演示 MVP（赶时间能砍）**：
- 不做 R5（LLM 个性化 summary） → 省 1d
- 不做"增加系统/字段"的 UI（只允许勾选 + 备注） → 省 0.3d
- 不持久化 EDITING 草稿（只在内存里） → 省 0.5d

MVP 范围约 **4-5 人日**。

---

## 7 · 演示口径

> "影响范围这一栏，业务方过去只是看 AI 给的清单，没法当场拍板。现在我们把它做成可勾选的三级树——报送项 / 系统 / 字段——业务可以勾掉错的、补上漏的、写上备注，确认后系统按受影响的 3 个系统直接生成 3 张可派单的工单，每张工单带上业务的原话备注。
>
> **设计精髓**：AI 出推荐（覆盖度），业务做复核（准确度），系统出工单（一致性）。三个角色各司其职，AI 不背"准确率"的锅，业务不写文档样板，下游团队拿到的是带业务上下文的精确工单。"

---

## 8 · 待你确认的 7 个决策点

| # | 问题 | 我的建议 |
|---|---|---|
| 1 | 旧的 7 种动作类型工单（v1）是否完全替换？ | **保留**，新 task 走 v2，老 task 用 v1，演示时只看 v2 |
| 2 | 7 种责任系统 / 业务能否新增第 8 种？ | **不能**，先锁死枚举；自定义系统名走"补充备注" |
| 3 | 字段技术编码是否需要校验存在性？ | **不校验**（业务想加什么就加什么，下游团队自己核实），但加 warning 提示 |
| 4 | 备注框是按报送项还是按系统？ | **按报送项**（数据更紧凑；落到子单时合并） |
| 5 | "确认并生成工单"后能否再编辑回 EDITING？ | **能**，但二次确认会重新生成工单覆盖旧的 |
| 6 | LLM 个性化 summary 现在做还是 W2 做？ | **W2 做**（MVP 先用模板 + business_note 拼接，演示已经够） |
| 7 | 演示这次铺到什么程度？ | **MVP 4 人日范围**：折叠树 + 勾选 + 添加字段 + 备注 + 按系统派单；不做 LLM summary、不做 EDITING 草稿持久化、不做"添加系统" |

---

## 9 · 开发顺序建议

如果决定做：

```
Day 1  R1 数据库 + R2 baseline 推算（Claude，半天）
       R6 前端折叠树骨架 + 假数据驱动（Codex，半天）

Day 2  R3 API（Claude）
       R6 继续 + R7 集成（Codex）

Day 3  R4 build_ticket_plan_v2（Claude）
       R8 前端测试（Codex）

Day 4  R9 后端测试 + 联调
       手工演示彩排
```

---

待你回复 §8 的 7 个决策点。
