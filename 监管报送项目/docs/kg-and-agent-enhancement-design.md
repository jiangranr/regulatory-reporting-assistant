# 业务知识图谱 + Agent 工作流增强设计

> 创建日期：2026-05-27
> 文档定位：基于现有 webproject 主流程，**叠加**业务知识图谱可视化与可控 Agent 工作流两套能力
> 适用项目：监管报送项目
> 状态：待审查（设计稿）

---

## 0 · 主线不丢

### 0.1 一句话定位

> 把现有"AI 应用层主流水平"升级到"**金融监管场景下 AI 工程方法论的领先实践**"，
> 通过引入业务知识图谱可视化 + Self-Correcting + ReAct Tool-Using Agent + 工单执行规划**四套能力**，
> **不动**上传 / 画像 / 字段定位 / 影响分析 / 工单生成的主流程语义。

### 0.2 四套能力的角色

```
┌──────────────────────────────────────────────────────────────┐
│ 主流程（不动）                                                │
│   上传 → 画像 → 字段定位 → 影响分析 → 工单                    │
└─────────────────┬────────────────────────────────────────────┘
                  │
                  │  内部能力（本设计新增 4 套）
                  ▼
┌──────────────────────────────────────────────────────────────┐
│ 模块 A · 业务知识图谱可视化                                    │
│   - 让"概念库 + 关系"的设计**显式化为图**                     │
│   - 演示效果最强；技术含量在"可视化 + 关系遍历"               │
│   - 解决：业务知识可视化诉求 / 概念辐射展示                   │
├──────────────────────────────────────────────────────────────┤
│ 模块 B · Self-Correcting Loop（自纠错 Agent）                  │
│   - 对 evidence_verified=false 的 signal 自动二次核验          │
│   - 解决"AI 幻觉率没量化没视觉"这个 #2 风险                   │
├──────────────────────────────────────────────────────────────┤
│ 模块 C · ReAct Tool-Using Agent                                │
│   - 让 LLM 在解读监管发文时主动调用 4 个 service 工具          │
│   - 解决"AI 是黑盒"的演示痛点                                 │
├──────────────────────────────────────────────────────────────┤
│ 模块 D · AI 工单执行规划 ⭐ 业务价值最高                       │
│   - 让 LLM 把 N 个结构化子单整合成可执行的"项目经理视角"叙事   │
│   - 解决：业务方拿到 9 个工单不知道先做哪个的"导航问题"        │
│   - 输出：执行顺序 / 关键路径 / 风险预警 / 跨团队协作建议       │
└──────────────────────────────────────────────────────────────┘
```

**四个模块的协作叙事**：
- A 让**数据**可信（业务知识可视化）
- B 让 **AI 输出**可信（自纠错锚定）
- C 让 **AI 推理过程**可信（工具调用透明）
- D 让 **AI 最终建议**可执行（项目经理视角整合）

### 0.3 设计 4 原则（金融场景核心）

1. **可控优先于自主** — 银行场景拒绝"AutoGPT 全自主 Agent"。所有 Agent 必须可暂停、可接管、可审计
2. **不破坏存量** — 新能力作为可插拔的增量路径，旧调用方零修改；主流程语义保持稳定
3. **可视化即可信** — Agent 每步推理过程必须显式呈现给业务方，不做黑盒
4. **诚实标注边界** — 哪些是确定性、哪些是 AI 推断、哪些是 fallback，UI 必须分档展示

### 0.4 与既有设计文档的关系

| 既有文档 | 本文档关系 |
|---|---|
| `rule-card-and-concept-kb-design.md` | 概念库 schema 不变，**叠加**图遍历能力 |
| `concept-and-ticket-reuse-design.md` | 补丁 A/B/D 不变；本文档是其上的"AI 工程方法论加固" |
| `feasibility-audit.md` | 本文档**实质解决**其中风险 #1 / #2 / #3 |
| `2026-05-27-ticket-governance-workbench-design.md` | Codex 在做的 Task 5 不受影响 |

---

## 1 · 模块 A · 业务知识图谱可视化

### 1.1 现状盘点

后端 schema 已具备 KG 全部要素：

| 表 | 充当 KG 的什么 |
|---|---|
| `RegConcept` | 节点（按 `concept_type` 分 6 类）|
| `RegConceptAlias` | 节点属性（同义词列表）|
| `RegConceptRelation` | 有向边，含 `relation_type`（INCLUDES/EXCLUDES/SUBSET_OF/DEPENDS_ON/SYNONYM/PREDECESSOR/REPLACES） |
| `RegConceptVersion` | 时间维度演化轨迹 |
| `RegConceptReportingItemMap` | 跨类型边（概念 → 报送项）|

**缺的是"显式化为图 + 用图算法 + 可视化"**。

### 1.2 要做什么

| # | 工作项 | 工作量 |
|---|---|---|
| A1 | 后端 `concept_graph_service.py` + `GET /api/concepts/graph` | 0.5d |
| A2 | 前端 `ConceptGraphView.vue`（cytoscape.js 力导向图）| 1d |
| A3 | 在 `LibraryView` 加 "知识图谱" Tab 入口 | 0.2d |
| A4 | eval case 锁住"图遍历 + 跨概念召回"效果 | 0.3d |

合计 **2 天**。

### 1.3 后端设计

#### 1.3.1 新增 service：`concept_graph_service.py`

```python
class ConceptGraphNode(BaseModel):
    concept_code: str
    canonical_name: str
    concept_type: str
    reporting_system_scope: str
    aliases: list[str]
    is_root: bool = False           # 是不是查询起点

class ConceptGraphEdge(BaseModel):
    from_concept_code: str
    to_concept_code: str
    relation_type: str              # INCLUDES / SYNONYM / ...
    confidence_level: str

class ConceptGraphResponse(BaseModel):
    nodes: list[ConceptGraphNode]
    edges: list[ConceptGraphEdge]
    # 用于前端按报送项分组着色
    related_reporting_items: dict[str, list[str]]  # concept_code → item_codes


def build_concept_graph(
    session: Session,
    root_concept_code: str | None = None,
    depth: int = 2,
    relation_types: list[str] | None = None,
    scope: str | None = None,
) -> ConceptGraphResponse:
    """
    若 root_concept_code 为空，返回整图（默认）；
    否则 BFS 取 N 跳邻居。

    depth=2 是性能与可读性的折中：23 个概念时整图够看，
    1000+ 概念时按 root + depth 局部展开。
    """
    ...
```

#### 1.3.2 新增 API：`GET /api/concepts/graph`

```
查询参数：
  root_concept_code  根概念（可选；空时返回整图）
  depth              最大遍历深度（默认 2，最大 3）
  relation_types     过滤关系类型，逗号分隔
  scope              限制 reporting_system_scope

响应：ConceptGraphResponse
```

#### 1.3.3 不影响现有 routes_concepts

完全新增的 endpoint，既有 `GET /api/concepts` / `POST /api/concepts/match` 等接口不变。

### 1.4 前端设计

#### 1.4.1 新视图 `ConceptGraphView.vue`

- 库选型：**cytoscape.js**（成熟、配 vue 包装好、支持中文标签）
- 默认显示整图（23 个 concept + 关系）
- 节点：
  - 颜色按 `concept_type`：METRIC=蓝 / SCOPE=橙 / CLASSIFICATION=紫 / CALCULATION=绿 / DIMENSION=灰 / ENTITY=红
  - 大小按 `total_matched_count`（未来加补丁 G match 埋点后启用）
  - 形状：标准概念=圆形；CROSS scope=六边形
- 边：
  - 颜色按 `relation_type`：INCLUDES=实线绿 / EXCLUDES=实线红 / SUBSET_OF=点线灰 / DEPENDS_ON=实线蓝 / SYNONYM=虚线灰 / PREDECESSOR/REPLACES=实线橙
  - 箭头方向：from → to
- 交互：
  - 点击节点 → 右侧抽屉显示概念详情（aliases / definition / related_items / 命中次数）
  - 双击节点 → 以该节点为 root 重新加载 depth=2 局部图
  - hover → 高亮该节点直接邻居

#### 1.4.2 `LibraryView` 顶部新增 Tab

```
[规则与口径] [监管概念库] [📊 知识图谱]  ← 新增
                                 ↑
                            点击进入 ConceptGraphView
```

### 1.5 eval 锁住

新增 case `concept_graph_traversal.json`：

```json
{
  "id": "concept_graph_traversal",
  "description": "图遍历能找到概念的 2 跳邻居",
  "target": "concept_graph",
  "inputs": {
    "root": "CON_BOND_INVESTMENT_BAL",
    "depth": 2
  },
  "expectations": [
    { "kind": "signal_count", "spec": { "min": 3, "max": 30 } },
    { "kind": "must_contain", "spec": { "keyword": "CON_UNDERLYING_ASSET" } }
  ]
}
```

### 1.6 可宣称话术

> ✅ "基于业务知识图谱建模监管报送领域：概念 + 别名 + 关系（7 种语义边）+ 版本演化，
> 图遍历驱动跨概念召回扩展，**可视化展示概念辐射网络**。"

不要宣称：
- ❌ "自研 KG 推理算法"
- ❌ "图神经网络 (GNN)"
- ❌ "百万级 KG 推理"

### 1.7 验收标准

- [ ] `GET /api/concepts/graph` 接口可用，返回正确的 nodes + edges
- [ ] `LibraryView` 新 Tab 入口，点击进入图谱视图
- [ ] 整图能渲染（23 个概念），节点边视觉清晰
- [ ] 点击节点显示详情抽屉
- [ ] 双击切换 root，重新渲染局部图
- [ ] eval case 通过
- [ ] 设计文档说明清晰

---

## 2 · 模块 B · Self-Correcting Loop（自纠错 Agent）

### 2.1 现状盘点

`document_profiler.py::_ground_signal()` 已经在做 evidence 核验：

```python
def _ground_signal(signal: TableChangeSignal, doc_normalized: str) -> TableChangeSignal:
    """检查 evidence_text 是否真实存在于原文中。
    存在 → evidence_verified=True
    不存在 → evidence_verified=False
    """
```

**缺的是"检测到 false 之后什么都不做"**。

### 2.2 要做什么

让 evidence_verified=false 的 signal 进入"自纠错循环"：

```
LLM 抽出 10 条 signal
  ↓
_ground_signal 核验
  ├─ 7 条 verified=true → 直接通过
  └─ 3 条 verified=false → 进入 SelfCorrectingAgent
                              ↓
                         对每条 signal：
                           1. 取 indicator_hint + change_type + 原文片段（hint 附近 ±500 字）
                           2. 重新调 LLM：
                              "请在以下原文中找最能支持
                               '{indicator_hint} {change_type}' 的句子，
                               必须是逐字摘录，不允许改写。"
                           3. 二次 _ground_signal 核验
                           4a. 成功 verified=true → 更新 signal，标 corrected=true
                           4b. 仍 false → 标 quarantined=true，UI 黄牌
                           4c. 重试次数 ≥ 2 仍 false → 弃用，整体降级 MANUAL_REVIEW
```

### 2.3 设计要点

#### 2.3.1 新增 service：`self_correcting_agent.py`

```python
@dataclass
class CorrectionResult:
    original_signal: TableChangeSignal
    corrected_signal: TableChangeSignal | None  # None 表示纠错失败
    attempts: int
    final_status: str  # CORRECTED / QUARANTINED / GIVEN_UP
    trace: list[dict]  # 每次重试的 prompt + response 留痕


class SelfCorrectingAgent:
    """对 evidence_verified=false 的 signal 启动二次核验循环。
    设计目标：把 AI 幻觉自动修正，不能修正的标记隔离。"""

    def __init__(self, max_retries: int = 2, llm_timeout: int = 30):
        self.max_retries = max_retries
        self.llm_timeout = llm_timeout

    def correct(
        self,
        signal: TableChangeSignal,
        document_text: str,
        doc_normalized: str,
    ) -> CorrectionResult:
        ...
```

#### 2.3.2 集成点：`document_profiler.generate_document_profile`

```python
change_signals = [_ground_signal(s, doc_normalized) for s in change_signals]

# 新增：对 verified=false 的 signal 启动自纠错
if any(not s.evidence_verified for s in change_signals):
    agent = SelfCorrectingAgent()
    corrected_signals = []
    for s in change_signals:
        if s.evidence_verified:
            corrected_signals.append(s)
        else:
            result = agent.correct(s, document.parsed_text, doc_normalized)
            if result.corrected_signal:
                corrected_signals.append(result.corrected_signal)
            else:
                # quarantine：保留原 signal 但加标记
                s.match_status = "QUARANTINED_UNVERIFIED"
                corrected_signals.append(s)
            # 留痕到 audit_logs
            _audit_correction(result, session)
    change_signals = corrected_signals
```

#### 2.3.3 失败兜底

- max_retries=2 次内未成功 → 标记 quarantined，**不阻塞主流程**
- LLM 调用失败 → 退回原 signal（保持 verified=false）
- audit_logs 必须留痕（detail JSON 含 attempts / trace / final_status）

### 2.4 前端展示

`PortraitView` 的 change_signals 列表加 3 档徽章：

| 徽章 | 含义 |
|---|---|
| ✅ verified | 原文已锚定（一次性通过） |
| 🔄 corrected | 经自纠错 Agent 二次锚定通过 |
| ⚠️ quarantined | AI 无法精确锚定，**人工审核** |

### 2.5 eval 锁住

新增 case `agent_self_correcting.json`：

构造一条故意 evidence_text 不在原文里的 signal，验证 Agent 能否纠正回原文存在的句子。

### 2.6 可宣称话术

> ✅ "Self-Correcting Agent Loop：对 AI 抽出的所有信号做原文锚定核验，
> 未通过的自动启动二次纠错循环，最多 2 次重试后仍无法锚定的隔离到人工审核队列。
> **AI 不发明事实，发明了被自动标记**。"

### 2.7 验收标准

- [ ] `self_correcting_agent.py` 实现 + unit test
- [ ] 集成到 `document_profiler` 主路径
- [ ] verified=false 的 signal 进入 Agent，max_retries=2
- [ ] CORRECTED / QUARANTINED 状态正确写入 audit_logs
- [ ] PortraitView 三档徽章可视
- [ ] eval case 通过

---

## 3 · 模块 C · ReAct Tool-Using Agent

### 3.1 现状盘点

当前 `document_profiler` 是**单次 LLM 调用**：

```
prompt（含报表本体 + 报表分区 + 文档正文）→ LLM → JSON 输出
```

LLM 是被动的，**无法主动调用我们已有的 service 工具**（concept_matcher / item_resolver / rule_cards / decision_archive）。

### 3.2 要做什么

引入 ReAct（Reasoning + Acting）模式的 Agent，让 LLM 在分析监管发文时**自主决定何时调用哪个工具**。

### 3.3 ReAct Agent 工作流

```
任务：分析这段监管发文 "调整G24同业融入余额统计口径..."

Step 1
  Thought: 我需要先识别这段话涉及哪些监管业务概念
  Action: match_concept(text="调整G24同业融入余额统计口径...")
  Observation: [CON_INTERBANK_BORROWING_BAL, CON_FINANCIAL_INSTITUTION, CON_TOP_100]

Step 2
  Thought: 这些概念对应哪些具体报送项？我先查 G24 的具体 item
  Action: resolve_item(table_code="G24", indicator_hint="同业融入余额")
  Observation: matched_item_code = G24.MAIN.INTERBANK_BORROWING_BAL_TOP100

Step 3
  Thought: 这个报送项有没有相关的规则卡片需要参考？
  Action: lookup_rule_cards(reporting_item_code="G24.MAIN.INTERBANK_BORROWING_BAL_TOP100")
  Observation: [RC_G24_001, RC_G24_002] (2 张卡片)

Step 4
  Thought: 历史上有没有类似变更的处理经验？
  Action: search_historical_decisions(concept_codes=["CON_INTERBANK_BORROWING_BAL"])
  Observation: [] (空，W2 之前)

Step 5
  Thought: 已经收集足够信息，可以产出 change_signal 了
  Final Answer: {
    "table_code": "G24",
    "indicator_hint": "同业融入余额",
    "matched_item_code": "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
    "change_type": "SCOPE_ADJUST",
    "related_concepts": ["CON_INTERBANK_BORROWING_BAL", "CON_FINANCIAL_INSTITUTION", "CON_TOP_100"],
    "related_rule_cards": ["RC_G24_001", "RC_G24_002"],
    "confidence": 0.92
  }
```

每一步都被记录、可视化、可暂停。

### 3.4 设计要点

#### 3.4.1 工具定义（4 个）

```python
# app/services/agent_tools.py

@dataclass
class AgentTool:
    name: str
    description: str       # 给 LLM 看的描述（用于 function calling）
    parameters_schema: dict
    handler: Callable

AGENT_TOOLS: dict[str, AgentTool] = {
    "match_concept": AgentTool(
        name="match_concept",
        description="给定一段中文文本，返回命中的监管业务概念列表，包含概念代码、规范名、召回路径。",
        parameters_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "scope": {"type": "string", "default": "1104"},
            },
            "required": ["text"],
        },
        handler=lambda inputs, session: concept_matcher.ConceptMatcher(session).match(
            text=inputs["text"], scope=inputs.get("scope", "1104")
        ),
    ),
    "resolve_item": AgentTool(...),
    "lookup_rule_cards": AgentTool(...),
    "search_historical_decisions": AgentTool(...),
}
```

#### 3.4.2 ReAct 执行框架

```python
# app/services/react_agent.py

@dataclass
class AgentStep:
    step_num: int
    thought: str
    action: str | None      # tool name，None 表示 final answer
    action_input: dict | None
    observation: dict | None
    final_answer: dict | None


class ReActAgent:
    """ReAct 模式的可控 Agent。

    设计原则：
    - max_steps 硬上限（10 步），防止死循环
    - 每步必须 LLM 给出 Thought + Action 才能继续
    - 工具调用结果作为 observation 喂回下一轮
    - 最终通过 Action=None + final_answer 终止
    - 每步留痕到 trace，供前端可视化和 audit
    """

    def __init__(self, session: Session, max_steps: int = 10):
        self.session = session
        self.max_steps = max_steps
        self.trace: list[AgentStep] = []

    def run(self, task: str, context: dict) -> dict:
        """运行 ReAct 循环。返回 final_answer + trace。"""
        for step_num in range(1, self.max_steps + 1):
            prompt = self._build_react_prompt(task, context, self.trace)
            llm_response = complete_json([{"role": "user", "content": prompt}])

            step = self._parse_step(step_num, llm_response)
            self.trace.append(step)

            if step.final_answer:
                return {
                    "final_answer": step.final_answer,
                    "trace": [asdict(s) for s in self.trace],
                    "steps_used": step_num,
                }

            if step.action:
                tool = AGENT_TOOLS.get(step.action)
                if not tool:
                    # 未知工具，记录后继续
                    step.observation = {"error": f"unknown tool {step.action}"}
                else:
                    step.observation = tool.handler(step.action_input, self.session)

        # max_steps 超出仍未给 final_answer
        return {
            "final_answer": None,
            "trace": [asdict(s) for s in self.trace],
            "steps_used": self.max_steps,
            "error": "max_steps_exceeded",
        }
```

#### 3.4.3 集成方式：可插拔的新路径

**不替换** `document_profiler` 主路径，而是新增一个**可选**入口：

```python
# document_profiler.py
def generate_document_profile(
    document, context, session=None,
    use_agent: bool = False,  # ← 新增 flag
) -> Document1104ProfileDraft:
    if use_agent:
        return _generate_via_react_agent(document, context, session)
    # 原逻辑保留不动
    ...
```

前端 PortraitView 加一个按钮 "**🤖 用 Agent 模式分析**"（默认禁用，opt-in）。

### 3.5 前端 Agent 可视化

新视图 `AgentTraceView.vue`（或 PortraitView 抽屉）：

```
┌──────────────────────────────────────────────────────────────┐
│ 🤖 Agent 推理过程  ·  共 5 步                                  │
├──────────────────────────────────────────────────────────────┤
│ Step 1  💭 我需要先识别这段话涉及哪些业务概念                  │
│         🔧 调用 match_concept                                  │
│         ✅ 命中 3 个概念：同业融入余额 / 金融机构 / 最大百家     │
├──────────────────────────────────────────────────────────────┤
│ Step 2  💭 这些概念对应哪些具体报送项？                        │
│         🔧 调用 resolve_item("G24", "同业融入余额")            │
│         ✅ 命中 G24.MAIN.INTERBANK_BORROWING_BAL_TOP100         │
├──────────────────────────────────────────────────────────────┤
│ Step 3-4 ...                                                  │
├──────────────────────────────────────────────────────────────┤
│ Step 5  🎯 Final Answer                                        │
│         产出完整 change_signal                                 │
└──────────────────────────────────────────────────────────────┘

[暂停/接管/重新运行]
```

### 3.6 失败兜底

- LLM 调用失败：当前 step 标 error，继续下一步（不阻塞）
- 工具调用失败：observation = {"error": ...}，让 LLM 自己决定是否换工具
- max_steps=10 超出：标 max_steps_exceeded，返回 trace 给业务方人工接管
- 工具死循环（同一个工具调 5 次）：自动 break + 标 loop_detected

### 3.7 eval 锁住

`agent_react_e2e.json`：

```json
{
  "id": "agent_react_e2e",
  "description": "ReAct Agent 完整跑通：解读一段 G24 发文，能调通 4 个工具，最终产出 change_signal",
  "target": "react_agent",
  "inputs": {
    "task": "分析这段监管发文",
    "text": "调整G24同业融入余额统计口径，按金融机构类型分类"
  },
  "expectations": [
    { "kind": "must_contain", "spec": { "keyword": "match_concept" } },
    { "kind": "must_contain", "spec": { "keyword": "resolve_item" } },
    { "kind": "signal_count", "spec": { "min": 2, "max": 10 } }
  ]
}
```

### 3.8 可宣称话术

> ✅ "**ReAct (Reasoning + Acting) Agent 工作流**：LLM 在解读监管发文时**主动调用** 4 个工具
> （概念匹配 / 字段定位 / 规则查询 / 历史决策档案），每步推理过程**可审计、可暂停、可人工接管**。
> 这不是 AutoGPT 风格的全自主 Agent，是**金融场景的可控 Agent 模式**。"

不要宣称：
- ❌ "AutoGPT" / "全自主 Agent"
- ❌ "Multi-Agent 协作框架"
- ❌ "自研 Agent 框架"

### 3.9 验收标准

- [ ] 4 个 agent_tool 全部实现，签名清晰
- [ ] `ReActAgent.run()` 单元测试通过（mock LLM）
- [ ] max_steps / loop_detection / 工具失败 等兜底测试通过
- [ ] document_profiler 加 `use_agent` 参数，opt-in
- [ ] PortraitView 加 "🤖 Agent 模式" 按钮
- [ ] `AgentTraceView` 时间轴可视化
- [ ] eval case 通过
- [ ] audit_logs 留痕完整

---

## 4 · 模块 D · AI 工单执行规划（业务价值最高）

### 4.1 现状盘点 + 解决什么真问题

Codex Task 5 完成后，工单页面会从"3000 字 Markdown"变成"结构化任务卡"，
解决了"**每张工单内部清晰**"。

但**整体维度的导航问题没解决**：

```
业务方现状：
  10 个子单卡片在屏幕上
  ↓
  我先做哪一个？
  哪些是阻塞我做下一步的？
  哪些可以并行？
  哪些团队该先去敲门？
  最大风险在哪？
  ↓
  ❌ 没有答案，业务方迷茫
```

模块 D 让 LLM 扮演**项目经理**角色，把 N 个子单整合成可执行的"执行规划总结"。
**这是 AI 在业务价值最直白的一次体现**。

### 4.2 形态 — ReviewTicketView 顶部新增"🎯 AI 执行规划"卡片

视觉示例：

```
┌──────────────────────────────────────────────────────────────┐
│ 🎯 AI 执行规划                              [收起]            │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           │
│                                                                │
│ 📋 全局摘要                                                    │
│ 本次变更影响 G24 同业融入 + G31 投资业务两张报表，涉及        │
│ 数据治理 / 数据集市 / 数据质量 3 个团队的协作。               │
│ 预估完成时间：2-3 周。                                         │
│                                                                │
│ 📅 推荐执行顺序                                                │
│                                                                │
│   第 1 周（关键路径 · 这两个不完成下游做不了）                 │
│     □ [数据治理] 确认 G24 同业融入字段血缘  ⛔阻塞下游         │
│     □ [业务部] 确认拆放同业纳入统计口径    ⛔阻塞下游          │
│                                                                │
│   第 2 周（可并行）                                            │
│     □ [数据集市] 调整 ETL 加工逻辑                             │
│     □ [源系统] 评估是否需新增字段                              │
│     □ [数据质量] 新增跨表勾稽校验规则                          │
│                                                                │
│   第 3 周（收尾）                                              │
│     □ [测试] 回归用例覆盖                                      │
│     □ [报送管理] 归档 + 经验入库                               │
│                                                                │
│ ⚠️ 关键风险（共 2 条）                                         │
│                                                                │
│   🔴 高：1.8.4 "其他子项"删除涉及历史数据追溯，               │
│           可能需要重算 6 个月数据                             │
│   🟡 中：拆放同业为新增统计范围，源系统团队暂未确认是否        │
│           需新增字段，建议第 1 周完成与源系统对齐              │
│                                                                │
│ 🤝 跨团队协作建议                                              │
│ 数据治理与业务部需在第 1 周同步对齐口径（建议拉一个联合会议），│
│ 否则数据集市的 ETL 改造无法启动。                              │
│                                                                │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━           │
│ 📜 该规划由 AI 基于上述工单事实生成，依据可追溯（点击查看）    │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 输入数据

```python
ExecutionPlannerInput = {
    "document_summary": str,                  # 监管发文摘要（取 profile.evidence_text）
    "tables_affected": list[str],             # ["G24", "G31"]
    "impact_items": list[ReportingImpactDraft],  # 影响项清单
    "concept_hits": list[ConceptMatchHit],    # 命中的概念
    "parent_ticket": TicketDraftRead,         # 母单
    "child_tickets": list[TicketDraftRead],   # 全部子单（带 card 结构化字段）
    "historical_cases": list[dict] | None,    # 历史相似案例（W2 后真实化）
}
```

### 4.4 LLM Prompt 设计（防幻觉关键）

```python
SYSTEM_PROMPT = """
你是银行数据治理项目经理，需要把以下监管报送变更工单整合成一份**面向业务方的执行规划**。

【严格约束】
1. 你只能基于下方提供的工单事实做规划，**不允许虚构**风险点或团队
2. 每个推荐的执行项必须 reference 一个具体子单 ID
3. 风险点必须基于工单的 blockers 字段或影响项内容，不能凭空推断
4. 团队推荐只能从以下 7 个责任系统选：
   REG_REPORTING_SYSTEM / DATA_GOVERNANCE_PLATFORM / DATA_MART_ETL /
   SOURCE_SYSTEM / DATA_QUALITY_PLATFORM / TEST_ACCEPTANCE / KNOWLEDGE_ARCHIVE
5. 工期预估必须给区间（如"2-3 周"），不允许给确定数字
6. 全文不超过 500 字
7. 输出必须是合法 JSON，符合下方 schema
"""

USER_PROMPT = f"""
【监管变更背景】
{document_summary}

【影响报表】{tables_affected}
【影响指标数】{len(impact_items)}
【关联概念数】{len(concept_hits)}

【已拆分的子单】
{json.dumps(child_tickets, ensure_ascii=False, indent=2)}

【历史相似变更案例（参考用）】
{historical_cases or "（暂无历史案例）"}

请生成 JSON 格式的执行规划：
{{
  "executive_summary": "2-3 句话全局摘要",
  "estimated_duration": "如 '2-3 周'",
  "execution_phases": [
    {{
      "phase_name": "第 1 周（关键路径）",
      "tasks": [
        {{
          "team": "DATA_GOVERNANCE_PLATFORM",
          "team_zh": "数据治理团队",
          "action": "确认 G24 同业融入字段血缘",
          "ticket_id": 123,
          "is_blocker": true,
          "blocker_reason": "下游 ETL 改造依赖字段映射"
        }}
      ]
    }}
  ],
  "critical_risks": [
    {{
      "severity": "HIGH",
      "description": "...",
      "ticket_id_ref": 124,
      "mitigation": "建议..."
    }}
  ],
  "team_coordination": "1-2 句协作建议"
}}
"""
```

### 4.5 输出 schema

```python
class ExecutionTask(BaseModel):
    team: str                        # ResponsibleSystem 枚举
    team_zh: str
    action: str
    ticket_id: int
    is_blocker: bool
    blocker_reason: str = ""

class ExecutionPhase(BaseModel):
    phase_name: str                  # "第 1 周（关键路径）"
    tasks: list[ExecutionTask]

class CriticalRisk(BaseModel):
    severity: str                    # HIGH / MEDIUM / LOW
    description: str
    ticket_id_ref: int | None        # 引用哪条子单
    mitigation: str

class ExecutionPlan(BaseModel):
    executive_summary: str
    estimated_duration: str
    execution_phases: list[ExecutionPhase]
    critical_risks: list[CriticalRisk]
    team_coordination: str
    # 元数据
    generated_at: datetime
    generated_by: str                # llm model name
    confidence: float                # 由核验逻辑给出
```

### 4.6 持久化

新表 `reg_task_execution_plan`：

```sql
CREATE TABLE reg_task_execution_plan (
  id              BIGINT PK,
  task_id         BIGINT UNIQUE,           -- 一个 task 一份最新规划
  plan_content    JSON,                    -- ExecutionPlan 完整序列化
  generated_at    DATETIME,
  generated_by    VARCHAR(64),
  confidence      DECIMAL(3,2),
  feedback_thumbs INT DEFAULT 0,
  status          ENUM('VALID', 'STALE', 'INVALID'),  -- 工单改了标 STALE
  created_at      DATETIME,
  updated_at      DATETIME
);
```

工单更新时触发：`task_execution_plan.status = STALE`，下次进页面提示"工单已变更，规划可能过期，重新生成？"

### 4.7 API 设计

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/tasks/{task_id}/execution-plan` | POST | 生成新规划（覆盖旧的） |
| `/api/tasks/{task_id}/execution-plan` | GET | 拉最近一次生成的规划 |
| `/api/tasks/{task_id}/execution-plan/feedback` | PATCH | 业务方点赞/拍砖反馈 |

### 4.8 防幻觉机制（关键）

| 防御层 | 做法 |
|---|---|
| **Prompt 约束** | 强制 reference ticket_id；team 限定枚举；不允许虚构 |
| **输出核验** | 解析 JSON 后逐项核：team 在枚举内 / ticket_id 存在 / severity 合规 |
| **失败兜底** | 任一核验失败 → 不展示 AI 规划，UI 回退"按子单创建顺序展示" |
| **可追溯展示** | 卡片底部 "📜 依据可追溯" 链接展开所引用的子单原文 |
| **业务方反馈** | UI 上每条规划项可 👍/👎 反馈，进 audit_logs |

### 4.9 前端设计

新组件 `ExecutionPlanCard.vue`：

- 集成到 `ReviewTicketView.vue` 顶部（Codex Task 5 完成后整合）
- 折叠式卡片，默认展开
- 包含：摘要 + 执行阶段时间轴 + 风险预警表 + 协作建议
- 每个 task 是 chip 形式，点击跳转到对应子单详情
- 风险条目按 severity 颜色区分（🔴/🟡/🟢）
- 底部"📜 依据可追溯"展开 AI 引用的子单原文片段

### 4.10 eval 锁住

新增 case `agent_execution_planner.json`：

```json
{
  "id": "agent_execution_planner",
  "description": "LLM 生成的执行规划必须 reference 真实存在的子单 ID，不发明团队",
  "target": "execution_planner",
  "inputs": { "task_id": 123 },
  "expectations": [
    {
      "kind": "must_contain",
      "spec": { "keyword": "DATA_GOVERNANCE_PLATFORM" },
      "reason": "G24 字段映射子单必须分到数据治理团队"
    },
    {
      "kind": "all_signals_match",
      "spec": { "field": "team_in_enum", "in": ["true"] },
      "reason": "所有 team 必须在 ResponsibleSystem 枚举内"
    },
    {
      "kind": "all_signals_match",
      "spec": { "field": "ticket_id_valid", "in": ["true"] },
      "reason": "所有 ticket_id 必须真实存在"
    }
  ]
}
```

### 4.11 可宣称话术

> ✅ "**AI 工单执行规划**：LLM 扮演项目经理角色，把 N 个结构化子单整合成
> 可执行的'执行顺序 + 关键路径 + 风险预警 + 跨团队协作建议'。
> 输出严格基于工单事实，不发明风险，每项可追溯到具体子单 ID。"

不要宣称：

- ❌ "AI 自动决策" — 是 AI 建议，业务方决策
- ❌ "完全自动化项目管理" — 我们是辅助不是替代
- ❌ "自研项目管理 AI" — 是 LLM prompted output

### 4.12 验收标准

- [ ] `ticket_execution_planner.py` 实现 + unit test（mock LLM）
- [ ] `reg_task_execution_plan` 表 migration 通过
- [ ] 3 个 API 端点（POST/GET/PATCH）实现并测试
- [ ] 输出核验逻辑：team 枚举 / ticket_id 存在 / severity 合规
- [ ] 失败兜底：核验失败时不展示，回退按时间排序
- [ ] `ExecutionPlanCard.vue` 渲染正确
- [ ] 工单更新触发 status=STALE
- [ ] eval case 通过
- [ ] audit_logs 完整留痕（生成 + 反馈）

---

## 5 · 整合与跨切关注

### 5.1 集成 timeline（推荐 D 优先）

**业务价值优先排序（推荐）**：

```
Day 1-3   ─  模块 D 工单执行规划 ⭐ 业务价值最高，先做
Day 4-5   ─  模块 A KG 可视化（演示视觉冲击）
Day 6-7   ─  模块 B Self-Correcting Loop（真解决幻觉）
Day 8-10  ─  模块 C ReAct Tool-Using Agent
```

合计 **10 个工作日**。

**为什么 D 优先**：
- D 直接解决业务方"拿到工单不知道先做哪个"的核心痛点
- 跟 Codex Task 5 完美衔接（Task 5 结构化工单 → D 加 LLM 总结）
- 工作量小（3 天）+ 演示效果直白（评委一眼能看出"AI 真有用"）
- 不依赖其他模块，独立性强

**保守备选排序**：

```
Day 1-2   ─  模块 A KG 可视化（先把数据展示做好）
Day 3-4   ─  模块 B Self-Correcting Loop
Day 5-7   ─  模块 C ReAct Tool-Using Agent
Day 8-10  ─  模块 D 工单执行规划
```

### 5.2 跟 Codex 那边的协作边界

| Codex 在做 | 我们这里在做 | 冲突点 | 缓解 |
|---|---|---|---|
| Task 5 ReviewTicketView 前端 | **模块 D 前端 ExecutionPlanCard** | 都改 ReviewTicketView | **D 加在顶部，Codex Task 5 改的是工单列表/卡片，垂直方向无冲突** |
| Task 5 ReviewTicketView 前端 | 模块 A KG 前端 / 模块 C AgentTraceView | 都改前端 | 不同 view，零冲突 |
| Task 5 类型 ts | 模块 A ConceptGraph / 模块 D ExecutionPlan 类型 | 改 types/api.ts | 各加各的 interface，无冲突 |
| Task 6 端到端回归 | 模块 B/C/D 加新 case | 都跑 eval | 我们多加几个 case，Codex 顺带验 |

### 5.3 不破坏存量的硬约束

| 既有功能 | 是否受影响 |
|---|---|
| 上传 → 画像 → 字段定位 → 影响分析 → 工单生成 | **不动** |
| `/api/concepts/match` | 不动；保留长别名优先 + 多路召回 |
| `document_profiler.generate_document_profile()` 默认行为 | 不动；`use_agent=False` 是默认 |
| `RegConcept` / `RegConceptRelation` 等表 schema | 不动 |
| `TicketDraft` 表 schema | 不动；模块 D 新建独立 `reg_task_execution_plan` 表 |
| 既有 19 个 eval case | 不动，新增 case 不破坏老的 |

### 5.4 风险与缓解

| 风险 | 缓解 |
|---|---|
| Agent 调 LLM 次数 5-10x，成本 / 延迟上升 | max_steps=10；工具调用结果缓存（同输入复用）；现网先 opt-in，证明价值后再默认启用 |
| Agent 死循环 / 跑偏 | max_steps 硬上限 + loop_detection + 每步审计 |
| 评委追问 "你这 Agent 多智能" | 诚实答："局部 Agent 模式，非全自主，重在可控可审计" |
| KG 关系太稀疏（23 个 concept 才几条关系） | 立项后 LLM 抽取 + 业务方审核扩到 100+ concept / 100+ relation |
| cytoscape.js 引入打包体积涨 | 估算 +200KB gzip；可接受。或用 d3-force 替代（更轻量） |
| **模块 D 执行规划 LLM 发明风险点** | Prompt 强约束 + 输出 JSON 核验 + 失败兜底回退到"按时间排序" |
| **模块 D 工单变更后规划过期** | 工单更新触发 `status=STALE` + UI 提示"规划已过期" |

### 5.5 跟既有"诚实清单"的关系

参照 `feasibility-audit.md`：

| audit 里的风险 | 本设计如何缓解 |
|---|---|
| #1 三路融合实际没合并器 | **不解决这个**（这是另一条路径） |
| #2 防幻觉没量化没视觉化 | ✅ 模块 B Self-Correcting Loop **真解决**：自动重试 + 三档徽章 + audit_logs |
| #3 概念库治理流程缺失 | ⚠️ 不解决（流程问题，需文档化） |
| #4 落格率 6/10 没路线 | ⚠️ 不解决 |
| #5 概念辐射映射没人背书 | ⚠️ 不解决 |
| #6 拆单规则没业务方验证 | ⚠️ 不解决（但 **模块 D 让"工单价值不够"的痛点被部分对冲** — AI 帮业务方导航，弱化了对子单本身合理性的依赖） |
| #7 eval 自评是否过松 | ✅ 模块 A/B/C/D 各自加 case，提升 eval 严格度 |

**本设计聚焦于把"AI 能力的展示性 + 可控性 + 业务可执行性"三点做强**，不试图解决所有 audit 风险。

---

## 6 · 演示故事整合

### 6.1 demo 期望体验路径

**5 分钟 demo 脚本（含本设计四个模块）**：

```
[0:00 - 1:00]  开场 + 业务问题  
  - 现状：监管发文落地 3 天，AI 辅助压到 5 分钟
  - 关键约束：AI 必须可控可审计可解释

[1:00 - 1:30]  概念库 + 知识图谱   ← 模块 A
  - 进入 LibraryView 知识图谱 Tab
  - 展示 23 个 concept 的关系网络
  - 点击 "同业融入余额" 节点 → 详情抽屉显示 alias / 辐射的报送项
  - 关键卖点："**业务知识图谱化**，AI 召回有图谱支撑"

[1:30 - 3:00]  上传发文 + Agent 模式分析   ← 模块 C
  - 上传 15 号公告
  - 点击 "🤖 Agent 模式分析"
  - AgentTraceView 时间轴动画展示 LLM 分 5 步推理
  - 每步显示：思考 + 工具调用 + 命中结果
  - 关键卖点："**LLM 主动调用工具，推理过程透明可审计**"

[3:00 - 3:30]  Self-Correcting 自纠错   ← 模块 B
  - PortraitView 显示 10 个 signal
  - 8 个 ✅ verified / 1 个 🔄 corrected / 1 个 ⚠️ quarantined
  - 点击 corrected 标记 → 显示"原本未锚定，自纠错 Agent 经 1 次重试找到原文"
  - 关键卖点："**AI 不发明事实，发明了被自动标记**"

[3:30 - 4:00]  字段定位 + 工单生成（现有）
  - LineageView 概念命中 + 字段血缘
  - 工单结构化任务卡（Codex Task 5）

[4:00 - 4:45]  AI 工单执行规划   ← 模块 D ⭐ 业务价值峰值
  - 工单页面顶部展开 "🎯 AI 执行规划" 卡片
  - 展示执行顺序：第 1 周关键路径 / 第 2 周并行 / 第 3 周收尾
  - 展示 2 条风险预警（标红/黄等级）+ 跨团队协作建议
  - 点击 "📜 依据可追溯" 展开 AI 引用的具体子单原文
  - 关键卖点："**AI 不只是抽信息，AI 像项目经理一样把工单整合成可执行计划**"

[4:45 - 5:00]  收尾
  - 工程严谨证据：149 测试 / 21 eval case / git history
  - 一句话：本项目不创新 AI 模型，**创新的是金融监管场景下 AI 落地的工程方法论**
```

### 6.2 答辩关键话术（与 feasibility-audit §13 对齐）

新增 4 条罐头话术：

| 追问 | 30 秒话术 |
|---|---|
| "你这个 KG 怎么做的" | 基于 7 种语义关系（INCLUDES/EXCLUDES/SUBSET_OF 等）建模概念网络。当前 23 个种子概念，演示概念辐射可视化。立项后扩到 100+ 概念 + LLM 抽取关系 + 业务方审核 |
| "Agent 多智能" | 是 ReAct 模式的**局部 Agent**，非全自主。LLM 主动调 4 个工具（概念匹配 / 字段定位 / 规则查询 / 历史决策），每步可暂停可接管可审计。**银行高合规场景下的可控 Agent 模式**，不是 AutoGPT |
| "幻觉怎么自动纠错" | Self-Correcting Loop：所有 LLM 输出做原文锚定核验，未通过的启动二次纠错（最多 2 次重试），仍未锚定的隔离到人工审核队列。**AI 不发明事实，发明了被自动标记**。审计 trail 完整 |
| "**AI 真能帮业务方做事吗**" | **模块 D 工单执行规划**：LLM 扮演项目经理角色，把 10 个子单整合成"第 1 周关键路径 / 第 2 周并行 / 第 3 周收尾"的可执行规划，标红风险点，给跨团队协作建议。每项建议可追溯到具体子单。**这不是 demo 表演，业务方真用得上** |

---

## 7 · 实施 checklist

### 7.1 后端

**模块 D（推荐先做）**
- [ ] `app/services/ticket_execution_planner.py` 新建（含输出 JSON 核验）
- [ ] `app/models/db_models.py` 加 `RegTaskExecutionPlan` 表
- [ ] `app/models/schemas.py` 加 ExecutionPlan / ExecutionPhase / ExecutionTask / CriticalRisk 类型
- [ ] `app/api/routes_tasks.py` 加 POST/GET `/api/tasks/{id}/execution-plan` + PATCH /feedback
- [ ] 工单更新时触发 `execution_plan.status = STALE`
- [ ] audit_logs 写入生成 + 反馈动作

**模块 A KG**
- [ ] `app/services/concept_graph_service.py` 新建
- [ ] `app/api/routes_concepts.py` 加 `/api/concepts/graph` endpoint

**模块 B Self-Correcting**
- [ ] `app/services/self_correcting_agent.py` 新建
- [ ] `app/services/document_profiler.py` 集成 Self-Correcting Loop

**模块 C ReAct Agent**
- [ ] `app/services/agent_tools.py` 4 个工具实现
- [ ] `app/services/react_agent.py` 新建
- [ ] `app/services/document_profiler.py` 加 `use_agent` 参数
- [ ] `app/api/routes_documents.py` opt-in 传 use_agent
- [ ] audit_logs 写入所有 Agent 动作

### 7.2 前端

**模块 D（推荐先做）**
- [ ] `frontend/src/components/ExecutionPlanCard.vue` 新建（折叠卡片）
- [ ] `frontend/src/views/ReviewTicketView.vue` 顶部集成（避开 Codex Task 5 改动区）
- [ ] `frontend/src/types/api.ts` 加 ExecutionPlan / ExecutionTask / CriticalRisk 类型
- [ ] `frontend/src/api/client.ts` 加 fetchExecutionPlan / generateExecutionPlan / sendFeedback 接口

**模块 A KG**
- [ ] 安装 cytoscape.js（pnpm add cytoscape）
- [ ] `frontend/src/views/ConceptGraphView.vue` 新建
- [ ] `frontend/src/views/LibraryView.vue` 加图谱 Tab

**模块 B Self-Correcting**
- [ ] `frontend/src/views/PortraitView.vue` 加 verified / corrected / quarantined 三档徽章

**模块 C ReAct Agent**
- [ ] `frontend/src/views/PortraitView.vue` 加 "🤖 Agent 模式" 按钮
- [ ] `frontend/src/views/AgentTraceView.vue` 新建（或抽屉形态）
- [ ] `frontend/src/types/api.ts` 加 ConceptGraph / AgentStep / AgentTrace 类型
- [ ] `frontend/src/api/client.ts` 加 fetchConceptGraph / runAgent 接口

### 7.3 测试

- [ ] `tests/eval/targets.py` 加 execution_planner + concept_graph + react_agent + self_correcting target
- [ ] `tests/eval/cases/agent_execution_planner.json`
- [ ] `tests/eval/cases/concept_graph_traversal.json`
- [ ] `tests/eval/cases/agent_self_correcting.json`
- [ ] `tests/eval/cases/agent_react_e2e.json`
- [ ] `tests/test_ticket_execution_planner.py` unit test（mock LLM + 核验逻辑）
- [ ] `tests/test_concept_graph_service.py` unit test
- [ ] `tests/test_self_correcting_agent.py` unit test（mock LLM）
- [ ] `tests/test_react_agent.py` unit test（mock LLM + tools）
- [ ] 全套 pytest 通过

### 7.4 文档

- [ ] `docs/README.md` 索引加本设计文档
- [ ] `feasibility-audit.md` 补充：风险 #2 已通过本设计缓解

---

## 8 · 决议待定项（需用户确认）

提交本设计前请审查：

1. **实施顺序**：先做 D（业务价值最高）→ A → B → C？还是按 A → B → C → D 顺序？**推荐前者**
2. **模块 D Prompt 是否走 LLM mock**：现网必须真调 LLM；eval / unit test 用 mock；现场 demo 是否需要预录 LLM 响应作为兜底？
3. **KG 可视化库选型**：cytoscape.js（推荐）vs d3-force vs vis.js？
4. **Agent 是否默认启用**：当前设计是 opt-in（默认禁用，业务方点按钮启用）。是否应该 demo 时默认启用以提升演示效果？
5. **Self-Correcting max_retries**：当前设计 2 次，是否合适？
6. **ReAct max_steps**：当前设计 10 步，是否合适？
7. **是否需要"接管"按钮**：用户在 AgentTraceView 看到某步走偏，能不能介入修改 prompt 重新跑？这会大幅增加复杂度
8. **跟 cytoscape.js 同时引入打包体积涨 200KB**，是否接受？
9. **模块 D 工单变更后规划过期处理**：标 STALE 但不自动重生成，让业务方手动点"重新生成"？还是后台静默重生？

---

## 修订记录

- 2026-05-27 初版（Claude 起草，含 A/B/C 三模块）
- 2026-05-27 v2（加入模块 D · AI 工单执行规划，调整 timeline 推荐 D 优先）
