# Reference SQL Generator — AI 参考 SQL 生成（每张系统子单一段）

> **更新日期**：2026-05-29
> **状态**：设计稿，待江秋萍确认；确认后切分给 Claude / Codex 实施。
> **前置依赖**：`2026-05-28-impact-scope-review.md`（业务复核 + 按系统派单）必须先落地。

---

## 1 · 背景与目标

### 现状
业务复核完字段后，每张系统子单只有"必须处理项 + 验收标准 + 业务备注"——告诉下游团队**做什么**，没有告诉**怎么写**。数据开发同学拿到工单后，仍然要：
1. 重新读一遍监管原文搞懂口径
2. 翻数据字典找字段
3. 解读业务备注里的隐含约束
4. 自己写第一版 SQL 后再和业务对齐

### 目标
**在每张系统子单底部加一段 AI 生成的参考 SQL**，把"监管原文 + 业务备注 + 字段 schema"三件套交给 LLM，输出带注释、带校验、可编辑、可保存的 ANSI SQL。

### 产品定位升级
- 现在：影响分析工具 + 自动建单工具
- 加这个之后：**AI 数据治理工程助手**（业务从"看到问题"升级到"看到解法"；开发从"从零写"升级到"改改就能用"）

---

## 2 · 设计原则

| 原则 | 含义 |
|---|---|
| **参考性优先** | 显式标注"AI 参考 SQL，必须人工审核"，永远不提供"一键执行" |
| **可校验** | 字段名必须来自业务勾选清单，编造字段标黄告警 |
| **可编辑** | 业务/开发能在前端 monaco editor 改完保存 |
| **可降级** | LLM 失败 / 语法错 / 字段编造严重 → 返回"骨架 SQL 模板"+ needs_human_review |
| **可解释** | SQL 顶部强制注入业务备注 + 监管原文摘录作为注释，使 SQL 自证 |
| **手动触发** | 业务点按钮才生成，避免没看的工单浪费 token |

---

## 3 · UI 交互

### 3.0 可生成性闸门（SQL-ability gate · 生成前先判定）

**不是所有子单都能/该生成 SQL。** 实测数据库后确认有三类口径天然写不出取数 SQL：
纯业务判断口径、非加工类子单（范围确认/任务配置/验收/沉淀）、源字段尚不存在的改造单。
所以在调用 LLM 之前先用纯规则给每张子单判一个等级（零 LLM 成本）：

| 档位 | 判定条件 | 处理 |
|---|---|---|
| 🟢 `CAN_GENERATE` | 有源字段 + 有 transform_expression + 取数类动作（DATA_MAPPING / REPORT_PROCESSING / LINEAGE_BUILD） | 正常生成 SELECT |
| 🟡 `PARTIAL` | 有源字段但 transform 不全（如修正久期需加权平均但血缘只标 direct_mapping） | 生成 SQL，confidence 上限 0.5，标注"加工逻辑需人工补全" |
| 🔵 `VALIDATION_ONLY` | 校验/勾稽类动作（VALIDATION_RULE） | 生成**对账校验 SQL**（两侧 SUM 相减比差异），非取数 SQL |
| ⚪ `NOT_APPLICABLE` | 非加工子单（SCOPE_CONFIRM / TASK_INIT / TEST_ACCEPTANCE / ARCHIVE_REVIEW / CATALOG_INIT）、或源字段缺失、或纯业务判断 | **不显示 SQL 区块**，改显示一句说明（见 §3.6） |

判定逻辑（`services/ticket_sql_generator.py::assess_sql_ability`，纯规则）：

```python
NON_DATA_ACTIONS = {
    ActionTicketType.SCOPE_CONFIRM,
    ActionTicketType.TASK_INIT,
    ActionTicketType.TEST_ACCEPTANCE,
    ActionTicketType.ARCHIVE_REVIEW,
    ActionTicketType.CATALOG_INIT,
}

def assess_sql_ability(
    action_type: ActionTicketType,
    has_source_fields: bool,
    has_transform_expression: bool,
) -> str:
    if action_type in NON_DATA_ACTIONS:
        return "NOT_APPLICABLE"          # 这类子单不碰数据
    if action_type == ActionTicketType.SOURCE_SYSTEM_CHANGE and not has_source_fields:
        return "NOT_APPLICABLE"          # 源字段还不存在，无从查起
    if action_type == ActionTicketType.VALIDATION_RULE:
        return "VALIDATION_ONLY"         # 写对账校验 SQL
    if has_source_fields and has_transform_expression:
        return "CAN_GENERATE"
    if has_source_fields:
        return "PARTIAL"
    return "NOT_APPLICABLE"
```

**数据基础（实测）**：`reporting_item_lineage.transform_expression` 已存有"伪 SQL 片段"——
`sum(position_balance)` / `asset_type in ('BOND','ABS','NCD')`（FILTER）/ `group by security_id`（DIMENSION）/
`fallback market_value when book_balance missing`。`data_field_catalog` 46 条字段都有真实 `table_name + column_name + data_type`。
所以 CAN_GENERATE 档位的 SQL 是 LLM **在已有血缘片段上拼装**，而非凭空编造，准确率显著高于裸生成。

闸门结果作为 LLM 提示词的输入（VALIDATION_ONLY 切换到对账 SQL 提示词分支），也作为前端区块渲染的开关。

### 3.1 入口

在每张**系统子单**的卡片底部加一个区块：

```
┌─────────────────────────────────────────────────────────────┐
│  📝 业务备注                                                  │
│  「修正久期口径调整请优先处理，历史数据由 ETL 团队补录」      │
├─────────────────────────────────────────────────────────────┤
│  💡 参考 SQL                          [🤖 AI 生成]            │
│                                                              │
│  尚未生成参考 SQL，点击右上角按钮让 AI 起草。                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 生成中

```
│  💡 参考 SQL                          [⏳ 生成中…]           │
│  ▓▓▓▓▓░░░░░░░░░░░░ 调用 qwen-plus（约 5 秒）                  │
```

### 3.3 生成完成

```
┌──────────────────────────────────────────────────────────────────┐
│  💡 参考 SQL                       [♻️ 重新生成] [📋 复制]        │
│  ⚠️ AI 生成参考 SQL · 必须人工审核 · 置信度 78%                    │
│  ─────────────────────────────────────────────────────────────── │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ -- 工单：修正久期穿透后口径                                  │ │
│  │ -- 业务备注：「修正久期口径调整请优先处理…」                  │ │
│  │ -- 监管：〔2026〕第 15 号 自 2026-07-01 起执行                │ │
│  │                                                             │ │
│  │ SELECT                                                      │ │
│  │   data_dt,                                                  │ │
│  │   SUM(modified_duration * balance) / NULLIF(SUM(balance),0) │ │
│  │     AS modified_duration_lookthrough                        │ │
│  │ FROM ods_bond_position                                      │ │
│  │ WHERE is_lookthrough = 'Y'                                  │ │
│  │   AND data_dt = '${report_date}'                            │ │
│  │ GROUP BY data_dt                                            │ │
│  │ ;                                                           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  🟡 字段引用提示（1 条）                                          │
│  · `is_lookthrough` 未在业务勾选字段内，请确认是否需要补充勾选     │
│                                                                  │
│  [✏️ 编辑] [💾 保存到工单] [👍 / 👎 反馈]                        │
└──────────────────────────────────────────────────────────────────┘
```

### 3.4 编辑态（点击「编辑」后）

```
│  💡 参考 SQL · 编辑中                  [取消] [💾 保存]      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  monaco editor，SQL 语法高亮 + 行号                     │  │
│  │  失焦自动 sqlglot 语法校验                              │  │
│  └──────────────────────────────────────────────────────┘  │
│  最后修改：业务张三 · 2026-05-29 14:30                       │
```

### 3.5 交互细节

| 操作 | 行为 |
|---|---|
| 点 `[🤖 AI 生成]` | 异步调用 LLM，loading 状态显示进度，5 秒左右返回 |
| 点 `[♻️ 重新生成]` | 弹确认框（"这会覆盖当前 SQL，包括人工编辑内容"），确认后重新调 LLM |
| 点 `[📋 复制]` | 复制 SQL 全文到剪贴板，含注释头 |
| 点 `[✏️ 编辑]` | monaco editor 进入编辑态，原 SQL 文本可改 |
| 点 `[💾 保存到工单]` | PUT 到 `ticket_drafts.reference_sql`，标记 `last_edited_by`，重跑字段校验 |
| 点 `[👍 / 👎]` | 写入 `ticket_drafts.sql_feedback_thumbs`，为后续 prompt 迭代积累数据 |
| 字段引用提示点击 | 跳转到"影响范围复核"对应字段处，提示业务"是否补充勾选" |
| 业务修改了影响范围 | SQL 显示"⚠️ 影响范围已更新，建议重新生成"横幅 |

---

## 4 · 数据模型

### 4.1 `ticket_drafts` 表加字段（不新建表）

```sql
ALTER TABLE ticket_drafts ADD COLUMN reference_sql TEXT DEFAULT '';
ALTER TABLE ticket_drafts ADD COLUMN sql_dialect VARCHAR(20) DEFAULT 'ANSI';
ALTER TABLE ticket_drafts ADD COLUMN sql_confidence FLOAT DEFAULT 0.0;
ALTER TABLE ticket_drafts ADD COLUMN sql_status VARCHAR(20) DEFAULT 'NOT_GENERATED';
  -- NOT_GENERATED / READY / DEGRADED / EDITED_BY_USER / STALE
ALTER TABLE ticket_drafts ADD COLUMN sql_warnings TEXT DEFAULT '[]';
  -- JSON 列表，每项含 type / message / field_code
ALTER TABLE ticket_drafts ADD COLUMN sql_generated_at DATETIME NULL;
ALTER TABLE ticket_drafts ADD COLUMN sql_generated_by VARCHAR(64) DEFAULT '';
  -- "sql_v1@qwen-plus" / "user:zhangsan"
ALTER TABLE ticket_drafts ADD COLUMN sql_feedback_thumbs_up INT DEFAULT 0;
ALTER TABLE ticket_drafts ADD COLUMN sql_feedback_thumbs_down INT DEFAULT 0;
ALTER TABLE ticket_drafts ADD COLUMN sql_ability VARCHAR(20) DEFAULT '';
  -- CAN_GENERATE / PARTIAL / VALIDATION_ONLY / NOT_APPLICABLE（§3.0 闸门结果）
ALTER TABLE ticket_drafts ADD COLUMN sql_not_applicable_reason TEXT DEFAULT '';
  -- NOT_APPLICABLE 时的人话原因，前端空态直接展示
```

走和现有 `_ensure_ticket_draft_columns()` 同样模式补列。

### 4.2 `sql_warnings` JSON 形态

```json
[
  {
    "type": "FIELD_NOT_IN_SCOPE",
    "message": "字段 is_lookthrough 未在业务勾选清单内",
    "field_code": "is_lookthrough",
    "severity": "WARNING"
  },
  {
    "type": "SYNTAX_ERROR",
    "message": "第 5 行：missing FROM clause near 'WHERE'",
    "severity": "ERROR"
  },
  {
    "type": "TABLE_NOT_IN_CATALOG",
    "message": "表 ods_bond_position 未在数据字典内（来自 AI 推断）",
    "field_code": "ods_bond_position",
    "severity": "INFO"
  }
]
```

3 个 severity 决定 UI 颜色：ERROR 红 / WARNING 黄 / INFO 灰。

---

## 5 · 提示词设计

### 5.1 模板文件

`backend/app/prompts/system_ticket_sql_v1.md`，jinja2 模板，分 `===SYSTEM===` / `===USER===` 两段（与 Module D 同一约定）。

### 5.2 SYSTEM 段（核心约束）

```
你是银行数据开发工程师，要为一个监管报送指标写一段 ANSI SQL。

【硬约束】
1. 严禁虚构字段：所有出现的字段必须来自下方"可用字段清单"
2. 严禁虚构表：所有 FROM/JOIN 的表必须出现在"可用字段清单"对应的 table_name
3. SQL 顶部必须有 3 行注释：工单标题 / 业务备注 / 监管文号 + 生效日期
4. 选用 ANSI SQL，避免特定方言函数（PIVOT / TOP / LIMIT 可，但避免 DECODE / IIF）
5. 避免 SELECT *，必须显式列名
6. 涉及聚合时除以 SUM 必须用 NULLIF 防零除
7. 时间过滤用 ${report_date} 占位符，不要写死日期
8. 输出必须是合法 JSON，schema 见下

【SQL 生成方法论】
- 先识别度量：报送项是聚合（SUM/AVG/COUNT/RATIO）还是明细
- 再识别维度：是否需按机构/产品类型/期限分组
- 然后识别过滤：监管口径是否要求排除某些场景（如"仅穿透后"、"不含其他"）
- 最后识别勾稽：业务备注里有没有提到"和 XX 表对账"

【confidence 自评】
- 字段完整匹配 + 度量明确 + 监管口径清晰 → 0.8+
- 任一字段需要推断（业务勾选了字段但 schema 缺失）→ 0.5-0.7
- 度量或过滤需要假设 → 0.3-0.5

【输出 JSON Schema】
{
  "sql": "string，完整 ANSI SQL，含注释",
  "explanation": "string，1-3 句话说明 SQL 思路（口径如何对应字段、为何这样聚合）",
  "assumptions": ["string", ...],  // SQL 里隐含的假设，如"假设 is_lookthrough='Y' 表示已穿透"
  "confidence": 0.78
}
```

### 5.3 USER 段（输入数据）

```
【报送目标】
报送项编码：{{ reporting_item.code }}
报送项名称：{{ reporting_item.name }}
口径定义：{{ reporting_item.definition or "（未抽到）" }}

【监管口径】
文号：{{ reg_document.document_no }}
生效日期：{{ reg_document.effective_date }}
首次报送：{{ reg_document.first_report_period }}
政策目的：{{ reg_document.regulatory_intent }}
原文摘录：{{ reporting_item.evidence_text }}

【可用字段清单（业务已勾选）】
{% for field in available_fields %}
- {{ field.code }}
  · 表：{{ field.table_name }}
  · 列：{{ field.column_name }}
  · 类型：{{ field.data_type }}
  · 业务含义：{{ field.business_meaning or "（未维护）" }}
  · 血缘角色：{{ field.lineage_role }}
{% endfor %}

【业务备注】
{{ business_note or "（无）" }}

请按 JSON schema 输出 SQL。
```

---

## 6 · 服务层

### 6.1 文件结构

```
backend/app/services/
  ticket_sql_generator.py    新增
backend/app/prompts/
  system_ticket_sql_v1.md    新增
```

### 6.2 主入口

```python
@dataclass
class SqlGenerationResult:
    status: str  # READY / DEGRADED / FAILED
    sql: str
    explanation: str = ""
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[SqlWarning] = field(default_factory=list)
    generated_by: str = ""


def generate_reference_sql(
    *,
    ticket: TicketDraft,
    reporting_items: list[ReportingItemContext],   # 该子单覆盖的报送项
    available_fields: list[FieldContext],           # 业务勾选的字段
    reg_document: RegDocumentContext,
    business_note: str = "",
) -> SqlGenerationResult:
    """生成参考 SQL，3 次重试 + 骨架兜底（同 Module D 风格）。"""
    ...
```

### 6.3 5 层校验（同 Module D 风格）

| 层 | 校验内容 | 失败处理 |
|---|---|---|
| L1 | JSON 合法 | 重试 |
| L2 | Pydantic schema（sql / explanation / confidence 必填） | 重试 |
| L3 | sqlglot 语法解析通过 | 标 SYNTAX_ERROR warning，仍展示，状态降为 DEGRADED |
| L4 | 提取 SQL 里所有 `table_name`，必须出现在 `available_fields` 的 table_name 内；不在则标 TABLE_NOT_IN_CATALOG warning | 标 warning，不阻塞 |
| L5 | 提取 SQL 里所有 `column_name`，必须出现在 `available_fields` 的 column_name 内；不在则标 FIELD_NOT_IN_SCOPE warning | 标 warning，不阻塞 |

**L3 失败 / 3 次重试全失败** → 返回骨架 SQL（`SELECT /* TODO */ FROM 表 WHERE ...`），confidence=0.2，status=DEGRADED。

### 6.4 sqlglot 字段提取

```python
import sqlglot
from sqlglot import expressions as exp

def extract_tables_and_columns(sql: str) -> tuple[set[str], set[str]]:
    tree = sqlglot.parse_one(sql, dialect="ansi")
    tables = {t.name for t in tree.find_all(exp.Table)}
    columns = {c.name for c in tree.find_all(exp.Column)}
    return tables, columns
```

`sqlglot` 已经在 Python 生态成熟，纯 Python 包，加进 `pyproject.toml` 即可。

---

## 7 · API 契约

### 7.1 `POST /api/tickets/{ticket_id}/reference-sql/generate`

触发生成。无 body。

响应：
```json
{
  "status": "READY",
  "ticket_id": 5012,
  "reference_sql": "-- 工单：...\nSELECT ...",
  "sql_dialect": "ANSI",
  "confidence": 0.78,
  "explanation": "按穿透后口径汇总修正久期，业务备注要求历史补录由 ETL 处理。",
  "assumptions": ["is_lookthrough='Y' 表示已穿透"],
  "warnings": [
    {
      "type": "FIELD_NOT_IN_SCOPE",
      "message": "字段 is_lookthrough 未在业务勾选清单内",
      "field_code": "is_lookthrough",
      "severity": "WARNING"
    }
  ],
  "generated_at": "2026-05-29T14:30:00Z",
  "generated_by": "sql_v1@qwen-plus"
}
```

### 7.2 `GET /api/tickets/{ticket_id}/reference-sql`

读取当前已保存的 SQL（含 warnings）。结构同上，无 SQL 时返回 `status=NOT_GENERATED`。

### 7.3 `PUT /api/tickets/{ticket_id}/reference-sql`

业务/开发手工编辑后保存。

请求体：
```json
{ "reference_sql": "...", "comment": "调整了聚合方式" }
```

响应：保存成功 + 重跑 L3-L5 校验后的 warnings。

`sql_status` 设为 `EDITED_BY_USER`，`sql_generated_by` 设为 `user:<username>`。

### 7.4 `POST /api/tickets/{ticket_id}/reference-sql/feedback`

```json
{ "thumbs": "up" | "down", "comment": "" }
```

写入 `sql_feedback_thumbs_*`。

### 7.5 `POST /api/tickets/{ticket_id}/reference-sql/mark-stale`

业务复核更新后由前端触发，把 sql_status 改为 STALE，提示"建议重新生成"。

---

## 8 · 工程拆分

| 任务 | 文件 | 工作量 | 谁做 |
|---|---|---|---|
| **Q1** DDL：`ticket_drafts` 加 8 个列 + `_ensure_ticket_draft_sql_columns()` | `db_models.py` / `database.py` | 0.3d | Claude |
| **Q2** 提示词模板 | `app/prompts/system_ticket_sql_v1.md` | 0.3d | Claude |
| **Q3** 服务 `ticket_sql_generator.py` + sqlglot 5 层校验 + 骨架兜底 | `services/ticket_sql_generator.py` | 1.2d | Claude |
| **Q4** 5 个 API 端点 | `routes_tickets.py`（如果没有就新建） / `routes_tasks.py` | 0.5d | Claude |
| **Q5** Pydantic schemas | `schemas.py` 加 `ReferenceSqlResponse` / `SqlWarning` / `SqlSaveRequest` | 0.2d | Claude |
| **Q6** 前端 SqlCard 组件 + monaco editor 集成 | `components/ReferenceSqlCard.vue` | 1.5d | Codex |
| **Q7** 集成进系统子单卡片 | 当前业务复核流改造完后的子单卡片 | 0.5d | Codex |
| **Q8** 前端 fixture + vitest | `fixtures/referenceSql.ts` + `__tests__/ReferenceSqlCard.test.ts` | 0.5d | Codex |
| **Q9** 后端 unit test + 3 个 eval case（happy / 字段编造 / 语法错） | `tests/test_ticket_sql_generator.py` | 0.8d | Claude |
| **Q10** sqlglot 依赖加进 `pyproject.toml` + `uv lock` | | 0.1d | Claude |

**总计：约 5.9 人日**，后端 3.4d / 前端 2.5d。

### MVP 砍法（赶演示能做的）
- 砍 Q5/Q6 反馈按钮 → 省 0.2d
- 砍 STALE 标记自动联动 → 省 0.2d
- 砍 monaco editor 用 `<textarea>` 替代 → 省 0.5d（**不推荐**，演示效果差异大）

MVP 范围约 **5 人日**。

---

## 9 · 与现有架构的契合

### 复用
| 现有能力 | 复用到 SQL 生成 |
|---|---|
| `RegDocument.regulatory_intent / effective_date / first_report_period` | 提示词监管口径段 |
| `DataFieldCatalog.business_meaning / data_type / table_name / column_name` | 提示词字段 schema 段 |
| `ReportingImpactReview.review_content` | 提示词"可用字段清单"段 |
| `TicketDraft.business_note` | 提示词业务备注段 |
| `llm_client.complete_json` | LLM 调用 |
| Module D 的 5 层校验范式 | 直接 copy 改造 |

### 新引入
| 新依赖 / 新表 | 用途 |
|---|---|
| `sqlglot` pypi 包 | SQL 语法校验 + 字段提取 |
| `@guolao/vue-monaco-editor` | 前端 SQL 编辑器 |

---

## 10 · 风险与缓释

| 风险 | 概率 | 影响 | 缓释 |
|---|---|---|---|
| LLM 编造表名 | 高 | 中 | L4 校验标 TABLE_NOT_IN_CATALOG warning，UI 黄色提示 |
| LLM 编造字段名 | 高 | 中 | L5 校验 + UI 提示业务"是否补充勾选" |
| 字段名相同但表不同导致歧义 | 中 | 中 | 提示词强制要求显式 alias（`ods_bond_position.modified_duration`） |
| 业务直接复制 SQL 上生产 | 中 | 高 | 顶部红色横幅 + 注释里"AI 参考" + 不提供"一键执行" |
| 复杂 SQL（窗口函数 / CTE）准确率低 | 中 | 中 | confidence < 0.5 时 UI 顶部贴"低置信，建议人工重写"标签 |
| 业务勾选字段但 schema 缺失业务含义 | 高 | 中 | 提示词内 fallback `"（业务含义未维护）"`，SQL 注释里标注"假设" |
| LLM 调用超时 / 失败 | 中 | 低 | 2 次重试 + 骨架 SQL 兜底，永远有结果可看 |
| 监管原文中口径表述模糊 | 高 | 中 | confidence 自动降低 + assumptions 字段输出推理假设，业务可看 |

---

## 11 · 演示口径

> "业务方确认完字段、写完备注后，每张系统子单底部多一段 AI 生成的参考 SQL —— 监管原文 + 字段 schema + 业务备注三件套拼成提示词喂给 LLM，输出带注释的 SELECT 语句。
>
> 后端用 sqlglot 解析这段 SQL，提取所有引用的字段名，逐个比对'业务勾选清单'，编造的字段会标黄告警 —— 不阻塞，但提示业务'要么补充勾选，要么核对是不是 AI 写错了'。
>
> SQL 业务可以直接复制给开发，开发也可以在前端 VSCode 同款编辑器里改完保存到工单。我们刻意没做'一键执行'按钮 —— 这是参考性 SQL，必须人工审核才能上生产。
>
> **这是把项目从 BI 风格的影响分析工具，升级到 AI 数据治理工程助手的最后一公里**。"

---

## 12 · 待你确认的 8 个决策点

| # | 问题 | 我的建议 |
|---|---|---|
| 1 | MVP 包含 monaco editor？ | **是**，3 行集成 `@guolao/vue-monaco-editor`，演示质变 |
| 2 | 触发方式：自动 / 手动 | **手动**，避免没看的工单浪费 token |
| 3 | 重新生成是否需二次确认？ | **是**，避免覆盖人工编辑成果 |
| 4 | 字段校验失败是否阻塞展示？ | **不阻塞**，标黄 + 提示，业务自决 |
| 5 | 语法错误是否阻塞展示？ | **不阻塞**，标红 + 显示原文供人工修正 |
| 6 | SQL 方言锁定 ANSI 还是支持选项？ | **MVP 锁 ANSI**，W2 加方言切换（MySQL / Oracle / PG） |
| 7 | 提示词版本管理是否复用 Module D 的 `planner_v1@<model>` 格式？ | **是**，统一为 `sql_v1@<model>` |
| 8 | 演示时铺到什么程度？ | **完整 5 人日**（含 monaco + 校验 + 反馈），少了任意一项演示效果都打折 |

---

## 13 · 开发顺序建议

业务复核 MVP 演示完成后接着做：

```
Day 1  Q10 sqlglot 依赖 + Q1 DDL（Claude，半天）
       Q2 提示词模板（Claude，半天）
       Q6 前端 monaco 集成骨架（Codex，1d）

Day 2  Q3 服务核心 + 5 层校验（Claude，1.5d）
       Q6 继续（Codex）

Day 3  Q4 API（Claude，半天）+ Q5 schemas（Claude，半天）
       Q7 子单卡片集成（Codex，半天）

Day 4  Q9 后端测试（Claude，1d）
       Q8 前端测试（Codex，半天）

Day 5  联调 + 手工演示彩排
```

---

待你回复 §12 的 8 个决策点，确认后我把 Q1-Q5/Q9/Q10 分给我自己，Q6/Q7/Q8 写一份 Codex 任务书放到 plans 下。
