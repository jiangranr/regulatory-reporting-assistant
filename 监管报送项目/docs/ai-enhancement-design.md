# 监管报送 AI 增强：三大痛点整体设计

> 更新日期：2026-05-30  
> 文档定位：三大业务痛点的统一设计文档，替代此前三份分散文档作为权威参考。  
> 关联文档：[血缘低维护（草稿）](lineage-low-maintenance-design.md) / [指标问答 Agent（草稿）](indicator-qa-agent-design.md)

---

## 0. 全局视角：三个痛点不是三个功能

三个痛点共享同一套数据基础，彼此之间是**生产-消费关系**，形成一个数据飞轮：

```
┌─────────────────────────────────────────────────────────────────────┐
│                        监管发文 / 填报说明                           │
└───────────────┬─────────────────────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  痛点 1：血缘低维护                                                   │
│  · 铺底：把"参与报送的表的全字段"录入字段目录                         │
│  · 审核：业务确认后血缘状态写回 DB                                    │
│  · 变更检测：监管字段新增/删除/修改 → 六路由工单                      │
│       └─ ADDED+未命中 → 调痛点3推荐引擎预填候选来源                  │
└──────────┬──────────────────────────────────────────────────────────┘
           │  血缘图（ReportingItemLineage）完善
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────────────────────────────────────────────────┐
│ 痛点 3  │  │  痛点 2：指标问答 Agent                               │
│ 来源推荐 │  │  · 解释模式：RAG + LLM + 监管答疑检索               │
│（见§3） │  │  · 排查模式：调用血缘图做假说生成（消费痛点1的产出） │
└────┬────┘  └──────────────────────────────────────────────────────┘
     │
     └── 推荐结果预填 → 痛点1工单 → 业务确认 → 血缘写回（飞轮闭合）
```

**实现顺序因此由依赖关系决定，不能并行乱序**：痛点 1 的基础数据必须先就绪，痛点 2 的排查模式和痛点 3 才能真正有效。

---

## 1. 共享基础设施

三个痛点都依赖以下两项共建，先于各痛点功能开发。

### 1.1 DataFieldCatalog 扩展（字段目录补全）

**现状**：`DataFieldCatalog` 只记录了有血缘映射的字段，即"已经参与报送的字段"。

**目标**：扩展为"参与报送的**表**的全字段"——凡是有任何一个字段参与报送的表，其所有字段都应入册，无论该字段是否已有血缘。

**为什么不做"全系统全字段"**：范围太重，引入大量无关系统；且新增监管指标的数据来源大概率还在现有报送生态内，不会凭空来自从未接入的系统。若真需全新系统，那是系统集成级决策，AI 推荐不了，应升级人工处理。

**扩展路径**：
```
ReportingItemLineage → DataFieldCatalog.table_name 去重
  → 得到"参与报送的表"清单
  → 对这些表采集全字段，补入 DataFieldCatalog（lineage 状态 = 空）
```

Demo 阶段：在种子数据中手动扩展每张表的字段覆盖。  
生产阶段：对接各源系统的元数据 API，定期同步。

**影响**：痛点 2 的血缘追溯更丰富；痛点 3 的语义搜索覆盖面更宽。

### 1.2 Embedding 基础设施

两处需要 embedding：
- 填报说明文本（`RegReportingInstruction`）→ 供痛点 2 的 RAG 检索
- `DataFieldCatalog` 字段名 + 描述 → 供痛点 3 的语义匹配

**Demo 方案**：embedding 结果存为 BLOB，Python 端用 numpy 做余弦相似度计算。规模小，够用。  
**生产方案**：引入向量数据库（pgvector 或独立 Qdrant），需提前规划。

新增表：
```python
class RegInstructionEmbedding(SQLModel, table=True):
    __tablename__ = "reg_instruction_embeddings"
    id / instruction_id / embedding: bytes / model_version: str

class DataFieldEmbedding(SQLModel, table=True):
    __tablename__ = "data_field_embeddings"
    id / field_id / embedding: bytes / model_version: str
```

---

## 2. 痛点 1：血缘低维护

### 2.1 问题

业务需要手工录入每个概念和血缘关系，维护成本高，导致知识库长期停留在演示数据状态。

### 2.2 改造方向

将"维护"拆成两段：一次性铺底（冷启动）+ 监管驱动增量更新（变更推送）。  
业务角色从"事前录入"变为"事后确认"。

### 2.3 铺底

**数据源**：Demo 使用模拟种子数据；生产对接监管系统定期拉取字段目录。  
**审核规则**：业务确认后直接写库，无额外审批流。

核心操作：将 `ReportingSeedCatalog.lineage` 持久化到 `ReportingItemLineage`，补充 `mapping_status = SEED_CONFIRMED`。

### 2.4 审核确认写回血缘

现有 `POST /tasks/{id}/impact-review/confirm` 只生成工单草稿，**不更新血缘**。需补充：

```
confirm 成功后 → apply_confirmed_review_to_lineage(review, session)
  · item.removed=True          → 该指标所有血缘 mapping_status=RETIRED
  · field selected, source=AI  → upsert, mapping_status=CONFIRMED
  · field removed/deselected   → mapping_status=RETIRED
  · field source=BUSINESS      → 新建 ReportingItemLineage, mapping_status=CONFIRMED
```

### 2.5 监管字段变更六路由工单

监管发文解析后，新增字段目录版本对比步骤，输出变更清单，按以下矩阵路由工单：

| 变更类型 | 命中知识库 | 工单动作 | 工单类型 |
|---|---|---|---|
| 新增 | 命中（有候选血缘）| 生成工单，预填候选血缘 | `DATA_MAPPING` |
| 新增 | **未命中** | 调推荐引擎（见§3）预填推荐来源，生成工单 | `LINEAGE_BUILD` 高优先级 |
| 删除 | 命中 | 生成退役工单，附影响范围分析 | `REPORT_DECOMMISSION` |
| 删除 | 未命中 | 记录日志，不生成工单 | — |
| 变更 | 命中 | 生成工单，附口径 diff | `DATA_MAPPING` |
| 变更 | 未命中 | 生成告警型工单（可能漏录血缘）| `LINEAGE_BUILD` 高优先级 |

"命中"定义：`ReportingItemLineage` 中存在该 `item_code` 的任意记录（不论 `mapping_status`）。

### 2.6 工单确认影响血缘

字段变更工单被业务确认后，根据工单类型更新血缘：
- `LINEAGE_BUILD`（新增/告警处理）→ 创建新 `ReportingItemLineage`，`mapping_status=CONFIRMED`
- `DATA_MAPPING`（变更）→ 更新已有记录，`mapping_status=CONFIRMED`
- `REPORT_DECOMMISSION`（删除）→ `mapping_status=RETIRED`

### 2.7 实现步骤

| 步骤 | 内容 | 主要影响文件 |
|---|---|---|
| **A** | 种子血缘写入 DB | `catalog_ingestor.py`（新增 `ingest_lineage_from_seed`）|
| **A'** | DataFieldCatalog 扩展到参与报送的表全字段 | 种子数据扩充 + `catalog_ingestor.py` |
| **B** | 审核确认写回血缘 | `impact_review_service.py`（新增 `apply_confirmed_review_to_lineage`）|
| **C1** | 字段变更记录数据模型 | `db_models.py`（新增 `RegFieldChangeRecord`）|
| **C2** | 字段变更检测服务 | 新建 `field_change_detector.py` |
| **C3** | 六路由工单生成（含 P3 推荐引擎调用）| 新建 `field_change_ticket_router.py` |
| **C4** | 字段变更 API 端点 | `routes_tasks.py`（新增 3 个端点）|
| **D** | 工单确认影响血缘 | `db_models.py`（`TicketDraft` 补 `status`）、`routes_tasks.py` |

---

## 3. 痛点 3：新增指标来源推荐

> 设计上痛点 3 是痛点 1 "ADDED+未命中"分支的增强，不是独立功能。  
> 推荐引擎由痛点 1 的 Step C3 调用，也支持业务手动触发。

### 3.1 问题

监管新增指标时，业务难以判断数据应取自哪个系统哪张表。现有血缘只覆盖已报送字段，新指标没有直接匹配，需要相似性推荐。

### 3.2 推荐引擎：两步走

三层级联的设计是过度工程。Layer 1（继承相似指标的源字段）假设"定义相似 = 来源相同"，在新增指标通常是旧指标加条件的场景下不成立，容易误导业务。实际上只需两步：

```
新指标定义（item_name + definition）
        ↓
第一步：字段候选检索
  · 在 DataFieldCatalog（仅"参与报送的表"范围）
    做关键词 + 语义双路搜索，取 top-10 候选字段
  · 前提：字段目录中字段要有业务描述（field_name + business_meaning）
    若字段只有短名称，语义搜索退化为关键词匹配，效果有限
        ↓
第二步：LLM 推理排序
  · 输入：新指标定义 + top-10 候选字段（含所属系统）
           + DataSystemCatalog 各系统描述
  · LLM 输出：
    - 哪些字段最可能是来源，以及原因（明确的自然语言解释）
    - 是否需要组合多个字段
    - 是否需要过滤条件（标注为"AI 建议，需人工确认"）
    - 若候选都不合适，说明可能需要引入新数据源
```

这个设计的好处：推理过程透明，业务能看懂 LLM 给的理由，可以判断对不对；不靠精确数字，不制造伪精确感。

### 3.3 推荐结果格式

```json
{
  "item_name": "绿色贷款余额",
  "candidates": [
    {
      "rank": 1,
      "system_name": "信贷系统",
      "field_code": "loan_balance",
      "field_name": "贷款余额",
      "reasoning": "贷款余额是最直接的来源字段；绿色贷款口径需叠加用途标识过滤，建议确认信贷系统是否有 green_flag 或 loan_purpose 字段",
      "ai_note": "过滤条件为 AI 推断，需人工核实源系统字段实际含义"
    },
    {
      "rank": 2,
      "system_name": "信贷系统",
      "field_code": "green_loan_flag",
      "field_name": "绿色贷款标识",
      "reasoning": "字段名直接对应绿色贷款概念，若该字段存在可作为过滤维度",
      "ai_note": "字段是否实际落库需与源系统团队确认"
    }
  ],
  "unresolved": false,
  "llm_summary": "建议以信贷系统 loan_balance 为主来源字段，叠加绿色贷款标识过滤。若信贷系统无绿色分类字段，可能需要引入合规/绿金系统数据。"
}
```

不展示精确置信度数字——LLM 给出的是推理文本，业务根据理由判断可信度，而不是根据小数点后两位。`unresolved=true` 时 `llm_summary` 说明需要引入新数据源，工单标注升级人工处理。

### 3.4 触发方式

| 触发场景 | 调用方式 |
|---|---|
| 痛点 1 变更检测，ADDED+未命中 | C3 路由工单时自动调用，结果预填工单 |
| 业务主动咨询 | 痛点 2 问答 Agent 识别意图后调用 |

### 3.5 实现步骤

| 步骤 | 内容 | 主要影响文件 |
|---|---|---|
| **A'** | DataFieldCatalog 扩展（共享基础设施，同痛点 1）| — |
| **E2** | DataFieldCatalog embedding 索引 | 新建 `services/embedding_indexer.py` |
| **F2** | 三层推荐引擎 | 新建 `services/source_recommender.py` |
| **H2** | 推荐 API 端点 | `routes_tasks.py` 或新建 `routes_recommender.py` |

---

## 4. 痛点 2：指标问答 Agent

### 4.1 问题

- 业务填报时需要翻 PDF 查指标含义，耗时费力
- 报送异常后需要跨系统排查原因，缺乏结构化引导

### 4.2 Agent 整体架构

```
业务自然语言输入
        ↓
   意图识别（LLM）
        ├─ 解释模式：问指标含义 / 填法
        └─ 排查模式：指标数值异常
```

两个模式共享工具层，Agent 根据意图选择工具组合。

### 4.3 解释模式

**回答结构**（按块组织，缺数据的块跳过）：
1. 指标基本信息（编码、报表、频度、单位）
2. 填报说明原文（RAG 召回，保留官方表述）
3. 通俗解释（LLM 生成，面向非技术业务人员）
4. 口径要点（LLM 从填报说明提炼，列关键注意事项）
5. 监管官方答疑（web search，仅检索官方来源，标注 URL 和日期）
6. 相关工单历史（本系统内历史工单处理经验摘要）

**关于"监管官方答疑"**：web search 返回的结果无法程序化地可靠区分官方和非官方来源，不做"仅检索官方"的承诺。实际处理：搜索结果原样展示给用户，注明"以下为网络检索结果，请自行判断来源可信度"，由用户决定是否采用。检索不到时跳过此块，不捏造内容。

**RAG 语料来源**：

真实填报说明文档（.doc 格式，后端 `doc_parser.py` 已支持解析）：

| 报表 | 文件 | 说明 |
|---|---|---|
| G01 主表 | `G01填报说明（251）.doc` | 资产负债综合报表，指标最多 |
| G01_IV | `G01_IV填报说明（251）.doc` | G01 第四部分 |
| G01_V | `G01_V填报说明（251版）.doc` | G01 第五部分 |
| G01_VII | `G01_VII填报说明（251版）.doc` | G01 第七部分 |
| G31 | `G31填报说明（251）.doc` | 投资业务表，含修正久期等复杂指标 |

G21/G24/G25/G27 的填报说明不在本次 251 版修订文件中，RAG 知识库暂不覆盖，Demo 演示使用 G01 和 G31。

**切片与召回策略**：

标准 RAG 流程，不做额外的元数据预过滤：

```
doc_parser.py 解析 .doc 原文
  ↓
按自然段落切片（约 300-500 token / 块）
每块开头附来源标注，如"G31《投资业务情况表》· 第三部分 · 列项目"
  ↓
整块文本 → embedding → 存入 RegInstructionEmbedding
  ↓
用户提问 → 查询向量 → 余弦相似度 → 取 top-5 块
  ↓
将原文块作为上下文交给 LLM 生成回答

跨报表同名指标（如"余额"在 G01 和 G31 含义不同）：
  LLM 读到来自不同来源的块，自然在回答中说明差异，无需提前设计过滤逻辑。
```

注：`item_code` 仅用于**精确查找**场景（工单/血缘表中已知具体指标时直接定位原文），与 RAG 语义检索是两条独立路径，不混用。

### 4.4 排查模式

**核心定位**：生成带证据的排查假说清单，**不给结论**。最终判断由业务人员做，AI 只负责把 80% 的排查工作结构化前置。

**回答结构**：
```
【异常概况】
  指标名称 / 本期值 / 上期值 / 变化幅度（由业务输入）

【假说清单（按优先级）】
  ✅ 假说 1：监管口径近期有变化   ← 系统内有数据，必查
  ✅ 假说 2：血缘上游数据质量问题 ← 系统内有数据，必查
  ⚠️ 假说 3：同表指标同向异动    ← 需数值数据，条件具备才展示
  ❌ 假说 4：业务事件            ← 固定标注 AI 无法分析

【建议排查顺序】
【一键生成排查工单（可选）】
```

**用户输入处理**：Agent 接受自然语言描述，不强制要求精确数值。

| 输入形式 | 示例 | Agent 行为 |
|---|---|---|
| 只描述现象 | "修正久期这期取值异常" | 识别指标 → 生成假说清单（不展示数值对比）|
| 带数值 | "修正久期从 3.2 变成 5.8" | 识别指标 + 解析数值 → 假说清单 + 数值概况展示 |

假说 1/2/4 不依赖数值，只需 item_code 即可运行；假说 3 有数值时展示，无数值时跳过。

**假说生成对应工具调用**：

| 假说 | 工具 | 数据来源 | 是否依赖数值 |
|---|---|---|---|
| 口径变化 | `get_regulatory_changes(item_code)` | `RegReportingChangeCandidate` + `TicketDraft` | 否 |
| 血缘质量 | `get_item_lineage(item_code)` | `ReportingItemLineage`（依赖痛点1铺底）| 否 |
| 同表对比 | `get_peer_report_data(report, period)` | 用户输入数值或数值接口（可选）| 是，无则跳过 |
| 业务事件 | 固定输出，不调工具 | — | 否 |

**假说 4 固定输出内容**：
> "业务事件（大额交易、新产品上线、客户结构变化）需结合业务源系统数据人工判断，本 AI 无法访问业务系统，请与业务条线确认本期是否有异常业务发生。"

### 4.5 工具清单

| 工具名 | 输入 | 输出 | 可用时机 |
|---|---|---|---|
| `search_instruction_rag` | 自然语言问题 | 填报说明相关段落（top-5）| Step E1 完成后 |
| `get_item_lineage` | item_code | 血缘路径 | 痛点1 Step A 完成后 |
| `get_regulatory_changes` | item_code | 变更记录列表 | ✅ 现在就有 |
| `get_related_tickets` | item_code | 历史工单摘要 | ✅ 现在就有 |
| `web_search_regulatory_qa` | 指标名关键词 | 网络检索结果（用户自判来源）| Step E1 配套 |
| `recommend_source` | item_name + definition | 候选来源 + LLM 推理文本 | 痛点3 Step F2 完成后 |
| `create_ticket_from_analysis` | item_code + 假说列表 | ticket_id | ✅ 现在就有 |

### 4.6 实现步骤

| 步骤 | 内容 | 主要影响文件 |
|---|---|---|
| **E1** | 填报说明 Embedding | `db_models.py`（新增 `RegInstructionEmbedding`）、新建 `embedding_indexer.py` |
| **F1** | 工具层实现 | 新建 `services/indicator_qa_tools.py` |
| **G** | Agent 编排层 | 新建 `services/indicator_qa_agent.py` |
| **H1** | API 端点 | 新建 `api/routes_indicator_qa.py` |
| **I** | 前端对话界面 | 新建 `IndicatorQAView.vue` |

---

## 5. 数据模型变更汇总

| 新增/修改 | 类型 | 用途 |
|---|---|---|
| `RegFieldChangeRecord` | 新增表 | 记录字段版本变更（新增/删除/修改）和路由结果 |
| `RegInstructionEmbedding` | 新增表 | 填报说明 embedding 向量 |
| `DataFieldEmbedding` | 新增表 | 字段目录 embedding 向量 |
| `TicketDraft.status` | 新增字段 | 工单状态（OPEN/CONFIRMED/CLOSED/IGNORED）|
| `ReportingItemLineage.mapping_status` | 补充枚举 | SEED_CONFIRMED / CONFIRMED / RETIRED / DRAFT |

---

## 6. 完整实现步骤表

```
基础层（必须最先完成）
  A   种子血缘写入 DB
  A'  DataFieldCatalog 扩展到参与报送的表全字段
  E1  填报说明 Embedding
  E2  DataFieldCatalog Embedding
        ↓
痛点 1 核心
  B   审核确认写回血缘
  C1  字段变更记录数据模型
  C2  字段变更检测服务
        ↓ （A' + E2 就绪后）
痛点 3（嵌入痛点 1）
  F2  三层推荐引擎
        ↓
痛点 1 路由层
  C3  六路由工单生成（含推荐引擎调用）
  C4  字段变更 API 端点
        ↓ （E1 就绪后，可与 C3/C4 并行）
痛点 2
  F1  问答工具层
  G   Agent 编排层
  H1  问答 API 端点
        ↓
收尾
  D   工单确认影响血缘
  I   前端对话界面
```

---

## 7. 设计决策记录

> 2026-05-30 与业务讨论后确认。

| 问题 | 决策 |
|---|---|
| 排查模式指标数值来源 | 用户自然语言输入，有数值展示，无数值跳过假说3，不强制 |
| Embedding 存储方案 | Demo 阶段用二进制字节+numpy余弦相似度，生产阶段升级向量数据库 |
| Web Search API | 待定（Tavily 优先，无限制则使用）|
| 推荐引擎前端入口 | 不做独立入口，通过问答 Agent 触发；痛点1检测到新增字段时自动调用 |

---

## 8. Demo 计划

### 8.1 种子数据准备

| 数据集 | 内容 | 用途 |
|---|---|---|
| 现有种子血缘 | G21/G24/G25/G27/G31 指标 + 源字段血缘 | 痛点 1 铺底、痛点 2 排查基础 |
| 扩展字段目录 | 上述报表所在表的全字段（含无血缘字段）| 痛点 3 推荐语料 |
| 模拟新增指标 | G31 新增 2-3 个无血缘指标（如绿色债券相关）| 演示推荐引擎三层效果 |
| 变更记录 | 由真实监管文件上传流程产生，不编造 | 演示六路由工单 |
| RAG 知识库 | G01（主表/IV/V/VII）+ G31 填报说明 .doc，共 5 个文件，解析切片后建 embedding | 痛点 2 解释模式 |

### 8.2 Demo 路径

**路径 A（痛点 1）**：上传模拟监管发文 → 系统检测字段变更 → 生成三类工单 → 业务确认 → 血缘表状态更新

**路径 B（痛点 2 解释模式）**：业务输入"G31 修正久期怎么计算" → RAG 召回填报说明原文（含 MD=-(dP/P)/dy 公式）→ LLM 通俗解释 + 口径要点 → 展示监管答疑（若检索到）

**路径 C（痛点 2 排查模式）**：业务输入"修正久期这期取值异常" → Agent 识别指标 → 检查口径变更 + 血缘追溯 → 假说清单 → 一键生成排查工单

**路径 D（痛点 3）**：演示新增指标工单被自动预填推荐来源 → 展示三层推荐的置信度和推理依据

---

## 9. 与业务沟通的整体话术

> 这套系统解决的是三件高频但费脑筋的事：
>
> **第一件**：血缘不用你一条条填——我们帮你从现有报表把历史血缘铺进去，后续监管发文一有变动，系统自动检测、自动开工单，你只需要点确认。
>
> **第二件**：指标不用翻 PDF——直接问系统，它会给你官方填报说明的提炼版，还能帮你查监管有没有公开答疑过这个指标。
>
> **第三件**：异常不用自己猜——系统帮你查口径有没有变、数据上游有没有问题，给你一张排好优先级的排查清单，结论还是你来下，但 80% 的排查工作 AI 先做了。
