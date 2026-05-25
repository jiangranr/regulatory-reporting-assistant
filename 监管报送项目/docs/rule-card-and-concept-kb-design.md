# 报送规则卡片与监管概念知识库设计

> 更新日期:2026-05-21
> 适用项目:监管报送变更影响分析与工单助手
> 文档定位:在现有 22 张表的报送项-血缘-工单体系上,新增"规则卡片"与"概念知识库"两层资产,把填报说明里的口径文本和监管反复修订的术语沉淀为可消费的结构化资产。
> 一期落脚点:G31(投资业务情况表第 I 部分:底层资产投资情况)。

---

## 1. 背景与目标

### 1.1 现状缺口

当前体系的最后两块短板:

1. **填报说明只是 PDF 原文**——`reporting_instructions` 表里存的是整段说明文字,不能驱动 LLM 校验,也不能挂在工单底部当参考。每次工单解决,开发要回头翻 PDF 找口径。
2. **口径术语没有沉淀**——监管全年若干次小改动里,"同业融入"、"底层资产"、"债券投资余额"这些概念的范围在变。每次新发文都要从零理解,历史经验沉淀在 PPT 和工单关闭说明里,没法被下一次 AI 抽取复用。

### 1.2 目标

新增两类资产,把上述短板补上:

| 资产 | 角色 | 核心问题 |
|---|---|---|
| 报送规则卡片 | 把填报说明的"段"切成"条",每条带级别和证据 | 工单能引用,LLM 能校验,人工能复核 |
| 监管概念知识库 | 跨表、跨版本的口径骨架(轻量本体) | 概念演化可追踪,新发文命中已知概念时可放大召回 |

两者强耦合:**每张规则卡片必须挂一个或多个 concept_id**,这样概念变化能自动辐射到所有相关卡片,卡片变化能自动驱动概念版本演化。

### 1.3 命名约定

经讨论确定:

- **数据模型 / 服务 / 接口 / 代码命名**:通用化,统一为 `reporting_rule_card`、`concept`,不带 G31 前缀。
- **前端展示文案 / 工单参考块标题**:一期可以叫"G31 填报规则卡片",符合演示场景。
- **二期扩展到 G24/G21/EAST 时**:模型不动,只改展示文案。

### 1.4 现有相关代码资产

- `backend/app/services/rule_extractor.py`(35 行,占位) — 本设计的主要承载体
- `backend/app/services/instruction_parser.py`(345 行) — 用于切段,本设计直接调用
- `backend/app/services/instruction_change_analyzer.py`(227 行) — 用于新旧填报说明 diff,本设计直接调用
- 数据库 22 张表中已预留 `reg_reporting_rules` — 与本设计的"规则卡片"是同一个概念,**本设计扩展该表,不新建同义实体**
- `frontend/src/types/api.ts::RuleCard` + `frontend/src/views/LibraryView.vue` — **已存在前端占位骨架**,字段是旧"业务对象影响"语义(risk_level/impacted_objects/applicable_business),本设计**重构该类型为 L1/L2/L3 语义**,LibraryView 同步重构,不新建组件

### 1.5 待清理的旧主线代码(经讨论确认删除)

`main.py` 已不注册 `routes_rule_library`,前端 4 个 `/api/rule-library/*` 方法亦无任何 View 调用。可安全清理的清单:

| 文件/符号 | 处置 |
|---|---|
| `backend/app/api/routes_rule_library.py` | 删除 |
| `backend/app/services/rule_library.py` | 删除 |
| `frontend/src/api/client.ts` 中 `seedRuleLibrary` / `listBusinessObjects` / `listMetadataFields` / `listFieldMappings` 四个方法 | 删除 |
| `frontend/src/types/api.ts` 中 `RuleLibrarySeed` 接口 | 删除 |
| `frontend/src/data/mock.ts` 中 `sampleRuleLibrarySeed` | 删除 |
| `frontend/src/api/client.test.ts` 中针对上述 4 接口的测试用例 | 删除对应 it 块 |
| `frontend/src/types/api.ts::RuleCard` 中 `risk_level` / `impacted_objects` / `applicable_business` 字段 | **重构而非删除**(替换为新字段) |

---

## 2. 数据范围与边界(必读)

### 2.1 库里实际有什么

| 数据 | G31 | G24 | G21 | G25 | G27 |
|---|:---:|:---:|:---:|:---:|:---:|
| seed 里的结构骨架 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 真实表样 .xls | ✅(8 份) | ❌ | ❌ | ❌ | ❌ |
| 真实填报说明 .doc | ✅(9 份) | ❌ | ❌ | ❌ | ❌ |
| 真实修订对照表 .xlsx | ✅(多份) | ❌ | ❌ | ❌ | ❌ |

### 2.2 对一期设计的直接影响

- **规则卡片**:一期**只能从 G31 抽真卡片**,从填报说明 .doc 走 L1 → L2 抽取流水线。G24/G21/G25/G27 这一期不抽真卡片。
- **概念库**:目标 20 个概念,**主体来自 G31**(预计 12-14 个),为了演示 demo 的"跨表概念辐射"画面,**手工补 6-8 个 G24/G21 概念**(共享同业相关术语),由我们直接灌种子。在文档里明确标注这部分是手工种子,不是从材料抽出来的。
- **demo 叙事主轴**:G31 真实材料 → 真实抽规则 → 真实演示飞轮;G24 辐射作为"概念库覆盖面"的补充画面。

---

## 3. 报送规则卡片设计

### 3.1 三级卡片模型

填报说明里的内容浓度差异很大,三级分层:

| 级别 | 形态 | 内容示例 | 校验能力 |
|---|---|---|---|
| **L1 文本卡** | 自然语言原文摘录 + 出处定位 | "本表统计范围不含表内自营投资中的股票投资,资产管理产品按穿透原则填报" | 仅供阅读,挂工单底部 |
| **L2 结构卡** | (主体, 谓词, 客体, 限定) 四元组 | (债券投资余额, 包含, 应收利息, 计提日 ≤ 报告日) | LLM judge 输入 |
| **L3 可执行卡** | DSL 或 SQL 表达式 | `SUM(book_balance) WHERE asset_type IN ('债券','ABS') AND NOT(category='股票')` | 直接跑 SQL 比对工单产物 |

**抽取节奏**:L1 力争 G31 填报说明 100% 覆盖,L2 抽 30% 高频条款(估计 8-15 条)。**L3 一期不实现**(经讨论确认),数据模型保留字段,二期评估是否启动。

**对象级 vs 指标级 卡片**:`reporting_item_code` 字段允许 NULL。NULL 表示"对象级卡片",规则适用于整张报表(如 G31 整表的统计范围说明、穿透原则等);非空表示卡片绑定到具体指标(如 G31.PART_I.BOND_INVESTMENT_BALANCE 的应收利息口径)。两种粒度并存。

### 3.2 数据模型

主表 `reg_reporting_rule_card`:

```sql
CREATE TABLE reg_reporting_rule_card (
  id                       BIGINT PRIMARY KEY AUTO_INCREMENT,
  card_code                VARCHAR(64) NOT NULL UNIQUE,         -- 业务主键,如 RC_G31_BOND_SCOPE_001
  reporting_object_code    VARCHAR(32),                          -- G31 等,NULL 表示跨表卡片
  reporting_item_code      VARCHAR(64),                          -- 具体指标,NULL 表示对象级
  card_level               ENUM('L1','L2','L3') NOT NULL,
  card_title               VARCHAR(200) NOT NULL,                -- 短标题,如"债券投资余额统计口径"
  card_text                TEXT NOT NULL,                        -- L1 原文摘录,L2/L3 也保留人话版本
  card_subject             VARCHAR(200),                         -- L2 主体
  card_predicate           ENUM('INCLUDES','EXCLUDES','EQUALS','DEPENDS_ON','APPLIES_WHEN','CONSTRAINS'),
  card_object              VARCHAR(500),                         -- L2 客体
  card_qualifier           VARCHAR(500),                         -- L2 限定
  card_expression          TEXT,                                 -- L3 DSL/SQL
  card_expression_lang     ENUM('SQL','DSL'),                    -- L3 表达式语言
  source_document_id       BIGINT,                               -- FK reg_documents
  source_location          VARCHAR(200),                         -- 页码/段落锚点
  evidence_text            TEXT,                                 -- 原文滑窗,防幻觉锚点
  evidence_verified        BOOLEAN DEFAULT FALSE,                -- 人工核对过原文
  effective_from_version   VARCHAR(32),                          -- 制度版本号,关联 reg_reporting_versions
  effective_to_version     VARCHAR(32),                          -- NULL 表示当前生效
  confidence_level         ENUM('HIGH','MEDIUM','LOW') DEFAULT 'MEDIUM',
  review_status            ENUM('PENDING','CONFIRMED','REJECTED','DEPRECATED') DEFAULT 'PENDING',
  status                   ENUM('ACTIVE','DRAFT','ARCHIVED') DEFAULT 'DRAFT',
  created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  created_by               VARCHAR(64),
  updated_by               VARCHAR(64),
  INDEX idx_object_item (reporting_object_code, reporting_item_code),
  INDEX idx_level_status (card_level, status, review_status)
);
```

关联表 `reg_reporting_rule_card_concept_map`(卡片 ↔ 概念,多对多):

```sql
CREATE TABLE reg_reporting_rule_card_concept_map (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  card_id      BIGINT NOT NULL,
  concept_id   BIGINT NOT NULL,
  role         ENUM('SUBJECT','OBJECT','QUALIFIER','RELATED') NOT NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_card_concept_role (card_id, concept_id, role),
  INDEX idx_concept (concept_id)
);
```

校验记录表 `reg_reporting_rule_card_validation`(每次工单提交跑校验留痕,一期不强阻断,只留痕):

```sql
CREATE TABLE reg_reporting_rule_card_validation (
  id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
  card_id             BIGINT NOT NULL,
  ticket_draft_id     BIGINT NOT NULL,                            -- FK ticket_drafts
  validation_result   ENUM('PASS','SUSPECTED_VIOLATION','UNCLEAR','NOT_APPLICABLE') NOT NULL,
  validation_reason   TEXT,                                       -- LLM/规则引擎给出的判断理由
  validator_type      ENUM('LLM_JUDGE','SQL_EXEC','MANUAL') NOT NULL,
  evidence_snippet    TEXT,                                       -- 从工单产物里摘录的依据片段
  human_override      ENUM('ACCEPT','REJECT','UNDECIDED') DEFAULT 'UNDECIDED',
  human_comment       TEXT,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_ticket (ticket_draft_id),
  INDEX idx_card (card_id)
);
```

### 3.3 抽取流水线

```
G31 填报说明 .doc
  → instruction_parser.py 切段(已存在)
  → rule_extractor.py::extract_l1_cards(段落, LLM)
       输出: 候选 L1 卡片(card_text + 出处 + evidence_text)
  → 人工/规则确认 → status=ACTIVE, review_status=CONFIRMED
  → rule_extractor.py::structure_to_l2(L1 卡片, LLM)
       输出: 候选 L2 四元组(subject/predicate/object/qualifier)
  → 人工/规则确认
  → rule_extractor.py::compile_to_l3(L2 卡片 + 字段映射上下文, LLM + 模板)
       输出: 候选 SQL/DSL 表达式
  → 开发人工修订并锁定
```

**关键约束(防幻觉)**:

- L1 阶段:LLM 只能从原文摘录,`evidence_text` 必须能在源文档原文中精确匹配。匹配不上的卡片标 `evidence_verified=false` 并打黄牌。
- L2 阶段:`card_subject` 和 `card_object` 必须命中已有 `reg_concept` 或加入"待新建概念候选",**不允许 LLM 凭空发明主体**。
- L3 阶段:`card_expression` 里出现的字段名必须在 `data_field_catalog` 里存在,LLM 不允许编造字段名。

### 3.4 工单挂载方式

工单生成时(`reporting_ticket_generator.py`),根据工单关联的 `reporting_item_code` 反查命中的规则卡片,在工单 Markdown 底部追加一节:

```markdown
## 参考:G31 填报规则卡片

### 卡片 RC_G31_BOND_SCOPE_001 · 债券投资余额统计口径 [L1]
> 本表统计范围不含表内自营投资中的股票投资,资产管理产品按穿透原则填报。
> 来源:G31 填报说明(251 版)§ 3.2,evidence_verified=true

### 卡片 RC_G31_BOND_SCOPE_002 · 应收利息计入规则 [L2]
> (债券投资余额, 包含, 应收利息, 计提日 ≤ 报告日)
> 关联概念:债券投资余额、应收利息
> 来源:G31 填报说明(251 版)§ 3.5
```

### 3.5 校验机制(提示不阻断)

经讨论确定:**校验结果不阻断工单提交,只作为"AI 复核意见"记录,人工决定是否采纳。**

触发时机:工单状态从 `DRAFT` → `SUBMITTED` 时,后端异步跑校验任务。

校验方式(按工单类型分):

| 工单类型 | 校验逻辑 |
|---|---|
| 口径确认工单 | LLM judge:把 L2 四元组 + 工单"处理结论"文本喂给 LLM,问"结论是否违反卡片?",输出 PASS / SUSPECTED_VIOLATION / UNCLEAR |
| 数据映射工单 | 规则引擎:卡片中提到的客体(应收利息/股票投资等)是否都在工单提交的字段映射 JSON 里被覆盖或显式排除 |
| 报送加工工单 | SQL 静态分析:工单产出的 SQL 是否包含 L3 表达式中的关键过滤项;L3 存在且工单未引用 → SUSPECTED_VIOLATION |
| 其他工单 | 仅 LLM judge,降级到文本对比 |

输出展示位置:工单详情页右侧栏新增"AI 复核意见"模块,显示命中的卡片 + 校验结果 + 理由,带"采纳 / 退回 / 标记不适用"三按钮,写入 `human_override` 字段。

---

## 4. 监管报送概念知识库设计

### 4.1 定位

- 不是字典,是轻量本体:概念有版本演化、关系网络、与报送项的多对多映射。
- 不是图数据库,用 MySQL + 简单的递归 CTE/Python 走图,规模 < 2000 概念时性能足够。
- 不是一次性建全,从工单驱动建,一期 20 个,二期到 50 个,三期目标 200+。

### 4.2 数据模型

主表 `reg_concept`:

```sql
CREATE TABLE reg_concept (
  id                       BIGINT PRIMARY KEY AUTO_INCREMENT,
  concept_code             VARCHAR(64) NOT NULL UNIQUE,         -- 业务主键,如 CON_BOND_INVESTMENT_BAL
  canonical_name           VARCHAR(200) NOT NULL,                -- 规范名,如"债券投资余额"
  short_definition         VARCHAR(500) NOT NULL,                -- 一句话定义
  full_definition          TEXT,                                 -- 完整定义
  concept_type             ENUM('METRIC','SCOPE','CLASSIFICATION','CALCULATION','DIMENSION','ENTITY') NOT NULL,
  reporting_system_scope   VARCHAR(64),                          -- 1104 / EAST / CROSS(跨体系)
  current_version_no       INT NOT NULL DEFAULT 1,
  status                   ENUM('ACTIVE','DEPRECATED','DRAFT') DEFAULT 'ACTIVE',
  created_by               VARCHAR(64),
  reviewed_by              VARCHAR(64),
  created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_canonical (canonical_name),
  INDEX idx_type_scope (concept_type, reporting_system_scope)
);
```

> 角色字段 `created_by` / `reviewed_by`:数据库预留,demo 阶段前端 mock 一个"概念管理员"角色写入,二期对接真权限模型。

别名表 `reg_concept_alias`(同义词、监管发文中的不同说法):

```sql
CREATE TABLE reg_concept_alias (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  concept_id         BIGINT NOT NULL,
  alias_text         VARCHAR(200) NOT NULL,
  alias_source       ENUM('REGULATION','INTERNAL','SYNONYM','HISTORICAL') NOT NULL,
  source_document_id BIGINT,
  evidence_text      TEXT,                                       -- 别名出现的原文
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_concept_alias (concept_id, alias_text),
  INDEX idx_alias_text (alias_text)
);
```

版本演化表 `reg_concept_version`(口径变化追踪,**这是飞轮核心**):

```sql
CREATE TABLE reg_concept_version (
  id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
  concept_id          BIGINT NOT NULL,
  version_no          INT NOT NULL,
  definition_text     TEXT NOT NULL,
  change_summary      TEXT,                                       -- 相对上一版的变化描述
  effective_from      DATE NOT NULL,
  effective_to        DATE,                                       -- NULL 表示当前生效
  source_document_id  BIGINT,                                     -- 引起这次变化的发文
  evidence_text       TEXT,                                       -- 原文片段
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_by          VARCHAR(64),
  UNIQUE KEY uk_concept_version (concept_id, version_no),
  INDEX idx_concept_effective (concept_id, effective_from, effective_to)
);
```

关系表 `reg_concept_relation`(轻量三元组,RDF 风格):

```sql
CREATE TABLE reg_concept_relation (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  from_concept_id    BIGINT NOT NULL,
  to_concept_id      BIGINT NOT NULL,
  relation_type      ENUM('INCLUDES','EXCLUDES','SUBSET_OF','DEPENDS_ON','SYNONYM','PREDECESSOR','REPLACES') NOT NULL,
  confidence_level   ENUM('HIGH','MEDIUM','LOW') DEFAULT 'MEDIUM',
  evidence_ref       VARCHAR(500),
  created_by         VARCHAR(64),
  reviewed_by        VARCHAR(64),
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_relation (from_concept_id, to_concept_id, relation_type),
  INDEX idx_to (to_concept_id, relation_type)
);
```

概念到报送项映射 `reg_concept_reporting_item_map`(**变更影响放大器**):

```sql
CREATE TABLE reg_concept_reporting_item_map (
  id                   BIGINT PRIMARY KEY AUTO_INCREMENT,
  concept_id           BIGINT NOT NULL,
  reporting_item_code  VARCHAR(64) NOT NULL,
  role                 ENUM('PRIMARY_METRIC','FILTER','EXCLUSION','DENOMINATOR','DIMENSION','ANNOTATION') NOT NULL,
  confidence_level     ENUM('HIGH','MEDIUM','LOW') DEFAULT 'MEDIUM',
  created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_concept_item_role (concept_id, reporting_item_code, role),
  INDEX idx_item (reporting_item_code)
);
```

### 4.3 一期初始 20 个概念清单(草案,等你确认)

**G31 真材料抽取(目标 12 个)**:

| 概念名 | 类型 | 一句话定义 |
|---|---|---|
| 底层资产 | SCOPE | 投资业务穿透到的最终标的资产 |
| 投资业务 | SCOPE | 银行表内/表外的投资类业务总称 |
| 债券投资余额 | METRIC | G31 中按债券类型分类的投资账面余额 |
| 资产管理产品 | CLASSIFICATION | 公募基金、理财、信托、ABS 等结构化产品的统称 |
| 穿透原则 | CALCULATION | 把结构化产品按底层资产类型还原到对应报送行的口径 |
| 应收利息 | SCOPE | 计提日已发生但尚未实际收到的利息款项 |
| 表内自营投资 | SCOPE | 银行用自有资金、计入表内的投资业务 |
| 股票投资 | CLASSIFICATION | 普通股、优先股等权益类投资 |
| 发行人类型 | DIMENSION | 政府/央行/政策性银行/商业银行/企业等 |
| 投资账面余额 | METRIC | 会计账面口径的余额(含减值准备前/后口径区分) |
| 风险加权资产 | METRIC | 按 RWA 口径折算的资产规模 |
| 资产支持证券(ABS) | CLASSIFICATION | 以基础资产产生的现金流作为偿付来源的证券 |

**手工补 G24/G21 跨表概念(目标 8 个,种子灌入)**:

| 概念名 | 类型 | 一句话定义 |
|---|---|---|
| 同业融入余额 | METRIC | 商业银行向其他金融机构融入资金的余额 |
| 金融机构 | ENTITY | 央行/政策银行/商业银行/证券/保险/信托等 |
| 最大百家 | SCOPE | 按余额排序的前 100 家交易对手 |
| 交易对手 | ENTITY | 同业交易、衍生品、回购等业务的对手方 |
| 流动性期限缺口 | METRIC | 未来某时段内资产现金流入与负债现金流出之差 |
| 合格优质流动性资产(HQLA) | METRIC | LCR 计算中符合监管口径的高流动性资产 |
| 流动性覆盖率(LCR) | METRIC | HQLA 余额 / 未来 30 日现金净流出 |
| 同业存放 | METRIC | 其他金融机构存放在本机构的资金余额 |

> ⚠️ 这份清单是我从 G31 填报说明 + 1104 文档结构推测的草案,需要你确认或调整,这是设计文档里**最依赖你判断的一处**。

### 4.4 概念抽取与回写

抽取来源:

- G31 填报说明 .doc → 用 instruction_parser 切段,LLM 抽候选概念(主语/宾语高频名词)
- 工单关闭时,推荐 1-2 个核心概念给用户勾选(**不强制**)
- 监管发文上传时,匹配现有别名,命中即放大召回;未命中的高频名词进入"待确认概念候选池"

回写到概念库的逻辑:

```
工单提交"处理结论"
  → 系统从结论文本抽取候选概念
  → 比对 reg_concept_alias,命中已有概念则在工单上挂 concept_id
  → 未命中的进入候选池,由概念管理员批量处理
  → 工单关闭后,如果结论里包含"口径变化"信号(关键词 LLM 识别)
     → 触发 reg_concept_version 新版本草稿
     → 概念管理员确认后生效
```

### 4.5 概念到报送项的辐射

这是概念库最核心的实用价值。例子:

```
监管发文 "拆放同业纳入同业融入统计范围"
  → 命中概念 "同业融入余额"(通过别名 "同业融入")
  → 该概念通过 reg_concept_reporting_item_map 关联到:
       - G24.MAIN.INTERBANK_BORROWING_BAL_TOP100 (PRIMARY_METRIC)
       - G27.MAIN.INTERBANK_DEPOSIT_BALANCE (RELATED via concept_relation)
       - 假设的 G14B.LIQUIDITY_INTERBANK (PRIMARY_METRIC)
  → 影响项自动放大召回 3 张表,而不是只在 G24 命中关键词
```

这套放大召回是报送平台厂商(Gientech/文思海辉)做不出来的——他们的字段目录没有"概念"层。

---

## 5. 两者的联动

### 5.1 数据耦合

每张规则卡片可挂多个概念(`reg_reporting_rule_card_concept_map`),角色分主体/客体/限定/相关。这样:

- **概念变 → 卡片预警**:概念出新版本时,自动列出所有引用该概念的卡片,提示是否需要更新
- **卡片变 → 概念演化**:L2 卡片被人工修订,如果修订涉及主体/客体概念的定义,自动建议在 `reg_concept_version` 创建草稿
- **影响分析放大**:新发文命中概念 → 命中所有相关卡片 → 命中所有引用卡片的工单历史 → 召回历史处理经验

### 5.2 流程位置

```
现有流程:
  上传发文 → 条款证据 → 语义识别 → 影响分析 → 工单草稿

加上规则卡片和概念库后:
  上传发文 → 条款证据
           → 语义识别 [增强:命中概念 + 命中卡片]
           → 影响分析 [增强:概念辐射 + 卡片匹配]
           → 工单草稿 [增强:卡片挂在工单底部]
           → 工单提交 [新增:卡片校验,提示不阻断]
           → 工单关闭 [新增:推荐挂载概念 + 触发概念版本草稿]
```

前端不需要新增页面,改的是现有几个 View 的展示内容。

---

## 6. 自动抽取与库更新流程(LLM 驱动)

### 6.1 这一节要解决什么

前面第 3.3 节描述了"从一份 G31 填报说明抽 L1 卡片"的方法,第 4.4 节描述了"概念抽取与回写"的来源,但**没把这两件事串成完整的自动化流水线**,尤其没说清:

- **触发**:前端上传新填报说明后,系统是不是自动跑抽取?手动还是自动?
- **合并**:新抽出的卡片/概念和库内已有的怎么合并?是覆盖、新建、还是建版本?
- **冲突**:LLM 抽出的内容和库内现状矛盾时,系统怎么处理?
- **可控**:LLM 抽出的东西什么时候可以直接进主表,什么时候必须人工确认?

本节补齐这套设计。

### 6.2 总体流程

```
[前端] 上传新填报说明 / 修订对照表 / 表样
  → POST /api/documents/upload(已有)
  → 后端保存原文 + 解析正文 + 识别文档类型
  → 文档类型 ∈ {INSTRUCTION, REVISION_TABLE, TABLE_FORM} 时自动 enqueue 抽取任务
  → POST /api/extraction-jobs(新增,异步 BackgroundTask)
      → extraction_pipeline.py 跑 6 阶段(见 6.3)
      → 候选卡片/概念/版本草稿/冲突项 → 写入"候选池"(不进主表)
      → 任务状态:PENDING → RUNNING → REVIEW_PENDING
  → 前端 LibraryView 顶部红点条提示"X 候选 / Y 冲突,去审核"
  → 用户进入审核队列 → 逐条/批量 采纳/退回/挂起
  → POST /api/extraction-jobs/{id}/apply
  → 选中项写入主表,卡片版本号自动迁移,概念版本草稿生效
  → 任务状态 → APPLIED
```

**核心约束**:**LLM 抽出的所有内容都不直接进 ACTIVE 主表,必须经人工确认才生效**。这是项目"AI 不发明事实"原则在这条流程上的落地。

### 6.3 抽取流水线六阶段(新增 `extraction_pipeline.py`)

| 阶段 | 是否用 LLM | 输入 | 输出 | 防幻觉约束 |
|---|:---:|---|---|---|
| **1. 文档预处理** | ❌ | doc/xlsx/xls | 段落 / 修订表行 / 表样结构 | 复用 instruction_parser / revision_table_parser / excel_parser |
| **2. L1 卡片抽取** | ✅ | 段落 + 报表上下文 + 已有指标清单 | 候选 L1 卡片(card_text + evidence_text + item_code 候选 + confidence) | evidence_text 必须能在原文精确匹配,否则该卡片 evidence_verified=false 打黄牌 |
| **3. 概念候选抽取** | ✅ | 段落 | 候选概念列表(canonical_name + 出处 evidence) | 候选名词必须能在原文找到出处片段 |
| **4. 库内比对** | ✅(部分) | 候选 + 库内现状 | 分四类:重复 / 更新候选 / 纯新增 / 冲突 | 比对仅在结构化字段层做,不允许 LLM 编造字段名;定义变化判定必须给出原文 A 段 vs 原文 B 段的具体差异点 |
| **5. L2 结构化** | ✅ | 已 CONFIRMED 的 L1 卡片 | 候选 L2 四元组,绑定 concept_id | subject/object 必须命中 reg_concept,不命中 → 进"待新建概念"队列;不允许 LLM 创建新概念 |
| **6. 写入候选池** | ❌ | 上述全部产物 | 落库到候选池 | 全部 status=DRAFT,review_status=PENDING |

### 6.4 库内比对的判定矩阵

**卡片层面(阶段 4 的核心逻辑)**:

| 场景 | 判定 | 系统动作 |
|---|---|---|
| 新候选与库内卡片 evidence_text 完全一致 | 重复 | 不入候选池,任务日志记录 |
| 新候选与库内卡片同 (item_code, subject, predicate) | 同卡片的新版本 | 入候选池,标记 "更新候选";apply 时:旧卡片 effective_to_version=前一版本,新卡片 effective_from_version=当前版本 |
| 新候选与库内卡片同 item_code 但语义不同 | 纯新增 | 入候选池,标记 "新增候选" |
| 库内卡片在新文档对应位置找不到任何内容 | 疑似下线 | 标记 "建议下线",apply 后 status=ARCHIVED |

**概念层面**:

| 场景 | 判定 | 系统动作 |
|---|---|---|
| 新候选片段匹配现有 alias,LLM 判定定义无实质变化 | 无变化 | 若是新的同义说法,仅追加一条 alias |
| 新候选片段匹配现有 alias,LLM 判定定义有变化 | 口径演化 | 生成 reg_concept_version 草稿(effective_from 留空,apply 时填) |
| 新候选片段未匹配任何 alias 但高频出现 | 候选新概念 | 入候选池,status=DRAFT |
| 新候选片段与库内概念定义矛盾 | 冲突 | 标 "口径冲突待裁决",阻塞自动 apply,必须人工裁决 |

### 6.5 LLM 不能做的事(防失控清单)

| 操作 | 是否允许 LLM 直接做 |
|---|:---:|
| 修改 status=ACTIVE 的卡片或概念 | ❌ |
| 直接创建概念主表记录 | ❌(只能进候选池) |
| 直接创建概念版本 | ❌(只能创建草稿,人工 apply 时才生效) |
| 合并两个 ACTIVE 概念 | ❌(只能建议,人工执行) |
| 编造 evidence_text(找不到原文锚点) | ❌(自动打黄牌) |
| 跨文档推断(在当前 doc 找不到证据,凭"常识"补) | ❌(必须基于当前 doc + 库内已有事实) |
| 给候选打 confidence | ✅ |
| 给候选写"建议理由" | ✅ |

### 6.6 三级处置策略(避免审核疲劳)

#### 6.6.1 为什么要分层

第 6.5 节的"必须人工确认"原则如果不分层,会出问题:

- 单次上传一份 G31 填报说明 → 出 20-40 个候选项
- 审核者疲劳 → 实际变成"全选 → 批量盖章"
- **防幻觉机制反而失效**,LLM 输出的低质量内容也被一并通过

所以需要**让真正低风险的候选自动通过,把人工精力集中在真正需要判断的事上**。

#### 6.6.2 三档定义

| 档位 | 触发条件(任一满足即归入对应档) | 处理方式 |
|---|---|---|
| **自动 apply** | 全部满足:`confidence=HIGH` + `evidence_verified=true` + 候选类型 ∈ {新增 L1 卡片, 新增别名, 新增概念} + 未标 conflict | status 直接置 ACTIVE,review_status='AUTO_APPROVED';审核队列以"已自动通过" Tab 展示,可随时一键回滚 |
| **必审** | `confidence ∈ {MEDIUM, LOW}` / `evidence_verified=false` / 候选类型 ∈ {L2 结构卡, 概念版本演化, 概念关系建议, 修改已有 ACTIVE, 建议下线} | 入候选池,审核队列支持批量操作("全选 HIGH 置信度 + 同类型"一键 apply、"全部退回"一键拒绝) |
| **强阻断** | 库内已存在 ACTIVE 资产与新候选矛盾(口径冲突)/ 删除已 ACTIVE 资产 / 修改已锁定的核心概念 | **阻塞整个任务的 apply 操作**,必须人工裁决冲突后才能解锁 |

#### 6.6.3 自动 apply 的兜底机制(可观测 + 回滚)

为了避免"AI 自动写库,业务方不知情":

- 审核队列页设独立"已自动通过(近 7/30 天)" Tab
- 每条 AUTO_APPROVED 都可一键回滚为 ARCHIVED
- 每周自动给概念管理员发汇总邮件:"本周自动通过 X 条,请抽查"
- 一旦回滚率 > 阈值(如 10%),系统自动把对应类型从"自动 apply 白名单"移除,提示运营复核 LLM 配置

#### 6.6.4 预期审核量(基于 G31 一份填报说明估算)

| 候选类型 | 估计总数 | 自动 apply | 必审 | 强阻断 |
|---|:---:|:---:|:---:|:---:|
| L1 新增卡片 | 8-12 | 6-9 | 2-3 | 0 |
| L1 卡片更新 | 0-3 | 0 | 0-3 | 0 |
| L2 候选(P1 才有) | 8-12 | 0 | 8-12 | 0 |
| 新增概念 | 3-5 | 2-3 | 1-2 | 0 |
| 概念版本草稿 | 0-3 | 0 | 0-3 | 0 |
| 冲突 | 0-1 | 0 | 0 | 0-1 |

**P0 阶段单次审核负担**:从原来的 20-40 条,降到 5-10 条,且真正"需要逐字看"的只有 2-3 条(低置信修改 + 冲突)。

#### 6.6.5 Schema 微调

`reg_reporting_rule_card.review_status` 和 `reg_concept.status` 的 ENUM 需扩展一个值:

```sql
-- review_status 在原有 ('PENDING','CONFIRMED','REJECTED','DEPRECATED') 基础上追加:
ALTER TABLE reg_reporting_rule_card MODIFY review_status
  ENUM('PENDING','CONFIRMED','AUTO_APPROVED','REJECTED','DEPRECATED') DEFAULT 'PENDING';

-- concept 主表新增字段,标记是否锁定(影响"强阻断"判定):
ALTER TABLE reg_concept ADD COLUMN is_locked BOOLEAN DEFAULT FALSE;
```

#### 6.6.6 对 demo 的额外价值

这套分层不只是工程优化,也是叙事卖点:

> "本系统不是 AI 全自动,也不是 AI 全人工——AI 自动处理 70% 的低风险增量,人工聚焦在 30% 真正需要判断的事。这是银行场景下的可控性设计。"

---

### 6.7 新增数据模型

抽取任务表 `reg_extraction_job`:

```sql
CREATE TABLE reg_extraction_job (
  id                       BIGINT PRIMARY KEY AUTO_INCREMENT,
  document_id              BIGINT NOT NULL,
  job_type                 ENUM('FULL','RULE_ONLY','CONCEPT_ONLY') DEFAULT 'FULL',
  trigger_source           ENUM('AUTO_ON_UPLOAD','MANUAL') NOT NULL,
  status                   ENUM('PENDING','RUNNING','REVIEW_PENDING','APPLIED','FAILED','CANCELLED') NOT NULL,
  stage                    VARCHAR(64),
  error_message            TEXT,
  candidate_card_count     INT DEFAULT 0,
  candidate_concept_count  INT DEFAULT 0,
  version_draft_count      INT DEFAULT 0,
  conflict_count           INT DEFAULT 0,
  started_at               DATETIME,
  finished_at              DATETIME,
  triggered_by             VARCHAR(64),
  created_at               DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_doc (document_id),
  INDEX idx_status (status)
);
```

三张候选池表加追溯字段:

```sql
ALTER TABLE reg_reporting_rule_card  ADD COLUMN extraction_job_id BIGINT;
ALTER TABLE reg_concept              ADD COLUMN extraction_job_id BIGINT;
ALTER TABLE reg_concept_version      ADD COLUMN extraction_job_id BIGINT;
```

### 6.8 新增 / 调整接口

```
POST   /api/extraction-jobs                      # 创建抽取任务(自动 or 手动)
GET    /api/extraction-jobs                      # 列表,支持 status / document_id 过滤
GET    /api/extraction-jobs/{job_id}             # 详情(含各阶段状态)
GET    /api/extraction-jobs/{job_id}/candidates  # 候选池(卡片/概念/版本/冲突分组)
POST   /api/extraction-jobs/{job_id}/apply       # 批量应用,body 指定要应用的候选 id 列表
PATCH  /api/extraction-jobs/{job_id}/cancel      # 取消任务
```

### 6.9 前端审核队列

LibraryView 顶部新增红点条:

```
[10 张候选卡片] [3 个候选概念] [2 个口径变化] [1 个冲突]   去审核 →
```

点击进入新页面 `ReviewQueueView`:

```
┌──────────────────────────────┬──────────────────────────┐
│ 左:候选列表(分 Tab)          │ 右:详情 + 原文锚点       │
│  · 候选卡片 (10)              │                            │
│    · RC_候选_001 ★高          │ 候选内容:                 │
│    · RC_候选_002 ★中          │ 来源:G31填报说明 §3.5    │
│  · 候选概念 (3)               │ 原文片段:[绿色高亮]      │
│  · 口径变化 (2)               │                            │
│  · 冲突 (1) [需裁决]          │ 库内现状(对比):          │
│                               │ 旧定义 ↔ 新片段 diff      │
│  [全选高置信度]              │ [采纳] [退回] [挂起]      │
└──────────────────────────────┴──────────────────────────┘
```

### 6.10 触发模式

| 模式 | 触发点 | 适用场景 |
|---|---|---|
| **自动触发** | 上传文档后,后端识别 doc 类型 ∈ {INSTRUCTION, REVISION_TABLE, TABLE_FORM},自动 enqueue | 主流程 |
| **手动触发** | LibraryView "手动抽取"按钮 → 选已上传文档 → 触发 | 历史文档重跑、demo 演示 |

二者调同一接口,只是 `trigger_source` 字段不同。

### 6.11 与现有 5 步流程的关系

**抽取流水线和 5 步加工流程是平行的,不嵌入其中**:

- 5 步流程:针对一次监管变更触发的任务,最终产物是**工单**
- 抽取流水线:持续维护规则/概念知识库,产物是**库资产**
- 二者共享原始文档(`reg_documents`),但产物不同

但二者在"影响分析"阶段汇合:

```
5 步流程的"影响分析"阶段
  → 调 /api/concepts/match
  → 命中本次发文涉及的概念(由历次抽取沉淀而来)
  → 通过 reg_concept_reporting_item_map 放大召回到报送项
  → 通过 reg_reporting_rule_card_concept_map 拉出相关卡片
  → ACTIVE 卡片做"影响项 + 工单参考"
  → DRAFT/PENDING 卡片做"待确认提示"
```

也就是说:**抽取流水线每跑一次,5 步流程的影响分析就更精准一分**——这才是飞轮的真正含义。

### 6.12 实施安排

**P0 不实现这套流水线**(经讨论确认,见第 10 节)。P0 阶段抽卡片走"开发手动跑脚本 + 人工确认 + 灌库"的简易模式,先把数据沉淀下来给 demo 用。

**P1(D+7~D+14)实施**:

| # | 任务 |
|---|---|
| EX-1 | `reg_extraction_job` 表 + 三张候选表加 `extraction_job_id` 字段 |
| EX-2 | `extraction_pipeline.py` 实现 6 阶段(预处理 / L1 抽 / 概念抽 / 比对 / 写候选池;L2 异步) |
| EX-3 | 上传文档时识别类型 → 自动 enqueue 任务(FastAPI BackgroundTask 即可,不上 celery) |
| EX-4 | 审核队列 API + 前端 ReviewQueueView |
| EX-5 | 批量 apply 接口 + 卡片版本号自动迁移逻辑 |
| EX-6 | LibraryView 红点条 + DocumentDetailView 关联任务状态 |

---

## 7. 前端改造点

| 现有页面 | 改动 |
|---|---|
| PortraitView | 语义识别结果旁新增"命中概念"芯片列表,点击跳概念详情抽屉 |
| ImpactView | 影响项卡片新增"关联概念"标签;新增"概念命中雷达图"组件,可视化本次发文命中哪些概念、辐射到哪些报送项 |
| ReviewTicketView | 工单底部新增"规则卡片参考"折叠区,工单提交后新增"AI 复核意见"右栏 |
| LibraryView(目前是占位) | 升级成"规则资产 + 概念资产"双 Tab:左 Tab 是卡片列表(按报表过滤),右 Tab 是概念列表(按类型过滤) |
| (新建) ConceptDetailDrawer | 概念详情抽屉:当前定义、版本演化时间轴、关联报送项、关联卡片 |

---

## 8. 接口设计(后端契约)

新增 8 个 REST 端点:

```
# 规则卡片
GET    /api/rule-cards                          # 列表,支持 object_code/item_code/level/status 过滤
GET    /api/rule-cards/{card_id}                # 详情
POST   /api/rule-cards/extract-from-document    # 触发从文档抽取 L1 候选卡片
PATCH  /api/rule-cards/{card_id}/review         # 人工复核(confirm/reject/edit)
POST   /api/tickets/{ticket_id}/validate-cards  # 触发工单的卡片校验
PATCH  /api/rule-card-validations/{vid}/override # 人工对校验结果做 accept/reject

# 概念库
GET    /api/concepts                            # 列表,支持 type/scope/keyword 过滤
GET    /api/concepts/{concept_id}               # 详情(含别名、版本、关联报送项)
GET    /api/concepts/{concept_id}/lineage       # 概念辐射到的所有报送项 + 关联卡片
POST   /api/concepts                            # 新建概念
PATCH  /api/concepts/{concept_id}               # 修改
POST   /api/concepts/{concept_id}/versions      # 新增版本
POST   /api/concepts/match                      # 给一段文本,返回命中的概念(用于影响分析放大)
```

---

## 9. 实施计划

### 9.1 阶段划分

**P0 · Demo 前必须(< 4 天)**

| # | 任务 | 工作量 |
|---|---|---|
| P0-1 | 建 8 张新表的 DDL + Alembic 迁移脚本 | 0.5 天 |
| P0-2 | 手工灌 20 个概念种子(`reg_concept` + `reg_concept_alias` + `reg_concept_reporting_item_map`) | 1 天 |
| P0-3 | 从 G31 填报说明抽 L1 卡片(LLM + 人工修订),目标 8-12 张 | 1 天 |
| P0-4 | `reporting_ticket_generator.py` 增加卡片挂载,工单 Markdown 底部展示 | 0.5 天 |
| P0-5 | 前端 ImpactView 增加"命中概念"芯片 + "概念命中雷达图"组件 | 1 天 |
| P0-6 | `/api/concepts/match` 接口实现(关键词 + 别名匹配,先不上语义相似度) | 0.5 天 |

**P1 · 一期内补齐(D+14)**

| # | 任务 |
|---|---|
| P1-1 | L2 结构卡抽取流水线 + 人工确认 UI |
| P1-2 | `reg_concept_version` 落地,工单关闭时触发版本草稿 |
| P1-3 | `reg_reporting_rule_card_validation` 落地,工单提交触发 LLM judge |
| P1-4 | LibraryView 升级为"规则资产 + 概念资产"双 Tab |
| P1-5 | ConceptDetailDrawer 实现 |

**P2 · 二期(D+30 及以后)**

| # | 任务 |
|---|---|
| P2-1 | L3 可执行卡片 + SQL 静态分析校验(**经讨论延后,二期再评估**) |
| P2-2 | `reg_concept_relation` 关系挖掘(从卡片 L2 中自动推导 INCLUDES/EXCLUDES 关系) |
| P2-3 | 概念抽取从手工灌升级为 LLM 候选 + 人工确认 |
| P2-4 | 概念匹配上语义相似度(embedding) |
| P2-5 | 扩展到 G24/G21/G25/G27 真实材料(需要先采集真填报说明) |
| P2-6 | 接入真实权限模型,`created_by` / `reviewed_by` 从 mock 角色切到真用户 |

### 9.2 现有代码的改动清单

| 文件 | 改动 |
|---|---|
| `backend/app/models/` | 新增 8 个 ORM 模型文件 |
| `backend/app/repositories/` | 新增 rule_card_repo.py、concept_repo.py |
| `backend/app/services/rule_extractor.py` | 从 35 行扩展到约 400 行,实现 L1/L2 抽取 |
| `backend/app/services/reporting_ticket_generator.py` | 工单生成时调用 rule_card 查询,挂载到 Markdown |
| `backend/app/services/reporting_impact_analyzer.py` | 影响分析时调用 concept_match,放大召回 |
| `backend/app/api/` | 新增 routes_rule_cards.py、routes_concepts.py |
| `backend/app/services/rule_library.py` | **删除**(经讨论确认) |
| `backend/app/api/routes_rule_library.py` | **删除**(main.py 已不注册,无引用) |
| `frontend/src/api/client.ts` | 删除 4 个 `/rule-library/*` 方法 |
| `frontend/src/types/api.ts` | 删除 `RuleLibrarySeed` 接口;`RuleCard` 重构为新字段 |
| `frontend/src/data/mock.ts` | 删除 `sampleRuleLibrarySeed`;`sampleRuleCards` 重写为新语义 |
| `frontend/src/api/client.test.ts` | 删除 4 个 `/rule-library/*` 接口的测试用例 |
| `frontend/src/views/ImpactView.vue` | 新增概念命中展示 |
| `frontend/src/views/ReviewTicketView.vue` | 新增卡片参考折叠区 + AI 复核意见栏 |
| `frontend/src/views/LibraryView.vue` | 升级双 Tab |
| `frontend/src/components/ConceptDetailDrawer.vue` | 新建 |
| `frontend/src/components/ConceptRadar.vue` | 新建(概念命中雷达图) |
| `backend/app/services/reporting_seed.py` | 增加概念种子函数 |

---

## 10. 决议记录(2026-05-21 与用户确认)

1. ✅ **20 个初始概念清单(第 4.3 节)**:无增删,按草案落地。
2. ✅ **L1 卡片支持对象级**:`reporting_item_code` 允许 NULL,挂到整张报表。
3. ✅ **校验结果独立表**:新建 `reg_reporting_rule_card_validation`,不并入 `review_records`。
4. ✅ **角色字段预留**:`created_by` / `reviewed_by` 在所有写操作表(rule_card / concept / concept_version / concept_relation / validation)上预留,demo 阶段前端 mock"概念管理员"角色。
5. ✅ **L3 暂不实现**:一期完成 L1 + L2,L3 数据模型保留字段,二期再评估。
6. ✅ **旧主线删除**:`routes_rule_library.py` + `services/rule_library.py` + 前端 4 个 `/rule-library/*` 方法 + `RuleLibrarySeed` 类型 + `sampleRuleLibrarySeed` mock + 对应测试,全部删除(见第 1.5 节清单)。`RuleCard` 类型保留但重构为新字段。

---

## 11. 不在本次设计范围

明确不做的事情,避免范围蔓延:

- 不做语义向量召回(embedding)——P0 用关键词 + 别名硬匹配就够
- 不做图数据库迁移——MySQL + 递归 CTE 撑得住
- 不做概念自动合并/去重——靠人工
- 不做规则引擎(Drools 之类)——L3 校验直接执行 SQL,L2 走 LLM judge
- 不做权限模型——一期所有操作不分角色,前端 mock
- 不接入真实工单系统——保持现有"草稿"形态
