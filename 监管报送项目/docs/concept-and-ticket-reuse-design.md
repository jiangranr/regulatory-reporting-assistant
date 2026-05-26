# 概念库与工单复用设计（基于代码现状的修订）

> 更新日期：2026-05-26
> 文档定位：在 `rule-card-and-concept-kb-design.md` 既有设计基础上，**基于当前代码实现现状**，补齐"让概念库与工单经验真正可复用"的缺失环节。**不替代既有设计文档**，只补充和修订。
> 适用项目：监管报送项目
> 状态：**已定稿**（2026-05-26 用户确认 5 个决策点，见 §7）

---

## 0. 这篇文档为什么写

用户原话：

> "想和你讨论下我们项目的监管概念库，规则与口径这两个资产，我的本意是希望他们能形成资产沉淀并且复用，比如下次监管发文口径相似，可以更加精准命中。"

`rule-card-and-concept-kb-design.md` 的 §4.5 / §5 / §6.11 已经讲了"概念辐射"和"飞轮"，但**没把"复用"切成可落地的工程动作**。同时，该文档写于 2026-05-21，部分内容代码已实现、部分被简化、部分未实现。**先重新对齐现状，再谈复用怎么做。**

---

## 1. 代码现状盘点（vs 既有设计文档）

### 1.1 已落地（可直接复用作为基底）

| 资产 | 状态 | 代码位置 |
|---|---|---|
| `RegConcept` / `RegConceptAlias` / `RegConceptVersion` / `RegConceptRelation` / `RegConceptReportingItemMap` | ✅ ORM 已建 | `app/models/db_models.py` L493-582 |
| `RegReportingRuleCard` / `RegReportingRuleCardConceptMap` / `RegReportingRuleCardValidation` | ✅ ORM 已建 | `app/models/db_models.py` L417-490 |
| `TicketDraft` 母子单 + severity + role 富字段 | ✅ 已建 | `app/models/db_models.py` L311-335 |
| `AuditLog` 表 | ✅ 已建 | `app/models/db_models.py` L338-346 |
| `GET/PATCH /api/concepts` + `POST /api/concepts/match` | ✅ 已实现 | `app/api/routes_concepts.py` |
| `GET/PATCH /api/rule-cards` | ✅ 已实现 | `app/api/routes_rule_cards.py` |
| 概念匹配：长别名优先 substring + 反查 reporting_item_codes | ✅ 已实现 | `routes_concepts.py::match_concepts` |
| 35+ 概念/卡片 seed（G31 + G24/G21 跨表） | ✅ 已灌入 | `app/services/concept_seed.py` |
| 简化版 P1 抽取（同步 L1 抽取，无任务表） | ✅ 已实现 | `app/services/extract_service.py` + `routes_extraction.py` |
| **工单底部已自动挂规则卡片** | ✅ 已实现 | `reporting_ticket_generator.py::_rule_cards_block` + `routes_tasks.py::_build_rule_cards_lookup` |
| Impact items 按 reporting_item_code 合并去重 | ✅ 已实现 | `reporting_impact_analyzer.py` L39-43 |
| 前端 LibraryView / ConceptsView 已对接 API | ✅ 已实现 | `frontend/src/views/Library*.vue` |

### 1.2 设计承诺但代码未实现（影响复用的关键空白）

| 缺口 | 设计文档章节 | 代码现状 | 对复用的影响 |
|---|---|---|---|
| `reg_extraction_job` 任务表 | §6.7 | ❌ 跳过（extract_service docstring 明说） | 弱：复用本身不依赖 |
| L2 结构卡抽取 | §3.3 / §6.3 阶段 5 | ❌ | **中**：L2 是"语义层复用"的载体，没它只能字面匹配 |
| embedding 语义召回 | §11 不在范围 / P2 | ❌ | **强**：新发文换说法（"拆放同业" vs "同业融入"）无法召回 |
| 概念版本演化主动追踪 | §4.4 | ❌（仅有 ORM） | 中：跨次发文的口径漂移看不见 |
| 三级处置策略 | §6.6 | ❌ | 弱 |
| 复用效果可观测指标 | （文档完全没设计） | ❌ | **强**：飞轮转没转看不见，等于没转 |
| 跨监管体系概念绑定 | （文档完全没设计） | ❌ | **强**：1104→一表通时所有经验断裂 |
| 工单底部挂"历史相似案例" | （文档完全没设计） | ❌ | **强**：业务方最直接的复用入口缺失 |

### 1.3 关键判断

**复用的工程瓶颈不在"建新表"，在"把现有数据通过新查询通路盘活"**。
基础设施 80% 已就绪。

---

## 2. 复用的 5 层金字塔（重新切片）

复用本身不是单一动作，是 5 层从浅到深的能力栈。**每一层在当前代码里有什么，缺什么：**

```
┌────────────────────────────────────────────────────────────┐
│ L5  决策/经验复用                                          │
│ 「上次类似发文怎么处理的？业务方采纳/退回/调整了什么？」  │ ← 完全空白（最高 ROI）
├────────────────────────────────────────────────────────────┤
│ L4  规则卡片复用                                          │
│ 命中概念 → 工单底部挂卡片                                  │ ← ✅ 已实现
├────────────────────────────────────────────────────────────┤
│ L3  语义相似度复用                                        │
│ "拆放同业"也能命中"同业融入"                               │ ← 文档说 P2，实际未做
├────────────────────────────────────────────────────────────┤
│ L2  概念辐射复用                                          │
│ 1 概念 → N 张报表（concept_reporting_item_map）            │ ← ✅ 已实现
├────────────────────────────────────────────────────────────┤
│ L1  字面别名复用                                          │
│ alias substring 命中（长串优先）                           │ ← ✅ 已实现
└────────────────────────────────────────────────────────────┘
```

**结论**：L1、L2、L4 已就绪；L3 半通；**L5 完全空白**。

用户问的"下次精准命中"，**精准 = L3**（同义改写也能命中），**复用经验 = L5**（不只命中概念，还要看上次怎么处理的）。这两层才是真正的红利所在。

---

## 3. 六个补丁（不破坏存量，按 ROI 排序）

每个补丁列：**改什么代码 / 新增什么 / 是否需要 DB migration / 向后兼容性**。

### 补丁 A：把 `/api/concepts/match` 升级为多路召回

**问题**：现在只有 alias substring 一路。新发文里"拆放同业"如果没人提前加进 `CON_INTERBANK_BORROWING` 的 alias，永远召不回。

**方案**：在 `routes_concepts.py::match_concepts` 内部加 2 路召回，输出结构 `ConceptMatchHit` 不变：

```
input text
  ├─ 路 1：alias substring（已有，保留）
  ├─ 路 2（新）：canonical_name + short_definition 关键字 ngram 召回
  │            从 text 中提取 2-4 字 ngram → 与概念名称/定义做包含匹配
  ├─ 路 3（新）：concept_alias.evidence_text 命中
  │            alias 表里 evidence_text 字段已存在（设计文档 §4.2），
  │            是"别名出现的原文"，本身是高质量训练数据，做关键词匹配
  └─ （可选）路 4：embedding 召回，bge-small-zh 本地跑（依赖：sentence-transformers）
  → 三路合并去重 → 按 confidence_score 排序 → top_k 截断
```

**改动**：
- 文件：`app/services/concept_matcher.py`（新增，把 match 逻辑从 routes 抽出来）
- 文件：`app/api/routes_concepts.py::match_concepts`（改成调 concept_matcher）
- DB migration：无
- 向后兼容：**完全**。`ConceptMatchHit` schema 不变；hits 数量可能增加（top_k 控制）

**工作量**：1.5 天（多路召回，不含 embedding）；+1.5 天上 embedding。

**风险**：召回 ↑ 但精度可能 ↓。**补丁 E 的 eval target 是必备护身符**。

---

### 补丁 B：决策档案 service（核心飞轮，**不新建独立大表**）

**问题**：用户最关心的"上次类似发文怎么处理的"完全没数据通路。

**关键洞察**：现有 `TicketDraft` + `RegReportingImpactItem` + `RegReportingRuleCardValidation` + `AuditLog` 已经记录了**全部决策证据**，只是没人把它们 join 起来反向查询。**不需要新建 `reg_decision_case` 表，建一个虚拟视图层 service 即可**。

**方案**：

```
新增 app/services/decision_archive_service.py
  函数 search_similar_decisions(
    concept_codes: list[str],
    object_codes: list[str] = None,
    top_k: int = 5,
  ) -> list[DecisionCase]:

  逻辑：
  1. 通过 RegConceptReportingItemMap 反查：concept_codes → reporting_item_codes
  2. 反查 RegReportingImpactItem.reporting_item_code IN (...) → task_ids
  3. 拉对应 TicketDraft（按 task_id），过滤 status='CLOSED' 或带业务签字
  4. 关联 RegReportingRuleCardValidation：拿"AI 复核意见 + human_override"
  5. 关联 AuditLog（target_type='ticket', action IN ['ACCEPTED','MODIFIED','REJECTED']）
  6. 计算 reuse_rank：
       - 概念命中数（越多越相关）
       - 时间衰减（半年内 +10%）
       - 该 task 当时的 severity_level（L3/L4 优先）
  7. 返回前 top_k，每条含：
       { ticket_id, ticket_title, task_title, decided_at,
         hit_concept_codes, decision_type, decision_rationale,
         field_adjustments(从 audit_logs.detail 解析), reused_count }
```

**为什么不建 `reg_decision_case` 独立表**：
- 既有写入路径（工单关闭、AuditLog 写入）已经在记录所有需要的数据
- 新建独立表 = 要新增写入触发 + 双写一致性问题
- 视图层 service 的成本是"每次查询 SQL 多 join 几张表"，但查询频率低（每次工单生成才查一次）

**改动**：
- 新增：`app/services/decision_archive_service.py`
- 新增：`app/api/routes_decision_archive.py`（GET `/api/decision-archive/search`）
- DB migration：**无**
- 向后兼容：**完全**

**可选小新增（如果补丁 C 落地）**：为更高质量的"决策摘要"，新增 `reg_ticket_decision_snapshot` 表（**单独一张，不动既有任何表**）：

```sql
CREATE TABLE reg_ticket_decision_snapshot (
  id                BIGINT PK,
  ticket_id         BIGINT NOT NULL,        -- FK ticket_drafts
  task_id           BIGINT NOT NULL,
  closed_at         DATETIME,
  decision_type     ENUM('ACCEPT_AS_IS','MODIFIED','REJECTED','ESCALATED'),
  decision_rationale TEXT,
  field_adjustments JSON,                   -- 业务方实际调整的字段
  hit_concept_codes JSON,                   -- 关闭时挂的概念
  hit_rule_card_codes JSON,
  reused_count      INT DEFAULT 0,          -- 后续被引用次数
  INDEX idx_concepts (((cast(hit_concept_codes as char(200))))),
  INDEX idx_task (task_id)
);
```

工单关闭时由专门的 hook 写入。比从 audit_logs 现拼更稳定、更可索引。

**工作量**：2 天（service + API + 工单关闭 hook + 可选快照表）

---

### 补丁 C：工单 Markdown 加 "历史相似决策" 节

**问题**：业务方在工单页看不到历史经验，每次都从零判断。

**方案**：在 `reporting_ticket_generator.py::_render_child_markdown` 已有的 `cards_block` 之后追加 `historical_cases_block`：

```python
# reporting_ticket_generator.py 新增
def _historical_cases_block(
    impacts: list[ReportingImpactDraft],
    historical_cases_by_key: dict[str, list[dict]],
) -> str:
    if not historical_cases_by_key:
        return ""
    # 渲染为 Markdown:
    """
    ## 📚 历史相似决策（飞轮引用）

    ### 2025-04-12 监管发文 "拆放同业纳入同业融入" · 引用 3 次
    > 业务方采纳了 AI 草稿，并把 unsettled_exposure_amt 字段从 INT 改成 DECIMAL(20,2)。
    > 命中概念：CON_INTERBANK_BORROWING、CON_FINANCIAL_INSTITUTION
    > [查看原工单 →](/tickets/123)

    ### 2025-09-08 ...
    """
```

调用链：
```
routes_tasks.py::generate_task_ticket
  → _build_rule_cards_lookup(impacts, session)              # 已有
  → _build_historical_cases_lookup(impacts, session)        # 新增，调 decision_archive_service
  → build_ticket_plan(..., rule_cards_by_key=..., historical_cases_by_key=...)
```

**改动**：
- `reporting_ticket_generator.py`：`build_ticket_plan`、`_build_child_plan`、`_render_child_markdown` 加 `historical_cases_by_key` 参数（默认 None，向后兼容）
- `routes_tasks.py`：新增 `_build_historical_cases_lookup`
- DB migration：无
- 向后兼容：**完全**（参数默认 None，老调用方零改动）

**工作量**：1 天

---

### 补丁 D：跨监管体系概念绑定（一表通进来时不要从零建库）

**问题**：1104 的 `CON_INTERBANK_BORROWING` ≈ 一表通的某个概念 ≈ EAST 的某个概念。现在三个体系各建一份，复用断在跨体系维度。

**方案 1（推荐，最小侵入）**：给 `RegConcept` 加一个字段。

```sql
ALTER TABLE reg_concept ADD COLUMN cross_system_group_code VARCHAR(64) NULL,
  ADD INDEX idx_cross_group (cross_system_group_code);
```

- 同一业务概念在 1104/EAST/一表通 用同一 `cross_system_group_code`（如 `GRP_INTERBANK_BORROWING`）
- 不强制：值为 NULL 表示纯单体系概念
- `/match` 命中后做二次扩张：拉同 group_code 的其他概念，把它们关联的卡片也带出

**方案 2（更结构化但复杂）**：新建 `reg_concept_cross_system_link` 表（如设计文档 §第三节补丁 ③ 描述）。

**推荐方案 1**：字段足够；表只在概念数 >500 且跨体系关系复杂时才考虑升级。

**改动**：
- `db_models.py::RegConcept`：加 `cross_system_group_code: str | None`
- `routes_concepts.py::match_concepts`：命中后做 group 扩张
- DB migration：**有**（加列），向后兼容（nullable + 默认空）
- 向后兼容：**是**

**工作量**：0.5 天（schema + 扩展逻辑） + 1-2 天人工标定初始 group_code

---

### 补丁 E：eval framework 锁住复用质量

**问题**：补丁 A 把单路升 3 路、补丁 B/C 加历史召回，**最大风险是召回↑、精度↓**。没法定量回答"这次是变好还是变差"。

**方案**：在 2026-05-26 已有的 eval framework 上加新的 target。

```python
# tests/eval/targets.py 新增

@register_target("concept_match")
def _run_concept_match(inputs: dict) -> list[dict]:
    """走 /api/concepts/match 的全流程（含多路召回）。"""
    matcher = ConceptMatcher(session=...)
    hits = matcher.match(text=inputs["text"], scope=inputs.get("scope", "1104"))
    return [
        {
            "concept_code": h.concept_code,
            "canonical_name": h.canonical_name,
            "matched_alias": h.matched_alias,
            "indicator_hint": h.canonical_name,
            "change_type": "MATCH",  # 让既有断言 spec 复用
            ...
        }
        for h in hits
    ]
```

加 case：

```jsonc
// tests/eval/cases/concept_match_interbank_synonym.json
{
  "id": "concept_match_interbank_synonym",
  "description": "拆放同业 / 同业融入 / 金融机构间融入款项 三种说法都应命中 CON_INTERBANK_BORROWING",
  "category": "rule_based",
  "target": "concept_match",
  "inputs": {
    "text": "本通知要求将拆放同业纳入同业融入统计范围，金融机构间融入款项一并报送"
  },
  "expectations": [
    { "kind": "must_contain", "spec": { "keyword": "CON_INTERBANK_BORROWING" } },
    { "kind": "signal_count", "spec": { "min": 1, "max": 8 } }
  ]
}
```

**改动**：
- `tests/eval/targets.py`：注册 `concept_match` target
- `tests/eval/cases/`：新增 3-5 个核心概念回归 case
- DB migration：无
- 向后兼容：完全（新 target 不影响既有 g31 case）

**工作量**：0.5 天

**这条必做**。补丁 A 不带 eval 就上线 = 赌博。

---

### 补丁 F：复用效果可观测看板（让飞轮可见）

**问题**：设计了一堆复用机制，但**没有任何"复用真的发生了"的量化证据**。

**方案**：新增 `reuse_metrics_service.py`，把现有数据聚合为指标：

| 指标 | 数据来源 | SQL 大致 |
|---|---|---|
| 本月概念召回率 | concept_match 日志 + impact_items | 命中既有概念的 signal 数 / 总 signal 数 |
| 新增概念产出率 | RegConcept.status='DRAFT' + created_at | 本月 DRAFT 数 / ACTIVE 总数 |
| 平均命中概念数/发文 | impact_items 关联的概念 join | avg(concept_codes_per_task) |
| 决策案例平均复用次数 | reg_ticket_decision_snapshot.reused_count（补丁 B） | avg(reused_count) |
| **Alias 空跑次数 Top10** | concept_match 日志（补丁 G） | 哪些关键词搜了但没命中 → 提示新增 alias |
| **长期未命中概念 Top10** | RegConcept + last_matched_at（补丁 G） | 90 天未命中的 → 提示是否过期 |

**前提**：补丁 G "match 调用埋点"（很小，单独提）。

**改动**：
- 新增：`app/services/reuse_metrics_service.py`
- 新增：`/api/reuse-metrics`（GET 单接口返回 JSON）
- 新增：前端 LibraryView 顶部加"复用看板"卡片
- DB migration：无（如果不加补丁 G）
- 向后兼容：完全

**工作量**：1.5 天（service + API + 前端）

---

### 补丁 G：concept_match 调用埋点（飞轮燃料）

**问题**：复用看板需要"哪些关键词召不回"的数据。

**方案**：新增小表，在 `match_concepts` API 内异步写入：

```sql
CREATE TABLE reg_concept_match_log (
  id                  BIGINT PK,
  request_text_hash   VARCHAR(64),         -- 文本片段去重（前 200 字 sha256）
  text_snippet        TEXT,                -- 前 500 字
  scope               VARCHAR(64),         -- 1104 / EAST / 一表通
  hit_concept_codes   JSON,
  hit_count           INT,
  task_id             BIGINT NULL,         -- 如果是工单流程触发的 match
  matched_at          DATETIME,
  INDEX idx_matched_at (matched_at)
);
```

每次 `/api/concepts/match` 调用写一条。

同时给 `RegConcept` 加：
```sql
ALTER TABLE reg_concept
  ADD COLUMN last_matched_at DATETIME NULL,
  ADD COLUMN total_matched_count BIGINT DEFAULT 0;
```

`match_concepts` 命中时更新这两个字段（异步）。

**改动**：
- 新增表 `reg_concept_match_log`
- `RegConcept` 加 2 个字段
- `routes_concepts.py::match_concepts` 末尾加埋点写入
- DB migration：是（向后兼容：字段都 nullable + 默认值）
- 向后兼容：是

**工作量**：0.5 天

---

## 4. 复用闭环全图（修订版）

```
┌──────────────────────────────────────────────────────────────────┐
│                     【发文进入 5 步流程】                          │
│                                                                    │
│  上传发文                                                         │
│    ↓                                                              │
│  文档画像（已实现）                                                │
│    ↓                                                              │
│  影响分析                                                          │
│    │                                                              │
│    ├─► 调 /api/concepts/match                                     │
│    │     ┌─ 路 1 alias substring（已有）                          │
│    │     ├─ 路 2 ngram + 定义关键词（补丁 A）                     │
│    │     ├─ 路 3 alias.evidence_text（补丁 A）                    │
│    │     ├─ 路 4 embedding（补丁 A 可选）                         │
│    │     └─ group 扩张（补丁 D 跨监管体系）                       │
│    │                                                              │
│    ├─► 命中的概念 → reporting_item_codes（已实现）                │
│    │                                                              │
│    └─► 命中的概念 → search_similar_decisions（补丁 B 新增）       │
│         反查 ticket_drafts + impact_items + audit_logs            │
│         + reg_ticket_decision_snapshot（补丁 B 可选）              │
│    ↓                                                              │
│  工单生成（reporting_ticket_generator.py）                         │
│    ├─► _rule_cards_block（已实现）                                │
│    └─► _historical_cases_block（补丁 C 新增）                     │
│    ↓                                                              │
│  工单审批                                                          │
│    ↓                                                              │
│  工单关闭                                                          │
│    │                                                              │
│    ├─► AuditLog 写入（已有）                                      │
│    ├─► reg_ticket_decision_snapshot 写入（补丁 B 可选）           │
│    └─► 更新 RegConcept.last_matched_at（补丁 G）                  │
│    ↓                                                              │
│  复用看板更新（补丁 F）                                            │
└──────────────────────────────────────────────────────────────────┘

并行：
  · eval framework 每天跑（补丁 E）         → 防止召回质量退化
  · reuse_metrics 每周报告                  → 飞轮可见
```

每跑一次完整流程，**右下角的"决策档案"就厚一分，下次相同发文的工单从 0 起点变成"上次怎么处理"起点**。这才是真飞轮。

---

## 5. 30 天分阶段落地计划

按 ROI × 工作量 排，每周一个主补丁：

| 周 | 主补丁 | 配套 | 产出 |
|---|---|---|---|
| **W1** | **补丁 A**：多路 /match（不含 embedding） | 补丁 E（concept_match eval 必带） | /match 召回质量量化可比 |
| **W2** | **补丁 B**：决策档案 service + 可选快照表 | 工单关闭 hook | 第一次有"历史决策"可查 |
| **W3** | **补丁 C**：工单 Markdown 加历史决策节 + **补丁 G**：埋点 | — | 业务方第一次在工单上看到历史经验 |
| **W4** | **补丁 F**：复用看板 + **补丁 D**：跨体系绑定（schema + 标定首批 5-10 个 group） | LibraryView 加看板组件 | 飞轮可见 + 一表通进来时不从零建库 |

P2（30+ 天）：补丁 A 上 embedding（要加 sentence-transformers 依赖，单独评估）。

---

## 6. 与既有设计文档的关系

本文档**修订并补充**，**不替代**：

| 既有文档章节 | 本文档对应 | 关系 |
|---|---|---|
| `rule-card-and-concept-kb-design.md` §3 卡片三级 | 维持 L1 落地、L2 暂缓 | 不变 |
| §4 概念库数据模型 | 加字段 `cross_system_group_code`、`last_matched_at`、`total_matched_count` | 增量 |
| §4.5 概念辐射 | 多路召回扩张（补丁 A） | 增强 |
| §5 联动飞轮 | 加 L5 决策复用层（补丁 B/C） | 补全 |
| §6 抽取流水线 | 维持现状简化版 | 不变 |
| §11 P2 才做 embedding | 改为 W4+ 可选 | 调整 |
| `regulatory-workflow-implementation.md` 5 步流程 | 工单生成节加历史决策（补丁 C） | 增量 |

---

## 7. 5 个决策点（2026-05-26 已确认）

| # | 决策点 | 结论 | 理由 |
|---|---|---|---|
| 1 | **补丁 B 是否新建 `reg_ticket_decision_snapshot` 表** | **先不建**。W2 纯视图层 service 跑通；若 W3 上线后发现查询性能不足 / 决策摘要不稳定，再补建快照表。 | 现有 `TicketDraft + ImpactItem + AuditLog + RuleCardValidation` 已记录全部决策证据，避免双写一致性 |
| 2 | **补丁 D 用字段还是关系表** | **用字段**（`RegConcept.cross_system_group_code`） | 最小侵入；概念数 >500 且跨体系关系复杂时再升级为关系表 |
| 3 | **补丁 A 是否在 W1 就上 embedding** | **不上**。先观察 3 路召回是否够；W4+ 再评估 | 加 `sentence-transformers` 依赖、引入向量列、增加部署复杂度；先用零依赖方案 |
| 4 | **历史决策"采纳/退回"信号从哪取** | **`audit_logs` 约定写入规范，见下方 §7.1** | 工单关闭 API 强制写一条结构化 AuditLog，复用看板和决策档案 service 都依赖这条记录 |
| 5 | **复用看板 6 个指标是否齐全** | **够用，W4 先实现这 6 个**，后续按真实使用场景再加 | 避免过度设计；先把"能看见飞轮转没转"做出来 |

### 7.1 `audit_logs` 写入约定（决策 4 的落地细节）

工单关闭路径（`PATCH /api/tickets/{id}` status=CLOSED 时）**必须**写入一条 AuditLog：

```python
AuditLog(
    action="TICKET_CLOSED",        # 固定字符串，索引可用
    target_type="ticket_draft",
    target_id=ticket_draft.id,
    detail=json.dumps({
        "task_id": ticket.task_id,
        "decision_type": "ACCEPT_AS_IS" | "MODIFIED" | "REJECTED" | "ESCALATED",
        "decision_rationale": "<业务方填写的处理结论文本>",
        "field_adjustments": [                                # 业务方实际改动的字段
            {"item_code": "G31.PART_I.X", "field": "...", "from": "INT", "to": "DECIMAL(20,2)"}
        ],
        "hit_concept_codes": ["CON_INTERBANK_BORROWING", ...],   # 工单生成时挂的概念
        "hit_rule_card_codes": ["RC_G31_BOND_SCOPE_001", ...],
        "closed_by": "<reviewer>"
    }, ensure_ascii=False),
)
```

其他可选 `action`（一并约定，避免后续散落）：

| action | 何时写 | detail 关键字段 |
|---|---|---|
| `TICKET_CREATED` | 工单生成时 | `task_id`, `hit_concept_codes`, `hit_rule_card_codes` |
| `TICKET_REVIEWED` | 业务方在 LineageView 点采纳/退回时 | `review_action`, `reviewer`, `comment` |
| `TICKET_CLOSED` | 工单流转到 CLOSED | 见上 |
| `CONCEPT_MATCHED` | （由补丁 G 的 match_log 替代，不再用 AuditLog） | — |
| `RULE_CARD_REVIEWED` | LibraryView 审核卡片时 | `card_id`, `action`, `reviewer` |

**复用查询的关键 SQL**（决策档案 service 用）：

```sql
SELECT detail FROM audit_logs
WHERE action='TICKET_CLOSED'
  AND JSON_CONTAINS(JSON_EXTRACT(detail, '$.hit_concept_codes'),
                    JSON_QUOTE('CON_INTERBANK_BORROWING'))
ORDER BY created_at DESC
LIMIT 10;
```

（SQLite 用 LIKE `'%CON_INTERBANK_BORROWING%'` 兜底；上 MySQL 后切 JSON_CONTAINS）

---

## 8. 不在本文档范围

明确不做的事情：

- 不重新设计抽取流水线（维持现状简化版）
- 不动 L2/L3 卡片抽取（按既有文档 P2 节奏）
- 不重做工单母子单结构（基础设施已就绪）
- 不动前端 5 步流程页面结构（仅在 LibraryView 加看板）
- 不接入真实权限模型（与既有文档一致）
