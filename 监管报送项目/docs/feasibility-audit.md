# 立项可信度自评：监管报送变更治理项目

> 创建日期：2026-05-27
> 目的：把每个核心功能从输入到输出的逻辑链路打磨严密，确保经得起领导追问
> 用法：先列追问 → 留答案空白 → 我和 Claude 一起讨论填写
> 留白即薄弱点 — 答不出来的就是真要补的

## 0 · 总览

### 0.1 项目核心一句话

把监管发文变更要求，自动定位到具体报送对象、报送项、字段血缘和源系统，
生成可复核的影响分析和分类型工单草稿，并将人工确认经验沉淀为可复用知识资产。

### 0.2 当前实现进度（commit / 测试覆盖）

| 功能模块 | 实现进度 | 测试覆盖 | 评级 |
|---|---|---|---|
| 文档上传 + 解析（.doc/.docx/.pdf/.xls/zip） | 主路径已通 | 多个 unit test | 🟢 |
| 文档画像 + LLM 变更识别 | 主路径已通 + 防幻觉锚定 | unit + eval | 🟡 |
| 三路融合（修订表/Excel diff/LLM） | 三路独立实现，**未真融合** | 各路有 test | 🟡 |
| 字段定位 + 血缘 + 概念命中 | 已通 + 今天刚清晰分层 | unit + eval | 🟢 |
| 概念库 + 多路 match（alias/definition/embedding） | 已通 | 19 eval case | 🟢 |
| 规则卡片 L1/L2/L3 | L1 已有，L2/L3 仅 schema | unit | 🟡 |
| 影响分析 | 已通，但 impact_type 单一 | unit | 🟡 |
| 工单生成（结构化卡片 + 触发器 + 质量评分） | Codex Task 4 已合，Task 5 进行中 | unit | 🟡 |
| 决策档案（W2 stub） | 仅接口骨架，无真数据 | — | 🔴 |
| eval framework | 19/19 全过 | 自身即测试 | 🟢 |

### 0.3 风险分级（高→低）

| 等级 | 问题 | 涉及模块 |
|---|---|---|
| 🔴 高 | #3 概念库治理流程完全缺失 | 概念库 |
| 🔴 高 | #5 概念辐射映射没人背书 | 概念库 + 影响分析 |
| 🔴 高 | 真实银行 lineage 数据怎么来 | 字段定位 |
| 🟡 中 | #1 "三路融合"实际没合并器 | 三路融合 |
| 🟡 中 | #2 防幻觉没量化没视觉 | 文档画像 |
| 🟡 中 | #4 落格率 6/10 没路线 | item_resolver |
| 🟡 中 | #6 拆单规则没业务方验证 | 工单生成 |
| 🟢 低 | #7 eval 自评标准是否过松 | eval framework |
| 🟢 低 | mock_ai 兜底真生效吗 | 文档画像 / LLM 全链路 |

---

## 1 · 文档上传 + 解析

### 1.1 我们做了什么

- 支持 .docx / .doc（LibreOffice 转换）/ .pdf / .xls / 三联 zip 包
- `document_parser.py` 主入口，`doc_parser.py` / `excel_parser.py` 处理具体格式
- 解析结果存 `reg_documents.parsed_text`
- 解析质量分级（HIGH/MEDIUM/LOW/FAILED）

### 1.2 追问清单

**技术**

- Q1 真实银行发文都什么格式？我们覆盖 90% 还是 60%？
- Q2 .doc 文件靠 LibreOffice subprocess 转 txt，CI 环境 / 生产环境怎么部署？
- Q3 大文件（50+ 页 PDF / 多 sheet xls）解析多久？现在有没有性能基准？
- Q4 OCR 处理过吗？扫描版 PDF 我们能不能处理？
- Q5 解析失败时降级到什么？有没有人工兜底通道？
- Q6 同一发文上传两次会重复跑流程吗？文档去重机制？

**业务**

- Q7 真实监管发文里附件多种格式混合（PDF 公告 + Word 填报说明 + Excel 修订表），我们的三联 zip 设计真覆盖业务需要吗？
- Q8 监管发文有时是"补充通知 + 引用历史发文"，我们怎么处理跨发文上下文？

**治理 / 安全**

- Q9 上传的文件存哪？银行数据安全要求是什么？等保几级？
- Q10 上传后能不能删除？保留多久？合规法务要求？
- Q11 病毒扫描？文件大小限制？防恶意上传？

### 1.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 真实银行发文格式覆盖率 | 已覆盖 docx / doc / pdf / xls / zip 三联包 5 种，估算覆盖 **80-85%** 的真实场景；漏的是图片型扫描件 PDF | OCR 不是 P0，立项后接 PaddleOCR 即可 |
| Q2 .doc 用 LibreOffice 部署 | 本地 dev 依赖 `soffice` 命令；生产 Docker 镜像需预装 LibreOffice | 立项后 Dockerfile 加 `apt install libreoffice-core` + healthcheck；备选用 antiword 纯 Python 解析 |
| Q3 大文件性能基准 | **没有基准** | 立项后写 `scripts/benchmark_parse.py` 跑 10/30/50/100 页 PDF，输出 p50/p95 时间 |
| Q4 OCR | 没做。真实监管发文 95% 是电子稿，扫描件少 | 立项后挂 PaddleOCR adapter；OCR 失败走人工兜底通道 |
| Q5 解析失败兜底 | `parse_status=FAILED`，前端显示错误。**无人工通道** | 立项后加"手工录入正文"入口；OPS 兜底队列 |
| Q6 文档去重 | 没做，同一份发文上传两次会重复跑 | 加 `content_hash`（sha256 前 1MB）+ 去重提示 |
| Q7 三联 zip 真覆盖业务？ | 当前覆盖：纯公告 / 公告+表样+修订表 zip / 单文件路径都支持。漏掉的是"发文+多个 word 附件"混合包 | 立项后加 multi-file zip 处理（已有 zip_scanner，需扩展） |
| Q8 跨发文上下文（引用历史发文） | **没做**。监管发文经常写"按 X 号文执行" | 立项后加 `document_reference` 字段建发文引用图，但 P0 不做 |
| Q9 数据安全 / 等保 | 当前本地 disk，**未加密**；不达任何等保等级 | **真上银行必须做**：加密存储 + 内部对象存储 + 访问审计；立项书必须明确成本 |
| Q10 保留期 / 合规 | **未设计**保留策略 | 监管要求一般 5-10 年；立项后加 `retention_policy` 字段，定期清理过期文档 |
| Q11 病毒扫描 / 大小限制 | 当前未做 | 立项后接 ClamAV + 50MB 上限；这不是难点是补漏 |

**整体定位**：解析侧基本是 PoC 可用 + 立项后补 5-6 个工程性短板。**没有架构性风险**。



---

## 2 · 文档画像 + LLM 变更识别

### 2.1 我们做了什么

- `document_profiler.generate_document_profile()` 主入口
- 调 LLM 抽 `change_signals`（table_code / indicator_hint / change_type / evidence_text）
- 原文核验：`_ground_signal()` 检查 evidence_text 是否真在原文中（防幻觉）
- 路径分流：FULL_ANALYSIS / LIGHTWEIGHT_ARCHIVE / MANUAL_REVIEW / SKIP
- 集成 `item_resolver` 补 matched_item_code 落格

### 2.2 追问清单

**技术**

- Q1 用的是哪个 LLM？模型升级了怎么办？prompt 怎么管理版本？
- Q2 LLM 失败 / 超时 / 限流时降级到什么？现网 mock_ai 真生效吗？
- Q3 文档超过 LLM context（如 200 页）怎么截断？截断会不会丢关键变更？
- Q4 evidence_verified 字段当前 true / false 比例是多少？现网真实数据
- Q5 LLM 抽出的 change_type 分类（ADD/MODIFY/DELETE/SCOPE_ADJUST/INSTRUCTION_ADJUST/UNCLEAR）准确率多少？有混淆矩阵吗？

**业务**

- Q6 LLM 抽错了影响一条监管报送出错，谁负责？
- Q7 业务方怎么知道 AI 抽得对不对？有"再核对一次"按钮吗？
- Q8 prompt 改一次会不会让历史 case 全变？我们的 eval 有没有覆盖这个？

**风险**

- Q9 LLM 幻觉率有量化吗？现在的"防幻觉"是兜底 + 显式标记，还是有 KPI？
- Q10 evidence_verified=false 的 signal 怎么对外展示？现在 UI 上跟 verified=true 视觉无差异 — 这是 bug 还是设计？

### 2.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 LLM 选型 / prompt 版本管理 | 当前 `gpt-5.4`（DashScope 兼容网关），fallback `gpt-5.3-codex`；**prompt 硬编码在 `document_profiler.py` 里，无版本管理** | 立项后：prompt 抽到 `prompts/*.txt` + git track；模型可热切（已抽象 `llm_client`） |
| Q2 LLM 失败 / mock_ai 兜底 | `complete_json` 抛 `LLMClientError` → 上游 502；**`mock_ai=true` 配置存在但代码没接 mock 分支**（即 demo 现场断网会翻车） | **P0 必修**：`llm_client` 加 mock 分支，预录响应；这是 `innovation-demo-todo.md` 的 P0-4，至今没做 |
| Q3 文档超 context | 当前 prompt 里 `(document.parsed_text)[:10000]` 硬截断；后半部分会丢 | 立项后：分段处理 + 重叠窗口 + LLM map-reduce |
| Q4 evidence_verified 比例量化 | **没量化**。字段存在但没人统计 | 一次性脚本扫库给出比例；并加 `/api/metrics/hallucination` 接口 |
| Q5 change_type 分类准确率 | **没标注、没混淆矩阵**。这是诚实短板 | 人工标 50-100 条 golden set 做评估；现有 eval framework 加 case |
| Q6 LLM 抽错谁负责 | 答："AI 仅辅助，业务方最终决策"。但 UI 上没视觉化此原则 | 立项后：每条 signal 加 review 按钮（采纳/退回）+ Banner 文案显化 |
| Q7 业务方"再核对"按钮 | **无** | 立项后加 review action，已有 audit_logs 表可写入 |
| Q8 prompt 改动让历史 case 失效 | 这就是 eval framework 的用途。现有 19 个 case 部分覆盖 | 继续扩 eval 到 50+；prompt 改动跑全套阻塞 commit |
| Q9 幻觉率量化 KPI | **没有** | 定义 KPI = `evidence_verified=true 比例` + `业务方采纳率` 双指标 |
| Q10 verified=false 视觉差异 | **真 bug**。当前 UI 上 verified=true/false 视觉无差异 | **P0 补丁**：PortraitView 加黄/绿牌，半天工作量 |

**整体定位**：LLM 核心可用，但**幻觉量化 + mock 兜底 + verified 视觉化**这三个不是技术难点而是**工程性补漏**。Demo 时必须有故事或 quick fix。



---

## 3 · 三路融合（识别变更）

### 3.1 我们做了什么

- 路 1：`revision_table_parser.py` 读 Excel 修订对照表
- 路 2：`g31_excel_diff.py` 新旧 Excel 物理对比
- 路 3：`document_profiler.py` 调 LLM 抽 change_signals
- 各路独立产出，**没有显式的 funnel/merger 模块**

### 3.2 追问清单（这是高风险区）

**核心追问**

- Q1 你说"三路融合"，代码里哪段在做合并？— 现在的答案是没有真合并
- Q2 三路命中同一变更时谁优先？— 设计文档有提"修订表 > Excel diff > LLM"，但代码里没有显式裁决器
- Q3 三路都没命中时回退到什么？— 现在是各自空返回，没有统一兜底
- Q4 三路覆盖率：单独 LLM / 单独 Excel / 三路合并 各能识别多少？没有数据
- Q5 三路冲突时怎么呈现给业务方？— UI 上看不出来某条信号是哪一路给的

**业务**

- Q6 真实银行可能有的不是 G31 251→252 这种纯结构化 Excel 修订，而是"以行文+附件表样"的混合形态，我们的三路怎么应对？
- Q7 修订对照表本身就是人工编的，会不会有错？我们的"三路融合"如果让 LLM 兜底修订表的错，逻辑是不是矛盾？

**架构**

- Q8 要不要真做一个 `triplet_funnel.py` 显式合并器？还是修正对外口径为"三路独立 + 优先级降级"？
- Q9 每路的置信度怎么对齐到同一刻度？— 现在三路各有 confidence 字段但量纲可能不一致

### 3.3 我们的答案 / 补救措施

⚠️ **这是 7 大风险里的 #1。诚实答案：我们的"三路融合"目前是 marketing 话术，代码层没真合并器。**

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 哪段代码在合并 | **没有**。三路独立产出，由调用方各自消费 | 立项后真做一个 `triplet_funnel.py` 显式合并器（约 1.5 天） |
| Q2 三路冲突优先级 | 设计文档说"修订表 > Excel diff > LLM"，**代码无显式仲裁器** | 在 funnel 里实现仲裁层 |
| Q3 都没命中回退 | 各自空返回，无统一兜底分支 | funnel 加 fallback：路 3 LLM 兜底 + 仍无 → 走 MANUAL_REVIEW |
| Q4 三路覆盖率数据 | **没有** | 立项后 `scripts/triplet_coverage_report.py` 跑 10 份发文统计 |
| Q5 三路冲突怎么呈现给业务方 | UI 看不出某条信号来自哪一路 | signal 加 `source_path` 字段，UI 用 chip 显示 [修订表 / Excel diff / LLM] |
| Q6 真实银行混合形态 | 我们处理 zip 三件套 + 单文件；漏掉"公告 + 多个独立附件包" | 立项后扩 zip_scanner |
| Q7 修订表本身可能错 | 这是真问题。设计有 review_status 字段但**没用** | 修订表入库强制走 PENDING；业务方审核后才进 funnel |
| Q8 真做 funnel 还是改口径 | **推荐：真做一个 thin funnel**（约 1.5 天）+ 显式 source 字段。话术保留"三路融合"，但实际有合并逻辑撑着 | 进项目 P1 |
| Q9 三路置信度对齐 | 不一致（修订表 ~1.0 / Excel diff 0.8-0.95 / LLM 0.5-0.95） | funnel 里做归一化 + 业务可解释的 score |

**面对追问的 30 秒话术（暂版）**：

> "当前三路独立产出，按修订表 > Excel diff > LLM 的优先级降级使用，UI 上能区分某条信号来自哪一路。计划立项后做一个显式合并器把仲裁逻辑代码化。"

— 诚实承认目前不是"完美融合"，但有清晰路径。比硬撑"我们融合了"经得起追问。



---

## 4 · 字段定位 + 血缘 + 概念命中

### 4.1 我们做了什么

- `LineageView.vue` 主页面，左侧报表目录树 + 右侧详情
- 概念命中横幅（顶部全文档级 14 个概念 chip）
- 右侧"通过这些概念辐射到此报送项"（今天刚改为 evidence_text 原文命中）
- 血缘可视化 `LineageGraph.vue` 4 列节点连线（指标→报送字段→源字段→维度）
- `item_resolver` 把 LLM 抽出的 indicator_hint 反查到 reg_reporting_items.item_code

### 4.2 追问清单

**技术**

- Q1 reporting_item_lineage 这张表数据从哪来？— 当前是 `reporting_seed.py` 手工写的 63 条
- Q2 真实银行有几千上万条字段血缘，怎么导入？谁来维护？
- Q3 血缘准确率谁背书？错的血缘会让整条工单链路歪掉
- Q4 跨系统血缘（源系统 → 数据集市 → 报送字段，多跳）现在能处理吗？
- Q5 血缘可视化（LineageGraph）在 1000+ 节点时还能用吗？

**业务**

- Q6 不同报表 lineage 密度差异大（G31 有 39 条 / G27 只有 4 条）— demo 时不同表看到的丰满度差别大，怎么解释？
- Q7 业务方维护血缘的工作量多大？立项后这块工作分给谁？
- Q8 银行通常已经有数据治理平台维护血缘了（如 Informatica / 自研），我们是替代还是消费？

**治理**

- Q9 血缘的版本管理？监管报表升级了血缘要同步更新，怎么对齐？
- Q10 字段血缘里有敏感字段（如客户身份证号），权限怎么管？

### 4.3 我们的答案 / 补救措施

⚠️ **这是 7 大风险里的 #5 + #6 — 真实银行 lineage 数据来源是落地最大未知。**

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 lineage 数据从哪 | **当前 63 条全是 `reporting_seed.py` 手工写的 seed**；evidence 字段标着"模拟生成的G31血缘参考数据" | 立项后做 importer：① 对接行内 Atlas / Informatica metadata；② Excel/CSV 批量导入；③ 单条手工录入 |
| Q2 真实银行几千上万条怎么导 | 没设计 | 立项后写 3 个 adapter（Atlas API / Informatica REST / 通用 CSV）+ 增量同步 |
| Q3 血缘准确率背书 | 当前 PoC seed 无背书。生产由数据治理团队背书 | schema 已有 `confidence_level` / `mapping_status` 字段；加 `verified_by` + `verified_at` |
| Q4 跨系统多跳血缘 | 现在 `lineage_role` 区分 REPORT/SOURCE/FILTER/DIMENSION 四类；实际仅 2-3 跳，未真做无限链 | lineage 边构成有向图，BFS/DFS 遍历即可；当前足够 |
| Q5 LineageGraph 1000+ 节点性能 | 当前 SVG 实现没 virtualization，1000+ 会卡 | 立项后：① 节点折叠（默认显示直接邻居）；② 切 canvas 渲染；③ d3-force layout |
| Q6 demo 时不同表丰满度差异 | 真问题。G31 39 条 / G27 4 条 / G21 5 条 / G24 7 条 / G25 8 条 | 你 TODO P1-3 写过"给 G21/G25/G27 各补 3-4 条"；约半天工作量 |
| Q7 lineage 维护谁来 | 立项后建议数据治理团队主负责，业务方提需求 | 写责任矩阵 |
| Q8 替代还是消费现有数据治理平台 | **关键定位**：**消费，不替代**。我们是"监管语义层"，他们是"业务数据层" | 立项后定义 adapter 接口；这条故事讲清楚就能化解 60% 数据治理团队的抵触 |
| Q9 血缘版本管理 | 当前 lineage 表无 effective_from/to | 加版本字段；版本切换由数据治理团队触发 |
| Q10 敏感字段权限 | 现在零权限。schema 里有 `sensitive_level` 字段但**没用** | 立项后接 LDAP + RBAC + 字段级 mask |

**面对追问的 30 秒话术**：

> "当前血缘是 PoC seed 数据，立项后通过 3 个 adapter（Atlas/Informatica/CSV）从行内数据治理平台导入。我们的定位是**消费**血缘+在上面叠加监管语义层，不是替代行内数据治理团队。"



---

## 5 · 概念库 + 多路 match

### 5.1 我们做了什么

- `RegConcept` + `RegConceptAlias` + `RegConceptVersion` + `RegConceptRelation` + `RegConceptReportingItemMap` 全套表
- 23 个种子概念（手工灌入）+ 各概念 2-5 个 alias
- `ConceptMatcher` 三路召回：alias substring / definition 子串 / embedding 余弦相似度
- embedding 用 DashScope text-embedding-v3（1024 维）
- `/api/concepts/match` 透出 paths / score 让前端区分召回路径

### 5.2 追问清单（这是高风险区）

**治理 — 重点**

- Q1 这 23 个概念是怎么挑的？根据什么标准？
- Q2 谁来扩到 100 个？谁来审？谁来废弃？— **当前完全无治理流程**
- Q3 alias 重复 / 冲突谁仲裁？
- Q4 概念准确性谁背书？错了导致工单全错怎么办？
- Q5 监管发文用新词时，加新概念的 SLA 是几天？
- Q6 概念库错了能不能回滚？审计 trail 有吗？

**业务**

- Q7 立项后这个概念库归谁维护？数据治理部 / 业务部 / IT？
- Q8 不同分行 / 不同业务条线的术语理解可能不一致，怎么统一？
- Q9 监管自己的术语在不同发文里就不一致（"同业融入余额"和"金融机构融入款项"），我们靠 alias 兜得住吗？

**技术**

- Q10 embedding 用 DashScope = 数据出行。银行场景里这是硬伤，本地化方案是什么？
- Q11 概念数到 500+ 时召回性能拐点在哪？现在没基准
- Q12 embedding 模型升级（如 v3 → v4）后如何重建？停机时间多久？

**反向**

- Q13 概念辐射的 `reg_concept_reporting_item_map` 是谁标的？业务方认可吗？
- Q14 #5 风险：CON_BILL "票据" 辐射到 G31 BOND_INVESTMENT_BALANCE — 这映射是基于业务推测还是 PoC 拍脑袋？

### 5.3 我们的答案 / 补救措施

⚠️ **这是 7 大风险里的 #3 + #5 — 治理流程和映射背书是最核心的薄弱点**

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 23 个概念怎么挑的 | 基于 G31 填报说明 + G24/G25/G27 真实材料**手工提取**；无正式 governance | 立项后给每个 concept 标 `source_document_id` + `extracted_by`，让来源可查 |
| Q2 谁扩 / 谁审 / 谁废弃 | **完全无流程** | 立项后写 1-2 页 governance 文档：数据治理部主管 + 业务方代表 + 监管口径专家三方机制 |
| Q3 alias 冲突仲裁 | 没机制 | alias 入库查重；冲突走 PENDING 状态 + 三方审核 |
| Q4 准确性背书 | 当前**无人背书** | 立项后业务方代表签字 + 在 demo 时承认这是 PoC 推测 |
| Q5 加新概念 SLA | 估计 1-3 工作日（人工审核） | 立项书里定义 SLA |
| Q6 错了能回滚 / 审计 | status 可设 ARCHIVED；audit_logs 表存在**但没用** | concept review 必须走 audit_logs |
| Q7 维护归谁 | 当前归我们；立项后数据治理 + 业务部协作 | 责任矩阵 |
| Q8 不同分行术语不一致 | 监管报送以**总行口径**为准 | 业务规范上统一 |
| Q9 监管自己术语不一致 | 真问题。靠 alias + embedding 兜 | 现有架构能处理 |
| Q10 **DashScope = 数据出行 = 银行硬伤** | **真问题。当前 demo 用阿里云** | **立项后必须本地化**：Qwen-72B / DeepSeek-V3 / bge-m3 本地部署；`llm_client` 已抽象，切换零成本；准备一份"私有化部署架构图" |
| Q11 性能拐点 | 没基准 | 立项后跑 100/500/1000 概念的 query 基准 |
| Q12 embedding 模型升级 | 当前 `model_name` 字段记录了 | 升级时双模型并跑 + 切流量灰度 |
| Q13 `reg_concept_reporting_item_map` 谁标 | 当前我们拍脑袋 | 业务方过一遍 + 加 `verified_by` 字段 |
| Q14 CON_BILL → G31 映射判断 | PoC 推测（2026-05-27 已讨论） | 标 `confidence=LOW + status=PENDING_BUSINESS_REVIEW` |

**面对追问的 30 秒话术**：

> "23 个种子概念是基于 G31 真实填报说明手工提取，立项后会建立三方治理机制（数据治理 + 业务方 + 监管口径专家）。当前 demo 的概念辐射映射是 PoC 推测，业务方审核是 P0 工作。embedding 用阿里云 DashScope 是研发版本，生产部署会切到本地化 Qwen / DeepSeek，已做接口抽象切换零成本。"



---

## 6 · 规则卡片 L1/L2/L3

### 6.1 我们做了什么

- L1（原文文本卡）部分实现：`rule_card_seed` 灌入 + 工单挂载
- L2（四元组）schema 已建，未真填充
- L3（可执行表达式）schema 已建，仅占位
- `RegReportingRuleCardValidation` 表已建，未跑过

### 6.2 追问清单

**技术 / 业务**

- Q1 L1/L2/L3 三级分层的业务依据是什么？为什么不是 L4 或 L2？
- Q2 L2 四元组 `(主体, 谓词, 客体, 限定)` 真能覆盖银行业务规则吗？举一个反例
- Q3 L3 可执行规则现在是 SQL 还是 DSL？真业务规则能转 SQL 吗（如"穿透原则"怎么转 SQL）？
- Q4 L1 卡片的"原文锚定"准确率？业务方对"原文摘录"的标准是不是跟我们抽的一致？
- Q5 卡片版本演进：监管改了，旧版卡片怎么 effective_to_version？谁来标？

**治理**

- Q6 卡片是谁审的？现在 demo 是种子，立项后流程？
- Q7 卡片错了导致工单错指建议，怎么追责？

### 6.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 L1/L2/L3 分层依据 | L1=原文摘录（最易做）/ L2=四元组（中等）/ L3=可执行（最难）；对应"文档→数据→执行"三层 | 设计文档已说明；demo 时讲清这是"渐进结构化"理念 |
| Q2 L2 四元组真覆盖业务规则？ | 部分场景可（"债券投资余额, 包含, 应收利息, 计提日 <= 报告日"）；不能覆盖：复杂条件嵌套 / 时间序列 / 跨表 join | 诚实说"L2 是规范化高频规则的工具，复杂规则留 L3 或自然语言备注" |
| Q3 L3 用什么语言 | 设计是 SQL/DSL；"穿透原则"用 SQL 表达困难 | L3 范围限制在"可 SQL 表达的口径校验"，非 SQL 规则留 L2 + 人工 |
| Q4 L1 原文锚定准确率 | 当前 `evidence_verified` 字段；业务方对粒度可能不一致 | 立项后定义抽取粒度规范（短语级 vs 句子级） |
| Q5 卡片版本演进 | `effective_from/to_version` 字段已有但没用 | 监管发文入系统时触发卡片 review 流程；旧卡片 effective_to_version=旧版 |
| Q6 卡片审查 | `review_status` 字段已有；当前 demo 数据自动设 CONFIRMED | LibraryView 加 review 按钮（已在 P1 todo） |
| Q7 卡片错了误指建议 | "AI 仅辅助 + 人工最终决策"原则 | 审计 trail 完备（audit_logs 必接入） |

**整体定位**：L1 已可用，L2 schema 就位但未实际填充，L3 设计文档明确**一期不实现**。诚实说**这是渐进式产品**，立项后随业务深化逐级落地。



---

## 7 · 影响分析

### 7.1 我们做了什么

- `reporting_impact_analyzer.analyze_reporting_impacts()`
- 输入：change_signals + catalog
- 输出：impact_items（包含 reporting_item_code / impact_type / 源字段 / 触发的子单类型）
- 按 reporting_item_code 合并去重

### 7.2 追问清单

**技术 / 业务**

- Q1 impact_type 当前实际只有 INDICATOR_SCOPE 一种 — 你设计文档列了 8 种（结构 / 口径 / 机构范围 / 源字段 / 加工逻辑 / 校验 / 补录 / 历史），其他 7 种什么时候做？
- Q2 影响项粒度（指标级 / cell 级）怎么定？现在是指标级，业务方需要更细吗？
- Q3 影响项的"假阳性"如何处理？— 现在我们没有 review 接口
- Q4 跨表 / 跨期 / 跨机构影响怎么追？现在似乎只支持本次发文涉及表内
- Q5 影响分析的 confidence 是怎么算的？

**业务**

- Q6 业务方拿到影响清单要做什么动作？现在的"recommended_action"是模板字符串，真能指导工作吗？
- Q7 影响项跟工单是什么关系？1 个影响项 → N 个工单？还是反过来？

### 7.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 8 种 impact_type 何时做 | 当前实际只有 `INDICATOR_SCOPE` 单一 | 你 TODO P1-7 已列；立项后细化 |
| Q2 影响项粒度 | 当前指标级（item_code）；业务方可能要细到 cell | 设计兼容：加 `cell_level_codes` 数组字段，必要时下钻 |
| Q3 假阳性 review | 当前**无 review 接口** | 你 TODO P1-4 已列（PATCH /api/reporting/impact-items/{id}/review） |
| Q4 跨表 / 跨期 / 跨机构 | 跨表通过 item_code 前缀拼接（简单）；跨期、跨机构未做 | 立项后加 dimension_filter |
| Q5 confidence 算法 | 当前透传 change.confidence_score | 立项后用"信号源置信度 × 业务关键度 × 历史采纳率"复合算法 |
| Q6 `recommended_action` 是模板字符串 | 是模板（"复核报送字段、资金同业源字段..."），G31 场景出现 G24 词汇是 bug | 你 TODO P1-7 + Codex Task 4 已部分修复；立项后真 LLM 化 |
| Q7 影响项 ↔ 工单关系 | 当前 1 影响项 → N 子单（通过 `related_impact_codes` 关联） | 立项后做双向可查 + 工单关闭回写影响项 review_status |

**整体定位**：影响分析骨架已成型，**impact_type 细分 + review 接口 + recommended_action LLM 化** 是立项后的核心深化。



---

## 8 · 工单生成（结构化任务卡 + 触发器 + 质量评分）

### 8.1 我们做了什么

- Task 1：TicketDraft 加 14 个结构化字段 ✅
- Task 2：触发器引擎 `ticket_trigger_engine.py` ✅
- Task 3：任务卡构造器 `ticket_card_builder.py` + 质量评分 `ticket_quality_checker.py` ✅
- Task 4：generator 重构为编排器 ✅（我做的）
- Task 5：前端 ReviewTicketView 重构 — Codex 在做
- Task 6：端到端回归 — 待做

### 8.2 追问清单

**技术**

- Q1 触发器的条件规则是哪里写的？谁定的？业务方校验过吗？
- Q2 拆单粒度合理吗？同一个 ETL 改动会不会被拆到 3 个不同子单里？
- Q3 工单关闭流转的工作流是什么？谁审批？现在只有 status=DRAFT/CLOSED 两个状态
- Q4 触发器规则跟业务方真实工作流的对齐度？(#6 风险)

**业务**

- Q5 ResponsibleSystem 枚举（REG_REPORTING_SYSTEM / DATA_GOVERNANCE_PLATFORM / DATA_MART_ETL / SOURCE_SYSTEM / DATA_QUALITY_PLATFORM / TEST_ACCEPTANCE / KNOWLEDGE_ARCHIVE）是不是真符合银行内部组织结构？
- Q6 责任人字段（owner / executor）是角色还是真名？怎么跟 AD/HR 系统对接？
- Q7 工单跟既有 ITSM 系统（ServiceNow / 自研）怎么集成？

**质量**

- Q8 quality_score 算法是什么？业务方认可这套评分吗？
- Q9 quality_score 低于多少不能流转出去？现在有阻塞机制吗？
- Q10 工单内容（must_do / acceptance_criteria）是模板还是 LLM 生成？立项后能 LLM 化吗？

### 8.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 触发器条件规则哪定的 | 在 `ticket_trigger_engine.py` 里写死；设计文档 `concept-and-ticket-reuse-design.md` 有规则表 | 立项后请银行报送岗 review 一遍；写"触发器规则对齐表" |
| Q2 拆单粒度合理吗 | 当前按 action_type × responsible_system 拆；同一 ETL 改动会被拆到 REPORT_PROCESSING + VALIDATION_RULE | 立项后加 merge 规则：同一影响项的多个子单可合并展示 |
| Q3 工单流转工作流 | 当前只有 status=DRAFT；缺 SUBMITTED / APPROVED / CLOSED | 立项后定 BPMN 流程；W2 决策档案需要它 |
| Q4 触发器对齐业务方？ | **没业务方校验** | **P0**：找银行报送岗 / 数据治理团队过一遍 |
| Q5 ResponsibleSystem 枚举对齐银行内部 | 我们 7 个：监管报送 / 数据治理平台 / 数据集市 / 源系统 / 数据质量 / 测试验收 / 知识归档；不同银行命名可能不同 | 立项后每个客户定制 enum 值 |
| Q6 责任人对接 AD/HR | 当前是字符串占位；无 LDAP 集成 | 立项后接 LDAP + RBAC |
| Q7 跟既有 ITSM 集成 | 推荐 webhook | 立项后定 adapter 接口（ServiceNow / Jira / 自研都通） |
| Q8 quality_score 算法 | 缺责任系统 / 缺资产 / 缺验收 / 正文过长等扣分；业务方未必认可这套 | 立项后业务方 review + 调权重 |
| Q9 quality 阻塞机制 | **当前不阻塞**任何流转 | 立项后：score < 60 阻塞 SUBMIT，强制人工补全 |
| Q10 must_do / acceptance 是模板？LLM 化？ | 当前模板字符串 | 立项后 LLM 化 + 引用决策档案 |

**整体定位**：Codex Task 1-4 已合，Task 5 前端进行中。**核心架构已通**，触发器需业务方 review，流转工作流是立项后必做。



---

## 9 · 决策档案（W2 stub）

### 9.1 我们做了什么

- `decision_archive_service.search_similar_decisions()` 接口骨架
- 当前返回空字典 stub
- W2 阶段才接真实 audit_logs 查询

### 9.2 追问清单

**业务 — 这是我们之前讨论过的现实摩擦**

- Q1 真实银行有"复用历史决策"的工作习惯吗？还是每次都"从零解读"避免背锅？
- Q2 历史工单的"决策结论"现在是非结构化文本，怎么变成可搜索？
- Q3 冷启动期（6-12 个月）档案是空的，业务方怎么用？
- Q4 决策档案错了（推荐了上次错的方案）怎么办？

**技术**

- Q5 历史工单关闭时怎么强制写入结构化 decision_type / decision_rationale / field_adjustments？
- Q6 跨任务相似度怎么算？concept_codes 交集吗？需要 embedding 吗？

### 9.3 我们的答案 / 补救措施

⚠️ **这是我们之前讨论时已经认定有"现实摩擦"的模块。诚实定位调整：从"自动复用推荐" → "决策档案/审计追溯"。**

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 银行真有"复用历史决策"习惯吗 | 合规岗倾向"每次从零解读"避免背锅；**纯"复用推荐"价值有限** | **重新定位**：3 个真价值场景 — 审计追溯 / 知识沉淀 / 新人 onboard；不主推"AI 一键复用方案" |
| Q2 历史工单变可搜索 | 当前关闭工单 audit_log 没强制结构化 | 立项后加工单关闭 hook：强制写 `decision_type` / `field_adjustments` / `hit_concept_codes` |
| Q3 冷启动 6-12 月 | 真问题 | demo 时讲长期价值；短期演示用 3-5 条 seed 案例 |
| Q4 推荐错的方案 | "AI 仅辅助 + 业务方最终决策" | UI 标"📚 历史参考"，不写"AI 推荐" |
| Q5 关闭时强制结构化 | 没做 | 立项后做 hook |
| Q6 相似度算法 | 当前 stub 返回空 | W2 实现：`concept_codes` 交集 + 时间衰减；不上 embedding |

**面对追问的 30 秒话术**：

> "决策档案不是'AI 自动给业务方复用方案'，而是'监管变更处理的结构化档案库'。三个真实价值：① 审计追溯监管能查；② 知识沉淀让 6 个月后还能找回结论；③ 新人入职看历史案例学习。短期 demo 用 seed 演示，长期价值依赖 6-12 个月真实工单积累。"



---

## 10 · eval framework

### 10.1 我们做了什么

- 19 个 eval case（G31 diff / concept_match × 10 / item_resolve × 8）
- 4 种断言类型（signal_count / must_contain / must_not_contain / all_signals_match）
- pytest 入口 + CLI run_eval.py
- 持久 DB embedding 克隆到 in-memory 让 eval 能测 embedding 路径

### 10.2 追问清单

**质量**

- Q1 19 个 case 是自己出题自己改卷，标准是不是太松？
- Q2 业务方有没有参与制定"正确答案"？— 现在没有
- Q3 case 的 signal_count 上限（如 max=15）是为了 pass 调宽的吗？— 部分是
- Q4 eval pass 不代表业务正确，怎么补充"业务 golden set"？

**工程**

- Q5 prompt 改动如何 review？现在 commit 顺手改，eval 跑过就过
- Q6 eval 失败时谁负责？阻塞 commit / merge 吗？

### 10.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 19 个 case 自评太松 | 部分 case 上限放宽到 max=15 是真的；但 must_not_contain / 负样本类是严格的 | 立项后区分"基础回归 case"（防退化）和"业务正确性 case"（业务方参与） |
| Q2 业务方参与制定正确答案 | **当前没有** | 立项后建 golden set，业务方过一遍 must_contain 期望 |
| Q3 max=15 是为了 pass 调宽 | embedding 启用后召回数自然涨；不是为了凑数 | 每条上限的依据要写在 case 的 reason 字段里（部分已写） |
| Q4 业务 golden set | **没有** | 立项后建；按报表 / 按概念 / 按变更类型分类 |
| Q5 prompt 改动 review | 当前 commit 顺手改 | 立项后写 prompt 改动 checklist + 跑 eval 全套阻塞 commit |
| Q6 eval 失败阻塞 merge | **当前没接 CI** | 立项后加 GitHub Action / 行内 Jenkins，PR 必跑 eval |

**整体定位**：eval 框架本身是工程优势（同行少见），但**自评数据需要业务方参与**才能真正可信。



---

## 11 · 跨监管体系扩展能力

### 11.1 我们做了什么

- 设计了 RegConceptGroup + RegConceptGroupMember（W4 补丁 D，尚未实现）
- 文档说明 1104 → EAST → 一表通 → 反洗钱可复用同一套底座

### 11.2 追问清单

**核心**

- Q1 当前 demo 只跑 1104，扩 EAST 工作量多大？给一个量化估计
- Q2 不同监管体系的报表元数据格式差异大吗？我们的 reg_reporting_objects schema 通用吗？
- Q3 跨体系概念绑定的"等价关系"谁标？这个标注本身就是巨大工作量
- Q4 当年银保监会、人民银行、外管局的报表系统各有差异，我们的设计是不是过于一厢情愿？

### 11.3 我们的答案 / 补救措施

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 扩 EAST 工作量 | 估算：概念库扩 30-50 个（2 人日）+ 报表元数据导入（1-2 人日）+ lineage seed（2-3 人日）= **总 5-8 人日** | 立项后写 EAST 接入路线图，量化各模块工作量 |
| Q2 schema 通用吗 | `reg_reporting_objects` / `reg_reporting_items` 字段对 1104/EAST/一表通基本通用 | reporting_system_code 已抽象；部分字段（表号格式）需要 schema 调整 |
| Q3 跨体系等价关系谁标 | 设计了 `RegConceptGroup` + `RegConceptGroupMember` 小表（W4 补丁 D），尚未实现 | 立项后业务专家 + 监管口径专家三方标定首批 5-10 个 group |
| Q4 设计是否过于一厢情愿 | **部分诚实点**。1104 vs 一表通的"报表"概念差异可能比想象大；如表号格式、行号系统、口径粒度 | **优先做 1104 上线**，积累真实数据，再评估扩 EAST/一表通；不要做"通用框架"营销 |

**面对追问的 30 秒话术**：

> "1104 是一阶段落脚点，扩 EAST 估算 5-8 人日。底层 schema 设计已抽象 reporting_system_code，但不同体系的报表细节差异需要适配。我们的策略是先在 1104 跑通，积累真实数据，再决定是否扩 EAST。不做空头'通用框架'承诺。"



---

## 12 · 跨切关注（团队 / 商业 / 合规）

### 12.1 团队

- Q1 现在是几个人做？— 主要是用户一人 + AI 协作
- Q2 立项后要几个人？什么角色？— 需要给出团队结构图
- Q3 业务专家在哪？数据治理顾问在哪？— 项目结构里这个空位很大
- Q4 持续维护怎么保障？— 没人维护就是单点风险

### 12.2 合规 / 数据安全

- Q5 数据是否出行？— 当前 DashScope embedding 是出行的，立项后必须本地化
- Q6 等保几级要求？现在没做任何认证
- Q7 监管报送数据涉密，权限怎么管？— 现在零权限模型
- Q8 审计 trail：每个工单决策的"谁在什么时候改了什么"能不能给监管查？— audit_logs 表有但没用

### 12.3 商业

- Q9 立项预算估算？人月 / 服务器 / LLM 调用成本
- Q10 跟现有报送平台（Gientech / 文思海辉 / 神州信息）是合作还是替代？
- Q11 ROI 怎么算？— 现在的"3 天压到 5 分钟"是单点感受，整体年化收益怎么估？

### 12.4 我们的答案 / 补救措施

#### 团队

| Q | 现状 | 补救路径 |
|---|---|---|
| Q1 现在几个人 | **用户一人 + AI 协作**；commit history 一目了然 | 立项后建团队 |
| Q2 立项后人员 | 建议 **2-3 个工程师（1 后端 + 1 前端 + 0.5 全栈）+ 1 业务专家 + 0.5 运维**；约 4-4.5 FTE | 立项书明确 |
| Q3 业务专家空位 | **当前没业务方代表**；这是最大短板 | 立项后必须配 1 个数据治理 / 报送岗专家半全职参与 |
| Q4 持续维护 | 单兵无法长期维护；监管改了我跑路就死项目 | 立项 = 团队化 = 解决持续性 |

#### 合规 / 数据安全

| Q | 现状 | 补救路径 |
|---|---|---|
| Q5 数据出行 | **当前 embedding 走阿里云 DashScope = 出行 = 银行硬伤** | **立项后必须本地化**：Qwen-72B / DeepSeek-V3 / bge-m3 本地部署；`llm_client` 已抽象切换零成本；提前准备私有化架构图 |
| Q6 等保等级 | 未做任何认证 | 立项后定目标（一般 3 级），合规团队走流程 |
| Q7 权限模型 | **当前零权限**，所有 API 裸开 | 立项后接 LDAP + RBAC + 字段级 mask；schema 里 `sensitive_level` 字段已就位 |
| Q8 审计 trail | `audit_logs` 表已建**但完全没用** | 立项后所有写操作必走 audit_logs；W2 决策档案依赖它 |

#### 商业

| Q | 现状 | 补救路径 |
|---|---|---|
| Q9 立项预算 | 估算（4.5 FTE × 6 个月 + 服务器 + LLM）≈ **150-200 万 + 私有云模型部署一次性成本 30-50 万** | 立项书细化 |
| Q10 vs Gientech/文思海辉 | **定位：合作不替代**。他们是"报送加工"，我们是"监管变更治理 + 报送加工的语义层" | 写一页 vs 表，明确补位关系 |
| Q11 ROI 算法 | 单点感受："3 天人工解读 → 5 分钟可复核结论"；年化估算：假设每年 30 份监管发文 × 节约 2.5 工作日 × 3-5 人参与 ≈ **225-375 工日 ≈ 50-100 万人工成本年化节约** | 立项书放估算公式 + 业务方过一遍 |



---

## 13 · 关键回答模板（领导追问时的 30 秒话术）

> _这部分填好后是 demo 现场万一被追问的"罐头答案"_

| 追问 | 30 秒话术 |
|---|---|
| "这是 AI 还是规则" | 三路混合：① 修订对照表纯规则确定性输出；② Excel 物理 diff 纯规则；③ LLM 抽取变更信号。所有 AI 输出都带原文锚定证据（evidence_verified）和置信度分。AI 在前提供"草稿"，业务方在终做"决策"。 |
| "幻觉怎么办" | 三层防御：① evidence_text 必须在原文中精确匹配，否则该信号自动打黄牌；② 业务方每条 signal 可采纳/退回，决策必走 audit_log；③ eval framework 19 个回归 case + 人工金标准持续打分。**AI 不发明事实，发明了就被自动标记。** |
| "为什么是你不是 Gientech" | Gientech 解决"怎么把数据填进报表"，我们解决"监管口径变了，要改哪些字段、谁来改、改完怎么验收"。**是补位不是替代**：在他们的报送平台之上，叠加一层"监管变更治理 + 业务概念语义层"，把人工 3 天的解读工作压缩到 5 分钟。 |
| "概念库怎么扩" | 当前 23 个种子是基于 G31/G24/G25/G27 真实填报说明手工提取。立项后建三方治理机制：数据治理部 + 业务方代表 + 监管口径专家。每个新概念入库走 PENDING → 三方 review → ACTIVE 流程，SLA 1-3 工作日。监管发文用新词时通过 alias 表 + embedding 兜底。 |
| "数据出行吗" | 当前 demo 用阿里云 DashScope embedding 是研发版本。生产部署版本会切到**本地化**：embedding 用 bge-m3（本地 CPU 即可）/ 对话用 Qwen-72B 或 DeepSeek-V3（行内 GPU 集群）。`llm_client` 已抽象 OpenAI 兼容协议，切换只改 `.env`，模型权重和向量库全部在行内私有云。 |
| "一个人能做吗" | 当前 PoC 由一人主导 + AI 工具协作，已沉淀 11K 行后端 + 8K 行前端 + 100+ 测试 + 完整设计文档（git history 可查）。立项后建议 2-3 工程师 + 1 业务专家 + 0.5 运维约 4.5 FTE 团队。**单兵做 PoC 是节省成本，团队化是落地保障**。 |
| "立项后多久能出 G24 上线版本" | 估算 **3 个月** MVP 上线 G24（单表）：第 1 月 — 团队组建 + 行内数据治理平台对接；第 2 月 — 概念库治理流程 + 业务方 review；第 3 月 — 真实数据接入 + 试点上线。后续每月可扩 1-2 张表。 |

---

## 14 · 优先讨论顺序（建议）

按"先攻最薄弱、先答最常被问"原则，建议讨论顺序：

1. **§5 概念库治理流程**（最高风险）
2. **§3 三路融合的真合并器**（差异化卖点站不站得住）
3. **§4 真实银行 lineage 数据来源**（落地最大未知）
4. **§2 LLM 幻觉量化 + 视觉化**（合规核心）
5. **§13 关键回答模板**（演示时罐头答案）
6. 其他模块按时间填

---

## 修订记录

- 2026-05-27 初版（Claude 起草，待用户讨论填答）
