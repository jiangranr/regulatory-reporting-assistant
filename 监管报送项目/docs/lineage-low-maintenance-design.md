# 痛点改造：血缘低维护设计

> 更新日期：2026-05-30  
> 文档定位：针对"业务觉得每个概念和血缘都要手动维护太麻烦"这一核心痛点，设计铺底策略和监管驱动的自动更新机制。

---

## 1. 痛点描述

当前模式要求业务人员：

1. 为每个报送字段手动登记概念定义
2. 逐条维护字段与源系统的血缘关系
3. 当监管发文修改口径时，自行判断哪些血缘受影响并更新

这导致知识库长期处于"只有演示数据、没有真实覆盖"的状态。业务愿意用工具，但不愿意先喂数据。

---

## 2. 改造方向

将"维护"拆成两个阶段：

```text
一次性铺底  ──────────────────────────────────────────→  监管驱动增量更新
（冷启动：从现有报表/规范中批量导入，业务只做确认）     （变更驱动：监管发文变化时自动检测差异、路由工单）
```

两段合在一起，业务从"事前录入"变成"事后确认"，心理负担从根上减轻。

---

## 3. 一次性铺底（冷启动）

### 3.1 目标

用一次性的半自动流程，将已有监管报表的字段和候选血缘批量导入知识库，达到 80% 以上覆盖率。剩余 20% 通过后续工单兜底。

### 3.2 铺底流程

数据源：直接对接监管系统（定期拉取字段目录 / 报表模板），不依赖手工上传文件。

```text
对接监管系统 → 拉取最新字段目录（字段名 / 含义 / 格式 / 适用机构范围）
  ↓
LLM 结构化处理 → 统一成内部字段目录格式
  ↓
语义匹配 → 与内部数据资产目录做字段匹配（精确 / 语义 / 无匹配）
  ↓
生成候选血缘列表（标注信心分）
  ↓
批量审核界面（业务一次性过审，而不是逐条录入）
  ↓
业务确认后直接写入知识库 / 低信心项 + 未匹配项 → 生成"待补录"工单
```

### 3.3 批量审核界面设计原则

- 业务确认后直接写库，无需额外审批流
- 按信心分排序：高信心项置顶，默认选中，业务"一键全部确认"即可
- 低信心项高亮，要求业务显式勾选确认或手动修改
- 未匹配字段单独列出，直接生成待补录工单，不阻塞其余项目的确认
- 整个审核过程可中断保存，不要求一次完成

### 3.4 信心分计算参考维度

| 维度 | 示例 |
|---|---|
| 字段名精确匹配 | "贷款余额" = "贷款余额" → 最高分 |
| 别名 / 近义词匹配 | "贷款余额" ≈ "信贷余额" → 高分 |
| 字段含义语义相似度 | 描述向量余弦 > 0.9 → 中高分 |
| 量级单位一致 | 都是"万元" → 加分 |
| 历史工单有过相同映射 | 有已闭合工单记录同一映射 → 加分 |
| 多个候选源字段 | 存在歧义 → 降分，标记"需人工判断" |

---

## 4. 监管驱动的增量更新

### 4.1 触发时机

现有流程中业务已经会上传新监管文件（发文 / 填报说明 / 表样）。在解析完文件之后，新增一个步骤：**与知识库中现有的字段目录做版本对比**，输出变更清单，再按规则路由工单。

### 4.2 变更检测

```text
新版监管文件
  ↓ LLM 解析
新版字段目录（字段名 / 含义 / 格式 / 适用范围 / 报送频度）
  ↓ 与知识库中"当前生效版本"对比
变更清单（新增 / 删除 / 修改 三类）
```

字段对比的粒度：字段名 + 所在报表 + 机构适用范围，三者合在一起作为唯一键。

### 4.3 工单路由规则

> **核心约束（来自业务明确要求）**：
> - 新增字段：**无论是否命中知识库，都必须生成工单**
> - 删除 / 变更字段：**只有命中知识库才生成工单**

| 变更类型 | 命中知识库？ | 生成工单？ | 工单状态 | 备注 |
|---|---|---|---|---|
| 新增字段 | 命中（有候选血缘）| ✅ 生成 | `候选血缘待审核` | 预填匹配到的候选源字段 |
| 新增字段 | 未命中 | ✅ 生成 | `来源待补录` | 血缘为空，优先级=高；这是最危险的盲区 |
| 删除字段 | 命中 | ✅ 生成 | `血缘退役待确认` | 附带影响分析：哪些下游依赖此字段 |
| 删除字段 | 未命中 | ❌ 不生成 | — | 无血缘无需清理，仅记录系统日志 |
| 变更字段 | 命中 | ✅ 生成 | `口径变更待审核` | 展示字段含义前后 diff |
| 变更字段 | 未命中 | ✅ 生成（告警型）| `隐藏血缘告警` | 字段仍在监管要求中但无血缘记录，可能漏录，自动开工单提醒排查 |

### 4.4 告警型工单说明

"变更字段未命中知识库"场景下，工单类型标记为 `隐藏血缘告警`，区别于普通工单的处理方式：

- 优先级默认设为高
- 工单描述说明：该字段在新监管文件中发生变更，但知识库中无血缘记录，可能存在漏录情况
- 建议操作项：① 排查是否确实无需血缘；② 若有隐藏血缘，补录后关闭工单；③ 若确认无需维护，标记忽略并注明原因
- 告警型工单同样走正常工单队列，不单独拉起通知，避免干扰

### 4.5 "命中知识库"的判断

命中 = 在知识库中找到同一字段的血缘记录（精确匹配字段名 + 报表）。

> 注：告警型工单（变更未命中）也在此判断后触发，不是另一套入口。

命中不要求血缘是正确的，只要求存在。如果存在但不确定是否正确，工单本身就是确认机制。

### 4.6 删除字段的影响范围分析

删除字段工单需要额外附上：

```text
字段 X 即将退役，当前知识库中的影响：
  - 直接映射该字段的源系统字段：[A表.a_col, B表.b_col]
  - 引用该字段口径的规则：[规则 R1, R2]
  - 历史已闭合工单中涉及此字段：[工单 #123, #456]

建议操作：
  □ 确认以上源字段映射是否需要同步下线
  □ 确认规则 R1/R2 是否需要修改或退役
```

### 4.7 变更字段的口径 diff 展示

```text
字段：贷款余额（G01_0001_C01）

变更前：包含正常类、关注类贷款余额，不含核销
变更后：包含正常类、关注类、次级类贷款余额，不含核销

差异：新增"次级类"覆盖范围 ← 高亮显示

当前血缘：信贷系统.loan_balance → 可能受影响，请确认取数口径是否需要调整
```

---

## 5. 关键数据结构补充

### 5.1 监管字段目录（新增版本管理）

现有知识库的字段记录需要补充：

```
字段记录：
  - 字段名
  - 所属报表 / 体系
  - 生效版本（关联到监管文件版本）
  - 当前状态：生效 / 待审核 / 已退役
  - 最后一次人工确认时间 + 确认人
```

### 5.2 变更日志

```
变更记录：
  - 变更来源文件（监管文件 ID）
  - 变更类型：新增 / 删除 / 修改
  - 变更前后快照
  - 是否命中知识库
  - 关联工单 ID（若有）
  - 处理状态：已处理 / 已忽略 / 告警中
```

---

## 6. 与现有流程的衔接

当前上传监管发文的主流程：

```text
上传文件 → 条款提取 → 语义识别 → 影响分析 → 生成工单
```

改造后，在"语义识别"之后插入新步骤：

```text
上传文件 → 条款提取 → 语义识别
                          ↓
                    ┌─ 原有：条款级影响分析（规则 / 业务对象）
                    └─ 新增：字段目录版本对比 → 变更清单 → 按规则路由工单
```

两条线并行，不替换现有逻辑，只新增字段粒度的检测分支。

---

## 7. 现有代码现状（实现前摸底）

> 2026-05-30 对照代码库确认，避免重复造轮子。

| 组件 | 现状 | 缺什么 |
|---|---|---|
| `ReportingItemLineage` 表 | 表结构存在，`mapping_status` 字段有 DRAFT | **种子数据从未写入 DB**，只在内存用 |
| `ReportingSeedCatalog.lineage` | 有完整的 1104 血缘种子数据 | 没有任何代码把它 persist 到 DB |
| `POST /tasks/{id}/impact-review/confirm` | 可以 `status=CONFIRMED`，并生成工单草稿 | confirm 后**没有回写 `ReportingItemLineage`** |
| `RegReportingChangeCandidate` | 有 `change_type` 字段 | 无字段版本对比逻辑，无六路由工单生成 |
| `TicketDraft` | 有完整工单字段 | **无独立 `status` 字段**，无"工单确认→影响血缘"入口 |

---

## 8. 实现规划

实施顺序依赖关系：**A → B → C1+C2 → C3+C4 → D**

### Step A：种子血缘写入 DB（铺底基础）

**背景**：Demo 所有场景的前提，没有这一步血缘表永远是空的。

**要做的事**：

在 `catalog_ingestor.py`（或新建 `lineage_seed_writer.py`）加函数：

```python
def ingest_lineage_from_seed(catalog: ReportingSeedCatalog, session) -> int:
    # 对每条 lineage 行：
    #   resolve item_code → RegReportingItem.id
    #   resolve data_field_code → DataFieldCatalog.id
    #   upsert ReportingItemLineage(mapping_status="SEED_CONFIRMED")
    # 返回写入条数
```

在 seed 初始化入口调用（现有 init endpoint 或 startup hook）。

`mapping_status` 枚举补充：`SEED_CONFIRMED / CONFIRMED / RETIRED / DRAFT`（在 `enums.py` 补）。

**影响文件**：
- `services/catalog_ingestor.py`（或新建 `services/lineage_seed_writer.py`）
- `models/enums.py`（补枚举）
- init endpoint（调用入口）

---

### Step B：审核确认写回血缘（审核闭环）

**背景**：现有 confirm 只存状态、生成工单草稿，血缘表完全不动。

**要做的事**：

在 `impact_review_service.py` 新增：

```python
def apply_confirmed_review_to_lineage(review: dict, session) -> LineageApplyResult:
    # 遍历 review.items：
    #   item.removed=True → 该指标所有血缘 mapping_status=RETIRED
    #   field selected=True, removed=False, source="AI" → upsert, mapping_status=CONFIRMED
    #   field removed=True / selected=False → mapping_status=RETIRED
    #   field source="BUSINESS" → 新建 ReportingItemLineage, mapping_status=CONFIRMED
    # 返回 {confirmed_count, retired_count, created_count}
```

在 `routes_tasks.py` 的 `confirm_impact_review` confirm 成功后调用，结果附加进响应。

**影响文件**：
- `services/impact_review_service.py`（新增函数）
- `api/routes_tasks.py`（`confirm_impact_review` 补调用）

---

### Step C1：字段变更记录数据模型

在 `db_models.py` 新增：

```python
class RegFieldChangeRecord(SQLModel, table=True):
    __tablename__ = "reg_field_change_records"

    id: int | None
    task_id: int              # 关联监管文件任务
    reporting_item_code: str  # 变更的报送字段编码
    item_name: str
    change_type: str          # ADDED / DELETED / MODIFIED
    before_snapshot: str      # JSON，变更前字段定义
    after_snapshot: str       # JSON，变更后字段定义
    library_hit: bool         # 是否命中 reporting_item_lineage
    ticket_id: int | None     # 生成的工单 ID（若有）
    status: str               # PENDING / TICKET_GENERATED / IGNORED / ALERT
    created_at: datetime
```

**影响文件**：`models/db_models.py`

---

### Step C2：字段变更检测服务

新建 `services/field_change_detector.py`：

```python
def detect_field_changes(old_items: list[dict], new_items: list[dict]) -> list[FieldChange]:
    # 按 item_code 做 diff → 识别 ADDED / DELETED / MODIFIED

def check_library_hit(item_code: str, session) -> bool:
    # 查 RegReportingItem + ReportingItemLineage
    # 有血缘记录（任意 mapping_status）= 命中
```

Demo 阶段：`old_items` 来自 DB 中现有种子数据，`new_items` 来自模拟的"新版监管字段"种子，对接监管系统抽数留到生产阶段。

**新建文件**：`services/field_change_detector.py`

---

### Step C3：六路由工单生成服务

新建 `services/field_change_ticket_router.py`，实现路由矩阵：

```python
def route_field_change_to_ticket(
    change: RegFieldChangeRecord,
    session,
) -> TicketDraft | None:
    match (change.change_type, change.library_hit):
        case ("ADDED", True):
            # DATA_MAPPING 类型工单，预填候选血缘
        case ("ADDED", False):
            # LINEAGE_BUILD 类型工单，高优先级，血缘待补录
        case ("DELETED", True):
            # LINEAGE_BUILD 类型工单，附影响分析（下游血缘+规则）
        case ("DELETED", False):
            # 不生成工单，RegFieldChangeRecord.status=IGNORED
            return None
        case ("MODIFIED", True):
            # DATA_MAPPING 类型工单，附口径 diff
        case ("MODIFIED", False):
            # LINEAGE_BUILD 高优先级告警型工单（隐藏血缘告警）
```

**新建文件**：`services/field_change_ticket_router.py`

---

### Step C4：字段变更 API 端点

在 `api/routes_tasks.py` 新增：

```
POST /tasks/{id}/field-changes/detect
    → 触发字段变更检测，写入 RegFieldChangeRecord

GET  /tasks/{id}/field-changes
    → 返回变更清单（含 library_hit、status、ticket_id）

POST /tasks/{id}/field-changes/route-tickets
    → 按矩阵对所有 PENDING 记录生成工单
```

**影响文件**：`api/routes_tasks.py`（新增 3 个端点）

---

### Step D：工单确认影响血缘（最后一公里）

**背景**：字段变更工单被业务确认/关闭后，要真正更新血缘表。

`TicketDraft` 补 `status` 字段（`OPEN / CONFIRMED / CLOSED / IGNORED`）。

新增端点：

```
POST /tasks/{task_id}/tickets/{ticket_id}/confirm
    → TicketDraft.status = CONFIRMED
    → 根据 action_ticket_type 决定血缘操作：
        LINEAGE_BUILD（新增）→ 创建 ReportingItemLineage, mapping_status=CONFIRMED
        DATA_MAPPING（变更）→ 更新已有记录, mapping_status=CONFIRMED
        DELETED 相关工单  → mapping_status=RETIRED
```

**影响文件**：
- `models/db_models.py`（`TicketDraft` 补 `status`）
- `api/routes_tasks.py`（新增 confirm 端点）

---

## 9. 分阶段交付目标

| 阶段 | 步骤 | 交付目标 |
|---|---|---|
| P0 铺底 | A | Demo 能看到真实血缘数据，不再是空表 |
| P1 审核闭环 | B | 业务点击"确认"后血缘状态真正更新，Review → Lineage 打通 |
| P2 变更检测 | C1+C2 | 能识别两个版本之间的字段新增/删除/修改 |
| P3 变更工单 | C3+C4 | 监管发文变化自动推送六类工单，业务不用手动发现 |
| P4 闭环 | D | 工单确认后血缘自动更新，全链路贯通 |

---

## 10. 与业务沟通的验收话术

> "以前你们每次监管发文都要自己对照着找哪些字段改了、再手动改血缘。
> 现在是这样的：我们替你解析文件、找出哪些字段新增了/删除了/改了。
> 新增字段不管有没有查到来源，都帮你开一张工单；
> 删除和变更字段，只要我们库里有记录，就自动帮你分析影响范围，你只需要点确认。
> 你需要做的事情只剩下：审核、拍板。"
