# 银行创新奖一期 Demo · 改进 TODO

> 本文档汇总当前项目距离参加银行创新奖一期 demo 的关键缺口与改进任务，按优先级分档。
> 评估基准：评委 5-10 分钟现场观看，需要在「看懂、相信、记住」三件事上都立得住。

---

## 总评

| 维度 | 评分 | 说明 |
|---|---|---|
| 设计文档 | 8/10 | 通用模型 + 1104 落脚点的抽象正确 |
| 模型层 | 7/10 | 22 张表覆盖主要业务对象 |
| 创新点（防幻觉/三路融合/Excel diff） | 7/10 | 代码已实现，但前端没讲透 |
| 业务素材完整度 | 5/10 | 种子数据太薄，G24 一条故事讲完就没了 |
| AI 真正介入深度 | 5/10 | LLM 只参与画像，影响分析和工单是模板 |
| UI 演示效果 | 5/10 | 没有血缘可视化、没有 diff 视图 |
| 闭环回写 | 3/10 | 复核回流链路完全缺失 |
| 可视化创新表达 | 2/10 | 基本是表格 |

**距离 demo 上场约 5-7 天集中开发**。底子做对了，特别是防幻觉与三路信号源两块如果显性化，足以撑住差异化定位。

---

## 关键缺口诊断（六个致命点）

### 1. AI 含金量在关键环节掉链子
- `analyze_reporting_impacts`：所有 impact 写死 `impact_type=INDICATOR_SCOPE`，`impact_reason` 是 f-string 模板
- `generate_reporting_ticket_markdown`：纯 Markdown 模板字符串
- **LLM 只参与了 portrait（画像），影响分析和工单都是查表/拼字符串**
- 评委翻代码即穿

### 2. 闭环没回写
- 文档承诺的 `PATCH /api/reporting/impact-items/{id}/review` 没实现
- "经验沉淀"目前是 PPT 概念
- DashboardView "已归档 18 / 22 条" 是 hardcode

### 3. 血缘可视化为零
- LineageView 是「目录树+字段表格」纯文字 UI，**没有任何节点连线图**
- 这是创新奖 ROI 最高的一项空白

### 4. 种子数据太薄
- 5 张表 6 个指标 13 条血缘，G24 一条故事讲完就没下文
- G21/G25/G27 平均不到 1.5 条边
- 文档承诺的 ETL/校验/码值维表全部缺失（7 段血缘缩水成 3 段）

### 5. 工单 SQL 是前端硬编码
- `ReviewTicketView.vue:120-145` 写死 SELECT G24/G21/G25 模板
- 翻代码一眼看穿

### 6. 现场断网即翻车
- `.env` 接的是第三方网关 `api.ikuncode.cc`
- `settings.REG_ASSISTANT_MOCK_AI=true` 开关 `llm_client` 没尊重
- key 失效/断网就 502

---

## P0 · 必须修才能 demo（< 3 天）

| # | 任务 | 文件/模块 | 工作量 |
|---|---|---|---|
| P0-1 | 准备 G24 完整故事素材包：测试公告 + G24 新旧表样 + 新旧填报说明 + 修订对照表，做"一键加载样例"按钮 | `backend/data/`、`DocumentsView.vue` 加按钮 | 0.5 天 |
| P0-2 | ReviewTicketView 用后端 `ticket.content` 渲染，去掉前端 `defaultTicketContent` 兜底 SQL 模板 | `ReviewTicketView.vue:120-145` | 0.5 天 |
| P0-3 | DashboardView KPI 数字改成动态读取，或 demo 前 seed 坐实 | `DashboardView.vue` | 0.5 天 |
| P0-4 | `llm_client` 尊重 `REG_ASSISTANT_MOCK_AI`，准备本地预录响应作为断网兜底 | `app/services/llm_client.py` | 0.5 天 |
| P0-5 | PortraitView 「幻觉预警条 + evidence_verified」做成显眼看点（加文案、加现场讲解锚点） | `PortraitView.vue` | 0.5 天 |
| P0-6 | 修 `_build_workflow_steps` 步骤名（clauses/impact/rule_cards/ticket）与前端 sidebar（upload/portrait/lineage/impact/ticket）对齐 | `routes_tasks.py:522-557` | 0.5 天 |
| P0-7 | 整理 demo 演讲稿与 5 分钟走查脚本 | `docs/demo-script.md` 新建 | 0.5 天 |

## P1 · 强烈建议补（3-7 天）

| # | 任务 | 文件/模块 | 工作量 |
|---|---|---|---|
| P1-1 | **LineageView 加 SVG 血缘图组件**（4 列节点：指标→报送字段→源字段→维度，点击节点高亮上下游） | `LineageView.vue` + 新建 `components/LineageGraph.vue` | 2 天 |
| P1-2 | **三路信号源融合做成 demo 开场主线**（修订表/Excel diff/填报说明 LLM 各产出几条变更，三路漏斗 + 优先级动画 + 命中/冲突标记） | `DocumentsView.vue` 升级 + 新建 `components/TripletFunnel.vue` | 2 天 |
| P1-3 | 给 G21/G25/G27 各补 3-4 条血缘边，让 demo 不止讲一个 G24 | `reporting_seed.py` | 0.5 天 |
| P1-4 | 实现 `PATCH /api/reporting/impact-items/{id}/review`，ImpactView 每行加「采纳/退回/挂起」 | `routes_reporting.py` + `ImpactView.vue` | 1 天 |
| P1-5 | ImpactView 加影响类型分布饼图 + 风险等级条形图 | `ImpactView.vue` | 0.5 天 |
| P1-6 | ReviewTicketView 加左右栏「新旧口径 diff」 | `ReviewTicketView.vue` | 0.5 天 |
| P1-7 | 把 `impact_type` 按 8 种类型真正区分（报表结构/口径/机构范围/源字段/加工逻辑/校验/补录/历史），让影响分析显得"智能" | `reporting_impact_analyzer.py` | 1 天 |
| P1-8 | 工单生成接入 LLM（基于 impact_items + signals 生成"待确认问题/验收标准/SQL 草稿"） | `reporting_ticket_generator.py` | 1 天 |

## P2 · 锦上添花（留二期或时间富余时做）

- LLM 流式输出 + 打字机效果，营造"AI 正在思考"画面
- 历史案例相似检索 TopN（mock 5-10 条历史工单即可演示）
- 桑基图全报送体系跨表影响图
- 权限模拟（业务/开发/合规 3 个角色 mock 登录）
- LibraryView、CatalogView 两个占位页补齐到原型完成度
- 把残留的旧主线 `routes_rule_library.py` 下线或归档
- 接 EAST/一表通占位 demo（页面级 stub），呼应"通用框架"叙事
- 知识资产沉淀回写：人工复核后 lineage `review_status=CONFIRMED`，规则资产页累积曲线

---

## Demo 主叙事建议（5 分钟版本）

**主线 A：三路融合发现变更**（30 秒～1 分 30 秒）
- 上传：监管公告 + 新表样 + 新填报说明 + 修订对照表
- 三路漏斗动画：修订表 8 条 / Excel diff 5 条 / LLM 7 条 → 去重合并 → 11 条变更
- 强调"AI 不是唯一信号源、人工填报对照表优先级最高"——这是项目的工程严谨性

**主线 B：防幻觉的可复核 AI**（1 分 30 秒～2 分 30 秒）
- PortraitView 展示 LLM 抽出的变更信号
- 高亮 evidence_verified=true 的"原文滑窗已核对"绿牌
- 展示一条 evidence_verified=false 的黄牌示例 → "AI 不发明事实"

**主线 C：血缘穿透定位影响**（2 分 30 秒～4 分钟）
- LineageView 血缘图：指标 G24.row5.col_C → 报送字段 unsettled_exposure_amt → 源字段 interbank_deal.contract_amt + counterparty.country_code
- 点击节点高亮下游所有报表（一个源字段改了影响 G24 + G21 两张表）
- ImpactView 影响类型分布饼图 → 这次变更主要是"指标口径调整 + 机构范围调整"

**主线 D：可复核工单 + 经验沉淀**（4 分钟～5 分钟）
- 工单详情：LLM 生成的待确认问题、验收标准、SQL 草稿
- 「采纳/退回」按钮点击 → lineage.review_status=CONFIRMED → Dashboard 已沉淀经验数字 +1
- 收尾："AI 把人工 3 天的解读工作压到 5 分钟，但最终决策权留给业务"

---

## 风险清单

- [ ] MySQL demo 机环境：本地 MySQL `reg_user / reg_pass_123 / reg_reporting` 要先起好
- [ ] LLM 网关 `api.ikuncode.cc` 现场可能不稳，必须有 mock 兜底
- [ ] G24 demo 数据要在 seed 后立即可用，避免每次现场都 reset 数据库
- [ ] 浏览器：建议用 Chrome 最新版，SVG 血缘图要测过缩放与触控板手势
- [ ] 准备一份"出 bug 时的 PlanB 截图剧本"，万一现场跑挂可以演示截图版

---

## 里程碑

- **D-7**：P0 全部完成，主流程能跑通且断网不挂
- **D-5**：P1-1（血缘图）+ P1-2（三路漏斗）原型可用
- **D-3**：P1-4（复核回写）+ P1-7（影响类型分类）完成
- **D-2**：全流程联调 + 走查脚本
- **D-1**：现场 dry run x 2，准备 PlanB
- **D-0**：demo
