# 监管报送变更影响分析 Backend

Python FastAPI 后端，当前主线是 1104 资金同业监管报送变更影响分析：

```text
监管材料上传
  -> 文档解析与任务画像
  -> 1104 报表目录和指标字段定位
  -> 报送指标到源系统字段的血缘召回
  -> 影响项生成
  -> 分类型工单草稿生成
```

后端不再以通用业务对象库作为主流程入口。早期规则库相关代码如仍存在，仅作为兼容或历史样例，不作为当前产品主线说明。

## 本地启动

```bash
uv sync
uv run uvicorn app.main:app --reload
```

默认服务地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

## 数据库

当前本地开发使用 MySQL：

```text
mysql+pymysql://reg_user:reg_pass_123@localhost:3306/reg_reporting?charset=utf8mb4
```

建表方式：应用启动时自动执行 `SQLModel.metadata.create_all(engine)`，**不依赖手写 migration**，新增模型类后重启即可建表。

SQLite 历史数据迁移到 MySQL：

```bash
uv run python -m scripts.migrate_sqlite_to_mysql
```

### 初始化样板数据（路线 A · seed 模式）

新环境第一次启动后，跑一次 bootstrap 把 1104 目录 + G31 字段血缘灌进库：

```bash
uv run python -m scripts.bootstrap_route_a
```

幂等，可重复跑。一次性完成：

1. `init_db()` 建/补全所有表（含三张血缘表 `data_system_catalog` / `data_field_catalog` / `reporting_item_lineage`）
2. 灌 1104 基础目录（5 张报表对象 + 章节 + 1 个 G31 粗粒度 item）
3. 兜底插入 5 个 G31 详细 item（`G31.PART_I.1_0.A` ~ `E`）—— 这些 item 原本由 Excel 解析产生，bootstrap 里硬编码补齐
4. 灌 G31 字段目录（7 系统 / 25 字段）+ 36 条血缘
5. 终端打印 D 列实际命中的 7 条血缘作为校验

> 这是"路线 A"——血缘暂时用 mock 数据演示。生产化时应改为对接元数据平台（SQL 解析、ETL 配置同步、人工录入）。

### 数据库表清单（共 22 张）

> ORM 框架：SQLModel（SQLAlchemy + Pydantic）| 定义文件：`app/models/db_models.py`

---

#### 一、核心主线表（5 张）

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `reg_documents` | **监管文件入口表**。记录每次上传的监管材料（PDF、Word 等），含全文解析结果和质量评分 | `filename`、`parsed_text`、`parse_status`、`parse_quality`、`char_count` |
| `reg_tasks` | **变更分析任务主线表**。每份文件对应一个任务，驱动"画像→影响→工单"全流程 | `document_id`、`status`（CREATED / IMPACT_ANALYZED / TICKET_GENERATED）、`risk_level` |
| `document_task_profiles` | **文档 AI 画像表**。LLM 对文件的分析结论：受影响报表代码、变更信号、是否进入报送影响分析 | `affected_table_codes`、`change_signals`、`in_scope_tables`、`confidence_score`、`llm_model` |
| `ticket_drafts` | **工单草稿输出表**。生成的可复核工单全文（Markdown 格式） | `task_id`、`title`、`content` |
| `audit_logs` | **操作审计日志**。记录系统所有动作（上传 / 分析 / 生成等） | `action`、`target_type`、`target_id`、`detail` |

---

#### 二、监管报送目录表（7 张）

静态参考数据，通过 `POST /api/reporting/seed-1104` 初始化。一期聚焦 **1104 资金同业**域（G21 / G24 / G25 / G27 / G31 报表）。

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `reg_reporting_systems` | **报送体系定义**。如 1104 非现场监管报表、EAST、客户风险、一表通 | `system_code`、`system_name`、`regulator` |
| `reg_reporting_versions` | **报送版本管理**。记录每个体系的版本迭代（如 1104 v2024Q1） | `version_code`、`effective_date`、`source_file` |
| `reg_reporting_objects` | **报表对象**。报送体系下的每张报表（如 G21、G24） | `object_code`、`object_name`、`report_frequency`、`submit_deadline` |
| `reg_reporting_sections` | **报表分区 / 章节**。报表内的行列分区（如"资产端"、"负债端"） | `section_code`、`section_name`、`display_order` |
| `reg_reporting_items` | **报送指标字段（核心）**。报表中每一个具体指标，是影响分析的最小颗粒单元 | `item_code`（全局唯一）、`item_name`、`definition`、`fill_requirement` |
| `reg_reporting_instructions` | **填报说明**。指标的详细填写说明文字 | `instruction_code`、`instruction_text`、`source_reference` |
| `reg_reporting_rules` | **指标校验 / 勾稽规则**。报表内或跨报表的校验表达式 | `rule_code`、`rule_expression`、`risk_level` |

---

#### 三、数据血缘表（3 张）

记录"报送指标 ↔ 企业内数据字段"的映射关系，是影响分析的核心依据。

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `data_system_catalog` | **数据系统目录**。企业内部各数据系统清单（核心系统、风控系统、账务系统等） | `system_code`、`system_name`、`owner_team` |
| `data_field_catalog` | **数据字段目录**。各系统中的具体字段清单，含业务含义和归属团队 | `field_code`（全局唯一）、`table_name`、`column_name`、`business_meaning`、`data_system_id` |
| `reporting_item_lineage` | **指标血缘关系（核心）**。`reg_reporting_items` ↔ `data_field_catalog` 的映射，含血缘角色（SOURCE_FIELD / DIMENSION / FILTER）和转换表达式 | `reporting_item_id`、`data_field_id`、`lineage_role`、`transform_expression`、`confidence_level` |

---

#### 四、影响分析结果表（2 张）

每次执行影响分析后写入，可反复覆盖（替换策略）。

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `reg_reporting_change_candidates` | **变更候选项**。LLM 或关键词匹配识别出的"某指标疑似受本次监管变更影响"的记录，含置信度和人工审核状态 | `reporting_item_code`、`change_type`、`evidence_text`、`confidence_score`、`review_status` |
| `reg_reporting_impact_items` | **精确影响分析结果**。结合血缘表生成的具体影响项，含受影响源字段、血缘角色和建议处理动作 | `reporting_item_code`、`impact_type`、`impacted_source_fields`（JSON）、`recommended_action` |

---

#### 五、规则库表（5 张）

用于从监管条款中提取和管理规则资产，流程尚在建设中。

| 表名 | 说明 | 关键字段 |
|---|---|---|
| `reg_clauses` | **文档条款**。将监管材料拆分为结构化条文（章节 / 条号 / 层级），是规则提取的输入 | `document_id`、`clause_no`、`clause_text`、`clause_level`、`text_hash` |
| `reg_semantic_items` | **语义项**。从条款提取的语义要素（如适用主体、报送频率、准入条件） | `clause_id`、`semantic_type`、`semantic_value`、`confidence_score` |
| `rule_cards` | **规则卡片**。结构化描述一条监管规则：适用主体、影响业务对象、影响系统、建议工单类型 | `clause_id`、`rule_type`、`applicable_subject`、`impacted_objects`（JSON）、`impacted_systems`（JSON） |
| `validation_rules` | **可执行校验规则**。从规则卡片中提取的具体校验表达式，供下游合规系统使用 | `rule_code`、`rule_expression`、`applicable_object`、`source_rule_card_id` |
| `review_records` | **人工审核记录**。通用审核流水，支持对任意目标类型（规则 / 影响项 / 工单）的审核意见记录 | `target_type`、`target_id`、`review_role`、`review_result`、`before_value`、`after_value` |

---

#### 数据流向

```
reg_documents          # 1. 上传文件
  └─> reg_tasks                    # 2. 创建任务
  └─> document_task_profiles       # 3. AI 画像（受影响报表代码）

reg_reporting_systems              # 参考数据（seed-1104 初始化）
  └─> reg_reporting_versions
  └─> reg_reporting_objects
      └─> reg_reporting_sections
      └─> reg_reporting_items      # 核心指标 ←→ reporting_item_lineage
                                   #                └─> data_field_catalog
                                   #                    └─> data_system_catalog

reg_tasks
  └─> reg_reporting_change_candidates  # 4. 影响分析：变更候选项
  └─> reg_reporting_impact_items       # 5. 影响分析：精确影响项
  └─> ticket_drafts                    # 6. 工单草稿生成
```

## 监管报送目录接口

| 方法 | 地址 | 说明 |
|---|---|---|
| `POST` | `/api/reporting/seed-1104` | 初始化 1104 资金同业报表目录、指标字段、数据字段和血缘样板 |
| `GET` | `/api/reporting/objects?reporting_system_code=1104` | 查询 1104 报表对象 |
| `GET` | `/api/reporting/items?reporting_system_code=1104` | 查询 1104 指标字段 |
| `GET` | `/api/reporting/items/{item_code}/lineage` | 查询某个报送指标到报送字段、源字段、维度字段的血缘 |

## 任务流程接口

| 方法 | 地址 | 说明 |
|---|---|---|
| `POST` | `/api/documents/upload` | 上传监管材料并解析正文 |
| `POST` | `/api/documents/{document_id}/profile` | 生成文档级任务画像，判断是否进入监管报送影响分析 |
| `POST` | `/api/tasks/from-document/{document_id}` | 从监管材料创建任务 |
| `GET` | `/api/tasks/{task_id}/workflow` | 聚合返回任务、文档、报送候选、血缘候选、影响项和工单草稿 |
| `POST` | `/api/tasks/{task_id}/analyze-impact` | 识别 1104 报送变更并根据血缘生成影响项 |
| `POST` | `/api/tasks/{task_id}/generate-ticket` | 生成 1104 资金同业影响分析工单草稿 |

## RAG 边界

首期不依赖 RAG 完成主流程。后端优先使用结构化报送目录、指标字段和血缘表做定位与影响分析。

RAG 后续只作为辅助能力：

- 从监管材料、填报说明、会议纪要中召回依据片段。
- 从历史影响项、历史工单和人工确认记录中召回相似案例。
- 在人工复核页辅助解释“为什么命中这个报表/指标/字段”。

RAG 不能替代报表目录、指标血缘和人工复核，也不能直接写库或直接生成最终工单。

## 测试

```bash
uv run pytest -q
```

重点测试范围：

- 1104 资金同业种子目录和血缘查询。
- 监管材料到报送变更候选的识别。
- 基于 `reporting_item_lineage` 的影响项生成。
- 工单草稿内容是否围绕报送指标、报送字段和源字段展开。
