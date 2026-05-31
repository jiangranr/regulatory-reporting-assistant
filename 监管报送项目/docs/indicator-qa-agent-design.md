# 痛点改造：指标问答 Agent 设计

> 更新日期：2026-05-30  
> 文档定位：将"指标含义解释"和"报送异常排查"统一为一个 Agent，复用血缘图、监管变更记录、工单历史等现有资产。

---

## 1. 痛点描述

### 1.1 指标解释痛点

业务在填报时遇到不熟悉的指标，现有做法是翻填报说明 PDF——文档冗长、搜索困难、口径描述晦涩。他们希望能直接问系统"这个指标是什么意思、怎么填"，得到一个通俗易懂的答案。

### 1.2 异常排查痛点

某个指标数值与上期差异过大触发异常预警后，业务需要自行判断原因——是数据问题、口径变化、还是真实业务波动。这个排查过程通常要跨多个系统，耗时且依赖经验。

### 1.3 为什么合并成一个 Agent

两个痛点共用同一套数据基础：

```
填报说明 + 血缘图 + 监管变更历史 + 工单历史
```

解释指标和排查异常，本质上都是"围绕一个指标聚合所有相关知识"，Agent 根据问题意图选择调用不同工具即可，不需要两套系统。

---

## 2. Agent 设计

### 2.1 整体架构

```text
业务输入（自然语言）
    ↓
意图识别（LLM classify）
    ├─ 解释模式  →  填报说明 RAG + LLM 通俗解释 + 监管答疑检索
    └─ 排查模式  →  监管变更检查 + 血缘追溯 + 工单历史 + 假说清单生成
         ↓
结构化回答（Markdown 分块，带证据来源链接）
```

### 2.2 意图识别规则

| 输入特征 | 识别为 | 示例 |
|---|---|---|
| 含"什么意思"、"怎么填"、"口径"、"定义" | 解释模式 | "G25 流动性覆盖率怎么算的？" |
| 含"异常"、"差异大"、"波动"、"跌了"、"涨了" | 排查模式 | "G21 期限缺口这期比上期大了 30%，什么原因？" |
| 同时包含两类特征 | 先解释后排查 | "这个指标是什么意思，为什么这期会异常？" |
| 无法识别 | 解释模式（兜底） | — |

---

## 3. 解释模式

### 3.1 回答结构

```
【指标基本信息】
  - 指标编码：G25.PART_I.LCR
  - 所属报表：流动性覆盖率和净稳定融资比例情况表（G25）
  - 报送频度：月报
  - 单位：%

【填报说明原文（RAG 召回）】
  引用原文段落，保留官方表述

【通俗解释（LLM 生成）】
  用业务能听懂的语言解释这个指标衡量什么、为什么重要

【口径要点（LLM 提炼）】
  - 分子包含哪些资产
  - 分母口径
  - 常见填报误区

【监管官方答疑（网络检索，若有）】
  检索到的监管公开解释或行业指引，注明来源和日期

【相关工单历史（系统检索）】
  本系统中历史上针对该指标的已闭合工单（若有），给出处理经验摘要
```

### 3.2 RAG 召回设计

填报说明文档已入库（RegDocument），需要额外做：
- 对解析后的 `parsed_text` 做分段（按填报说明的结构：按指标/行列项切分）
- 对每段做向量 embedding，存入向量表
- 查询时按指标编码做精确过滤 + 语义相似度排序，取 top-3 段落

```text
查询路径：
  item_code（指标编码）
    → RegReportingItem.item_code 精确匹配
    → RegReportingInstruction（该指标的填报说明段落）
    → embedding 语义检索补充（跨段落关联内容）
```

已有 `RegReportingInstruction` 表，直接关联到 `reporting_item_id`，是 RAG 的主要数据源。

### 3.3 监管官方答疑检索

定位：**不是查"同业怎么填"，而是查"监管有没有官方答疑"**。

检索来源：
- 银保监 / 国家金融监督管理总局官网公开问答
- 中国人民银行公开指引
- 中国银行业协会发布的填报指引
- 监管培训材料中涉及该指标的说明

检索方式：web search，关键词组合 = 指标名称 + 监管机构 + 答疑/解释/指引。

输出要求：
- 必须标注来源 URL 和发布日期
- 检索不到时直接跳过此块，不捏造内容
- 不呈现非官方来源（论坛、自媒体）

---

## 4. 排查模式

### 4.1 回答结构

```
【异常概况】
  指标：G21.MAIN.LIQUIDITY_GAP_30D（30 日内流动性期限缺口）
  本期值：-120 亿元 | 上期值：-85 亿元 | 变化：+41%
  触发阈值：环比变化 > 20%

【假说清单（按优先级排序）】
  ✅ 假说 1：监管口径近期有变化
  ✅ 假说 2：血缘上游数据质量问题
  ⚠️ 假说 3：同表相关指标同向异动（需数值数据确认）
  ❌ 假说 4：业务事件（超出 AI 分析范围，需人工确认）

【各假说证据详情】
  （逐条展开，见 4.2）

【建议排查顺序】
  第 1 步 → 第 2 步 → ...

【生成排查工单（可选）】
  一键生成工单，分配给相关责任人
```

### 4.2 假说生成逻辑（对应工具调用）

**假说 1：监管口径变化**

```
调用：get_regulatory_changes(item_code)
  → 查 RegReportingChangeCandidate + TicketDraft
  → 该指标近 N 个月内是否有口径变更工单
输出：
  - 有变更：列出变更内容、生效日期、关联工单编号
  - 无变更：排除此假说
```

**假说 2：血缘上游数据质量**

```
调用：get_item_lineage(item_code)
  → 查 ReportingItemLineage → DataFieldCatalog → DataSystemCatalog
  → 返回该指标的完整血缘路径（源系统 → 字段 → 指标）
输出：
  - 血缘路径图（文字版）
  - 标注哪些源字段近期有过工单或变更记录
  - 无法确认数据质量时，给出"建议核查 X 系统 Y 字段"的操作建议
```

**假说 3：同表指标同向异动**

```
调用：get_peer_report_data(report_code, period)（L3，需数值接口）
  → 查同报表内其他关联指标的同期值
  → 判断是否多个指标同向变化（可能是系统性原因）
输出：
  - 若数值接口不可用：标注"需人工核查同表其他指标"
  - 若可用：列出同向变化的指标列表
```

**假说 4：业务事件**

```
此假说始终标注为 ❌（超出 AI 分析范围）
固定输出：
  "业务事件（如大额交易、新产品上线、客户结构变化）需结合业务系统数据人工判断，
   本 AI 无法访问业务源系统，建议与业务条线确认本期是否有异常业务发生。"
```

### 4.3 假说优先级排序逻辑

```
优先级 = 证据强度 × 可排查性

口径变化（假说 1）> 血缘质量（假说 2）> 同表对比（假说 3）> 业务事件（假说 4）

原因：
  - 假说 1/2 的数据我们系统内有，证据可量化
  - 假说 3 依赖外部接口，置信度不确定
  - 假说 4 系统内完全没有数据，只能提示
```

### 4.4 排查结果生成工单

异常排查完成后，业务可一键生成工单：
- 工单类型：`MANUAL_REVIEW`（人工复核）
- 工单内容：自动填入假说清单 + 建议排查步骤 + 责任人（根据血缘上游的系统归属推断）
- 状态：`OPEN`，进入正常工单队列

---

## 5. 工具清单

| 工具名 | 输入 | 数据来源 | 可用性 |
|---|---|---|---|
| `search_instruction_rag` | item_code / 关键词 | RegReportingInstruction + embedding | 需新增 embedding |
| `get_item_lineage` | item_code | reporting_item_lineage（痛点 1 铺底后可用）| 依赖 Step A 完成 |
| `get_regulatory_changes` | item_code | RegReportingChangeCandidate + TicketDraft | ✅ 现有数据 |
| `get_related_tickets` | item_code | TicketDraft.related_impact_codes | ✅ 现有数据 |
| `web_search_regulatory_qa` | 指标名 + 机构关键词 | 网络检索（Bing / Tavily） | 需接入 search API |
| `get_peer_report_data` | report_code + period | 数值接口（待定） | ⚠️ 依赖数据接入 |
| `create_ticket_from_analysis` | 假说清单 + item_code | TicketDraft 写入 | ✅ 现有写入逻辑 |

---

## 6. 与现有系统的衔接

### 6.1 复用资产

```
填报说明文档库（RegDocument + RegReportingInstruction）→ RAG 数据源
报送指标目录（RegReportingItem）                       → 指标基本信息
血缘图（ReportingItemLineage）                        → 假说 2 数据源（依赖痛点1 Step A）
监管变更记录（RegReportingChangeCandidate）            → 假说 1 数据源
工单历史（TicketDraft）                               → 历史经验 + 生成工单
```

### 6.2 新增组件

```
embedding 向量表        → 填报说明的语义检索
Agent 编排层            → 意图识别 + 工具调用 + 回答合成
web_search 工具         → 监管官方答疑检索
（可选）数值接口适配层   → L3 同表对比
```

### 6.3 入口位置

建议在前端新增一个常驻的对话入口，不绑定特定任务/工单：
- 侧边栏快捷入口"问指标"
- 也可以在具体工单页内嵌，针对该工单相关指标直接问答
- 排查模式可从指标异常告警处一键触发（传入异常指标和本期/上期值）

---

## 7. 实现规划

### Step E：填报说明 Embedding

在现有 `RegReportingInstruction` 基础上，新增向量列（或独立向量表）：

```
新建 RegInstructionEmbedding(instruction_id, embedding: bytes, model_version)
新建 embedding_indexer.py：对所有 instruction 文本做 embedding，批量写入
```

**影响文件**：`models/db_models.py`（新表）、新建 `services/embedding_indexer.py`

### Step F：工具层实现

新建 `services/indicator_qa_tools.py`，实现所有工具函数：

```python
def search_instruction_rag(item_code: str, query: str, session) -> list[dict]
def get_item_lineage(item_code: str, session) -> dict
def get_regulatory_changes(item_code: str, session) -> list[dict]
def get_related_tickets(item_code: str, session) -> list[dict]
def web_search_regulatory_qa(item_name: str, item_code: str) -> list[dict]
def create_ticket_from_analysis(item_code: str, hypotheses: list[dict], session) -> int
```

**新建文件**：`services/indicator_qa_tools.py`

### Step G：Agent 编排层

新建 `services/indicator_qa_agent.py`：

```python
def run_indicator_qa(
    question: str,
    item_code: str | None,
    anomaly_context: AnomalyContext | None,
    session,
) -> IndicatorQAResponse:
    # 1. 意图识别
    # 2. 按意图选择工具组合
    # 3. 并行调用工具
    # 4. LLM 合成结构化回答
```

**新建文件**：`services/indicator_qa_agent.py`

### Step H：API 端点

```
POST /indicator-qa/ask
  body: {question, item_code?, anomaly_context?}
  → 触发 Agent，流式返回或一次性返回

GET  /indicator-qa/items
  → 返回可查询的指标列表（用于前端下拉选择）
```

**影响文件**：新建 `api/routes_indicator_qa.py`，`main.py` 注册路由

### Step I：前端对话界面

新建 `IndicatorQAView.vue`：
- 左侧：指标选择（下拉 + 搜索）
- 中间：对话区（支持自然语言输入）
- 右侧：当前指标的血缘图快照 + 相关工单列表

---

## 8. 分阶段交付目标

| 阶段 | 步骤 | 交付目标 |
|---|---|---|
| P0 | E | 填报说明 embedding 完成，RAG 检索可用 |
| P1 | F | 所有工具函数可独立调用，单测通过 |
| P2 | G | Agent 完整跑通解释模式（不含排查） |
| P3 | G+H | 排查模式接入，两种模式 API 可用 |
| P4 | I | 前端对话界面上线，血缘图 + 工单联动 |

---

## 9. Demo 效果预期

**解释模式示例**：

> 问：G25 的流动性覆盖率这个指标怎么填？
>
> 答：
> 【官方定义】根据填报说明第 12 条……（RAG 原文）
> 【通俗理解】流动性覆盖率衡量的是银行在压力情景下能撑多少天……
> 【填报要点】① 分子只计算"优质流动性资产"，不含受限资产 ② 分母的净现金流出按照压力情景测算……
> 【监管官方答疑】2024 年 9 月银保监答疑文件中提到……（来源：xxx.gov.cn）

**排查模式示例**：

> 问：G21 期限缺口本期比上期大了 30%，帮我分析
>
> 答：
> 【假说 1 ✅】监管口径近 3 个月内有变更：2026-03-15 生效的填报说明修订将 XX 纳入缺口计算口径（工单 #234）
> 【假说 2 ⚠️】血缘上游：该指标来源于信贷系统 loan_maturity 字段，建议核查该字段本期数据质量
> 【假说 3 —】数值接口不可用，建议人工比对同表 G21.MAIN.LIQUIDITY_GAP_90D 是否同向变化
> 【假说 4 ❌】业务事件超出 AI 分析范围，建议询问业务条线本期是否有大额提前还款或新增负债

---

## 10. 与业务沟通的验收话术

> "以前出了异常你们要自己翻填报说明、问数据团队、核对上期数据，来回折腾。
> 现在直接问系统：'这个指标为什么异常？'——AI 会先查监管口径有没有改、
> 再查数据血缘上游有没有问题，给你一张优先级排好的排查清单。
> 结论还是你来下，但 AI 帮你把 80% 的排查工作提前做了。"
