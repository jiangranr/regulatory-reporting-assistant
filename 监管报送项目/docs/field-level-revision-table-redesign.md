# 字段级修订对照表设计方案

> 状态：方案 v2（已纠偏）
> 最近更新：2026-05-24

## 1. 一句话定位

**修订对照表是独立的、长期沉淀的「监管制度变更知识库」，类似"报表目录"是一种知识资产。**
**它不取代主流程**（上传发文 → 影响分析），但会作为参考资料被主流程和工单生成参考，并供数据治理团队人工维护。

## 2. 为什么需要它

### 2.1 监管侧客观情况

经调研 1104 / EAST 5.0 / 一表通发布材料：

- 监管**不主动发布修订对照表**，给的是 PDF 通知 + Excel 表样 + Word 填报说明
- 节奏不固定：年度大更新（zip 包）+ 平时小补丁（单文件）
- 银行需**自行对比新旧版本**产出"变更影响清单"

### 2.2 行内现状

银行内部也**没有现成的修订对照表**，每次升级靠业务/数据治理同学人工梳理 Excel，质量参差，无版本管理，跨年丢失。

### 2.3 本系统要解决的

- 为修订对照表提供**结构化存储**（之前只有 6 列 cell 维度 Excel 解析器，颗粒不对）
- 提供**人工录入/审核 UI**（复用"报表目录"页面架构）
- 未来通过 zip 包自动抽取（**先不做，明确延后**）

## 3. 主流程与修订对照表的关系

```
┌─────────────────────────── 主流程（不动）──────────────────────┐
│  上传发文 → 文档画像 → 影响分析 → 工单草稿                       │
└──────────────────────────────────┬─────────────────────────────┘
                                   │
                          (未来可选参考)
                                   │
                                   ▼
┌──────────────────────── 修订对照表（新增）──────────────────────┐
│  数据治理同学维护                                                │
│  ├─ 制度版本管理（regime_versions）                              │
│  └─ 字段级修订条目（regulatory_revisions）                       │
│                                                                  │
│  前端：在「报表目录」页面增加 Tab「修订对照表」                   │
│  未来：zip 包自动抽取（阶段 2 工作，本期不做）                    │
└──────────────────────────────────────────────────────────────────┘
```

**关键边界：**

- 影响分析（`/api/tasks/{id}/analyze-impact`）继续读 `change_signals`，**不读修订对照表**
- 修订对照表的 CRUD 是独立 API，**和影响分析解耦**
- 未来若要让影响分析参考修订对照表，再额外开口子；当前不耦合

## 4. 决策记录（已确认）

| # | 决策 | 内容 |
|---|---|---|
| 1 | `change_summary` | **加**。一句话变更摘要，列表展示用 |
| 2 | `source_document_id` | **加**。绑定到 `reg_documents.id`，可空（手工录入留空，未来 zip 解析自动填） |
| 3 | `analyze_from_revisions` 代码 | **直接删**。回退到主流程不变 |
| 4 | 前端方案 | **A. CatalogView 加 Tab**。和"报表对象/指标/字段"并列一个"修订对照表" |
| 5 | `field_code` 命名 | snake_case 英文（参考 EAST 数据元） |
| 6 | 字段粒度 | 1 业务字段 → N cell，通过 `affected_cells` 数组反向展开 |
| 7 | `change_dimensions` | 起步 14 项，按需扩展 |
| 8 | 版本策略 | 每个 zip 包独立一份 `regime_version` + 累计视图按 (report, field) 取最新 |

## 5. 数据模型

### 5.1 `regime_versions` —— 制度版本目录（10 列）

每次监管发文 zip 包对应一行。一年内多次小更新各占一行，互不覆盖。

| 字段 | 类型 | 说明 |
|---|---|---|
| `regime_version` | str, unique | `1104-2026Q1-v2` |
| `reporting_system_code` | str | `1104` / `EAST` / `一表通` |
| `version_name` | str | "2026 年第 14 号公告·1104 资金同业指标口径修订" |
| `effective_date` | str | 首次生效报送期 `2026-06-30` |
| `publish_date` | str | 监管发文日期 `2026-03-15` |
| `source_zip_name` | str | `1104-2026Q1-v2.zip` |
| `affected_report_codes` | JSON | `["G31","G24"]` |
| `revision_count` | int | 修订条目数（冗余，列表展示用） |
| `status` | enum | `DRAFT / PUBLISHED / SUPERSEDED` |
| `notes` | text | 备注 |

### 5.2 `regulatory_revisions` —— 字段级修订条目（最终 17 列）

每条 = 一个业务字段的一次变更。

**身份（6 列）：**

| 字段 | 类型 | 示例 |
|---|---|---|
| `revision_id` | str, unique | `REV-1104-2026Q1-G31-007` |
| `regime_version` | str | `1104-2026Q1-v2`（FK → regime_versions） |
| `reporting_system_code` | str | `1104` |
| `report_code` | str | `G31` |
| `section_code` | str | `PART_I` |
| `field_code` | str | `indirect_holding_balance`（snake_case，系统级唯一） |

**变更内容（5 列）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `field_name` | str | "因持有非底层资产间接持有期末余额" |
| `change_type` | enum | `NEW / MODIFY / DELETE / RENAME / SPLIT / MERGE` |
| `change_dimensions` | JSON list | 14 项之一或多选（见 §5.3） |
| `change_summary` | text | **一句话人话摘要**，列表展示用，必须说清具体怎么变 |
| `before_value` / `after_value` | JSON | 旧/新版属性快照，详情对比用 |

**证据（3 列）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `source_document_id` | int, nullable | 关联 `reg_documents.id` |
| `regulation_evidence` | text | 监管原文片段 |
| `evidence_source_ref` | str | 文件锚点：`filing.pdf#§3.4` |

**衍生（1 列）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `affected_cells` | JSON | 自动展开的 item_code 列表（按 field_code → column_label 匹配） |

**审核（5 列）：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `effective_date` | str | 生效报送期 |
| `confidence_level` | enum | `HIGH / MEDIUM / LOW` |
| `review_status` | enum | `DRAFT / CONFIRMED / DISPUTED` |
| `reviewer` | str | 复核人 |
| `remark` | text | 备注 |

**唯一约束：** `(regime_version, field_code)`，同一版本同一字段不能重复登记。

### 5.3 `change_dimensions` 14 项枚举

| 维度 | 示例场景 |
|---|---|
| 口径 | 余额定义从"账面"改"账面 + 应收利息" |
| 数据类型 | DECIMAL(10,2) → DECIMAL(15,4) |
| 长度 | VARCHAR(20) → VARCHAR(50) |
| 单位 | 元 → 万元 |
| 枚举值 | 发行人类型从 5 个枚举扩展到 9 个 |
| 必填 | 选填 → 必填 |
| 默认值 | 默认 0 → 默认 null |
| 校验规则 | A + D = E → A + D = E ± 5% |
| 计算公式 | 加权方式从余额加权改市值加权 |
| 填报说明 | 文字说明补充澄清 |
| 归集范围 | 含/不含某类资产 |
| 数据来源系统 | 投资管理系统 → +估值系统 |
| 报送频率 | 月报 → 季报 |
| 机构范围 | 全部金融机构 → 仅商业银行 |

## 6. API

### 6.1 制度版本

```
POST   /api/regimes                                   # 创建
GET    /api/regimes?reporting_system_code=1104        # 列表
```

### 6.2 修订条目

```
POST   /api/revisions                                  # 创建单条
POST   /api/revisions/bulk                             # 批量上传（Excel 解析输出）
GET    /api/revisions?regime_version=&report_code=&field_code=&review_status=
GET    /api/revisions/cumulative?report_code=          # 累计视图
GET    /api/revisions/{revision_id}                    # 详情
PATCH  /api/revisions/{revision_id}/review             # 改 review_status
```

**注意：没有 `analyze-from-revisions` —— 影响分析与修订对照表解耦。**

## 7. 前端方案（A：CatalogView 加 Tab）

```
报表目录页 (现有 CatalogView)
├─ Tab1: 报表对象（既有）
├─ Tab2: 指标项（既有）
├─ Tab3: 字段目录（既有）
├─ Tab4: 数据血缘（既有）
└─ Tab5: 修订对照表（新增）⭐
    ├─ 顶部筛选：制度版本 / 报表 / 状态
    ├─ 表格列：
    │   变更ID | 报表 | 字段名 | 变更类型 | 变更摘要 | 维度 | 影响cell数 | 状态
    ├─ 点行 → 抽屉
    │   ├─ before/after 对比视图（左右双栏）
    │   ├─ affected_cells 展开列表（可跳转字段定位页）
    │   ├─ 监管原文（regulation_evidence + 原文锚点）
    │   └─ 编辑模式（DRAFT 状态可编辑，CONFIRMED 只读）
    └─ 顶部操作：新建 / 导入 Excel / 导出 Excel
```

**复用既有组件：**
- 表格、筛选条、抽屉样式直接复用 CatalogView
- 跳转字段定位：复用之前实现的 `view-lineage` 事件

## 8. 实施阶段

### 阶段 1 · 数据模型与 API ✅ 已完成

| # | 交付物 | 状态 |
|---|---|---|
| ① | `RegimeVersion` + `RegulatoryRevision` ORM（含 17 列，含 `change_summary` + `source_document_id`） | ✅ |
| ② | Pydantic schemas + 6 个 CRUD endpoint | ✅ |
| ③ | G31 mock：1 个 regime + 8 条字段级修订 | ✅ |
| ④ | Excel 测试文件：`backend/data/G31_修订对照表_v2_2026Q1.xlsx` | ✅ |

### 阶段 1.5 · 前端 Tab 展示（**下一步**）

| # | 交付物 | 估时 |
|---|---|---|
| ⓐ | CatalogView 新增"修订对照表" Tab | 0.5d |
| ⓑ | 列表视图：表格 + 筛选 + 变更摘要 chip 展示 | 0.5d |
| ⓒ | 详情抽屉：before/after 对比 + affected_cells 展开 + 原文 | 1d |
| ⓓ | 编辑表单：DRAFT 状态可改，CONFIRMED 只读 | 0.5d |

合计 **2.5 天**。

### 阶段 2 · zip 包自动抽取（**未来工作，本期不做**）

| # | 交付物 | 说明 |
|---|---|---|
| ⑥ | `zip_revision_extractor.py` | 解 zip + 文件类型分发器 |
| ⑦ | `regime_excel_differ.py` | 新旧表样 Excel diff |
| ⑧ | `instruction_change_llm.py` | LLM 抽取填报说明 |
| ⑨ | `POST /api/regimes/{version}/extract-from-zip` | 一键解析入库 |

### 阶段 3 · 高级功能（远期）

- Excel 在线编辑/原文 PDF 高亮跳转
- 修订对照表 → 影响分析的双向关联（按需开启）
- 字段生命周期视图（NEW → MODIFY → MODIFY → DELETE 追溯）
- 多体系适配（EAST 5.0 数据元字典对接）

## 9. 测试数据

### 9.1 Mock 数据

`backend/scripts/seed_g31_revisions_v2.py` 灌入：
- 1 条制度版本：`1104-2026Q1-v2`
- 8 条字段级修订（覆盖 NEW/MODIFY/DELETE 三种类型，6 种 change_dimension）

### 9.2 Excel 测试文件

`backend/data/G31_修订对照表_v2_2026Q1.xlsx`，3 个 sheet：

1. **制度版本**：单条制度元数据
2. **修订对照表**：8 条字段级修订，按 17 列布局，变更类型有颜色标识
3. **字段说明**：每列的类型 + 说明，便于业务方理解

可用作：
- 主流程测试上传（未来上传 → 解析 → 入库的入口）
- 给业务/数据治理团队当沟通模板
- 给监管或审计当归档物

## 10. 文件清单（阶段 1 最终态）

**新增（5 文件）：**
```
backend/app/api/routes_revisions.py                    # 6 CRUD endpoint
backend/scripts/seed_g31_revisions_v2.py               # mock 8 条
backend/scripts/export_g31_revisions_to_xlsx.py        # Excel 导出
backend/data/G31_修订对照表_v2_2026Q1.xlsx              # 测试 Excel
docs/field-level-revision-table-redesign.md            # 本文档
```

**修改（4 文件）：**
```
backend/app/models/db_models.py                        # RegimeVersion + RegulatoryRevision 两张表
backend/app/models/schemas.py                          # 4 个 schema
backend/app/main.py                                    # 注册 routes_revisions router
backend/app/core/database.py                           # init_db 增量列兼容
```

**未动（主流程完整保留）：**
```
backend/app/services/reporting_change_extractor.py     # 不动
backend/app/services/reporting_impact_analyzer.py      # 不动（已删 analyze_from_revisions）
backend/app/api/routes_tasks.py                        # /analyze-impact 维持原状
frontend/                                              # 阶段 1 完全不动前端
```

## 11. 业界参考

- [1104 监管报表全解析（亿信华辰）](https://www.esensoft.com/industry-news/data-governance-52491.html)
- [2026 年 1104 报表新规解读（知乎）](https://zhuanlan.zhihu.com/p/1991165545026965719)
- [银行业金融机构监管数据标准化规范 EAST5.0 解读](https://www.jrwenku.com/46253.html)
- [EAST5.0 正式发布 — 德勤中国](https://www2.deloitte.com/cn/zh/pages/risk/articles/east-5-release.html)
- [统一监管合规平台 — 广电运通](https://www.gientech.com/product/regulation-reportings.html)
