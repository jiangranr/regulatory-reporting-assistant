# 报表目录 Zip 上传与解析设计文档

- 日期：2026-05-19
- 状态：待实施
- 版本：v1

---

## 背景

当前系统通过 `POST /api/reporting/seed-1104` 手动初始化报表目录，无法追踪报表版本，也不支持业务人员自主维护。

监管局下发的附件目录（如"附件4：报表表样和填报说明汇总"）本身就是结构化的：
- 目录名区分新增 / 修订 / 机构类
- 每张报表一个子文件夹，含 Excel 表样 + Doc 填报说明
- 文件名中嵌有版本号（如 `G31(251).xls` → 版本 251）

本方案支持业务人员将该目录压缩成 zip 一次性上传，系统自动解析所有报表并入库。

---

## 范围

- 一期目标：支持 zip 上传 → 批量解析 → 全量入库（不做历史版本 diff）
- 本方案与现有监管发文流水线（`/api/documents/` + `/api/tasks/`）完全独立
- 本方案为"报表目录基础数据维护"，是影响分析的数据基础

---

## 目录结构规则

zip 包内的顶层目录名决定每张报表的元信息，**只做关键词匹配，不要求全匹配**：

| 目录名包含关键词 | change_type |
|----------------|-------------|
| 含 `新增` | NEW |
| 含 `修订` | MODIFIED |
| 含 `填报说明` 且不含 `新增`/`修订` | INSTRUCTION_ONLY |
| 其他 | NEW（默认兜底） |

解析示例：
- `1.新增报表（基础类、业务类、支持发展类）` → NEW
- `2.修订报表（基础类、业务类、支持发展类）` → MODIFIED
- `5.填报说明及其他调整` → INSTRUCTION_ONLY
- `6.分支机构报表` → NEW（兜底）

这样即使监管局将来调整目录编号或分类文字，解析规则仍然稳健。

每个报表子文件夹（如 `G31/`）包含：
- Excel 文件：`G31(251).xls` → 表样
- Doc 文件：`G31填报说明（251）.doc` → 填报说明

版本号从文件名括号内自动解析：`G31(251).xls` → `version_label = "251"`

---

## 数据库设计

### 新增表（2 张批次追踪表）

```sql
reg_catalog_batches
  id                    INTEGER PRIMARY KEY
  batch_code            VARCHAR(50) UNIQUE        -- 如 BATCH_20260519_001
  source_zip_filename   VARCHAR(500)              -- 上传的 zip 原始文件名
  source_document_ref   VARCHAR(255)              -- 来源文件（如"金发〔2024〕39号"，选填）
  version_label         VARCHAR(20)               -- 从文件名自动解析，如 "251"
  total_count           INTEGER DEFAULT 0
  done_count            INTEGER DEFAULT 0
  fail_count            INTEGER DEFAULT 0
  status                VARCHAR(30)               -- PENDING / PROCESSING / DONE / PARTIAL_FAIL
  created_at            DATETIME
  finished_at           DATETIME

reg_catalog_batch_items
  id                    INTEGER PRIMARY KEY
  batch_id              INTEGER NOT NULL
  object_code           VARCHAR(50)               -- G31 / G04 …
  change_type           VARCHAR(30)               -- NEW / MODIFIED / INSTRUCTION_ONLY
  table_category        VARCHAR(50)               -- 基础类 / 业务类 / 机构类 / 分支机构
  excel_filename        VARCHAR(500)
  doc_filename          VARCHAR(500)
  parse_status          VARCHAR(30)               -- PENDING / PARSING / DONE / FAILED
  parse_error           TEXT
  change_summary        TEXT                      -- LLM 提取的本次变更摘要
  items_count           INTEGER DEFAULT 0         -- 解析出的 reporting_items 数量
  created_at            DATETIME
  finished_at           DATETIME
```

### 新增表（5 张报表结构表）

```sql
reg_reporting_templates          -- 表样版本实例（sheet 级）
  id, template_code, object_code, section_code
  batch_item_id, version_label
  sheet_name, source_file, status, created_at

reg_reporting_template_cells     -- 原始单元格（保留 Excel 原始坐标）
  id, template_id, sheet_name
  row_index, col_index, excel_ref
  raw_text, cell_type            -- DATA_CELL / HEADER_CELL / MERGED_CELL
  style_json                     -- { rgb, role: FILLABLE/DERIVED/NO_DATA }
  merge_json                     -- 合并单元格范围
  created_at

reg_reporting_dimensions         -- 行维度 / 列维度定义
  id, object_code, dimension_code, dimension_name
  axis                           -- ROW / COLUMN
  status, created_at

reg_reporting_dimension_members  -- 行项目 / 列头成员（含层级）
  id, dimension_id, member_code, member_name
  parent_member_id, level_no, display_order
  source_cell_ref, metadata_json
  status, created_at

reg_reporting_item_dimensions    -- 指标项 × 维度成员映射
  id, reporting_item_id, dimension_id, member_id
  axis, display_order
```

### 现有表扩展字段

`reg_reporting_items` 新增：
```
batch_item_id       INTEGER   -- 关联到哪次上传的 batch_item
change_status       VARCHAR(20)  -- NEW / MODIFIED / UNCHANGED
```

`reg_reporting_objects` 新增：
```
change_type               VARCHAR(30)   -- NEW / MODIFIED
table_category            VARCHAR(50)   -- 基础类 / 业务类 / 机构类
current_version_label     VARCHAR(20)   -- 当前已入库版本号，如 "251"
latest_batch_item_id      INTEGER       -- 最近一次成功导入的 batch_item
```

---

## 后端解析流水线

### 处理流程

```
POST /api/catalog/upload-zip
  │
  ├─ 1. 解压 zip 到临时目录（/tmp/catalog_batch_{uuid}/）
  ├─ 2. zip_scanner：扫描目录结构
  │      - 解析顶层目录名 → change_type / table_category
  │      - 识别报表子文件夹 → object_code
  │      - 匹配 Excel + Doc 文件，解析 version_label
  │
  ├─ 3. 创建 reg_catalog_batches（状态 PENDING）
  │      + 创建所有 reg_catalog_batch_items（状态 PENDING）
  │
  ├─ 4. 返回 { batch_id, batch_code, version_label, total_count }
  │
  └─ 5. FastAPI BackgroundTask 逐表处理：
         for each batch_item:
           ├─ 5a. excel_parser（读 xls/xlsx）
           │       → reg_reporting_template_cells（原始单元格）
           │       → reg_reporting_dimensions + dimension_members（行列维度）
           │       → reg_reporting_items（每个有效格一条，含 item_code）
           │       → reg_reporting_item_dimensions（指标项×维度映射）
           │       → reg_reporting_rules（从核对关系区块提取）
           │
           ├─ 5b. doc_parser（读 doc/docx）
           │       → 提取全文 → reg_reporting_instructions（全文存库）
           │       → 调 LLM：提取变更摘要 → batch_item.change_summary
           │
           ├─ 5c. 更新 reg_reporting_objects（change_type / version_label）
           ├─ 5d. 更新 batch_item.parse_status = DONE，items_count
           └─ 5e. 更新 batch.done_count++（原子操作）
```

### 容错策略

- 某张表 Excel 解析失败 → batch_item 标 FAILED，parse_error 记录原因，不影响其他表
- LLM 调用失败 → change_summary 存空字符串，不阻塞入库流程
- 5.填报说明及其他调整 目录（无 Excel） → 只跑 doc_parser，batch_item 标 INSTRUCTION_ONLY
- 临时目录在批次完成后统一清理

### 新增服务模块

| 文件 | 职责 |
|------|------|
| `app/services/zip_scanner.py` | 解压 zip，扫描目录，输出每张表的文件路径和元信息 |
| `app/services/excel_parser.py` | 读 xls/xlsx，输出 template_cells / dimension_members / items |
| `app/services/doc_parser.py` | 读 doc/docx，提取全文 + 调 LLM 生成 change_summary |
| `app/services/catalog_ingestor.py` | 编排上述三个解析器，管理事务写库，更新 batch 进度 |

---

## API 设计

```
POST   /api/catalog/upload-zip
       请求：multipart/form-data
         file                 .zip 文件（必填）
         source_document_ref  来源文件说明（选填，如"金发〔2024〕39号"）
       响应：{ batch_id, batch_code, version_label, total_count, status }

GET    /api/catalog/batches
       响应：批次列表（倒序），含 status / done_count / fail_count / version_label / created_at

GET    /api/catalog/batches/{batch_id}
       响应：批次详情 + 所有 batch_items 列表
       用途：前端轮询，每 2 秒一次，直到 status = DONE / PARTIAL_FAIL

GET    /api/catalog/batches/{batch_id}/items/{object_code}
       响应：单张报表解析结果预览
         change_summary, items_count, 前 20 条 reporting_items

GET    /api/catalog/objects?version_label=251
       响应：已入库报表对象列表（支持版本过滤）

GET    /api/catalog/objects/{object_code}/items?section_code=PART_I
       响应：该报表指定分区的全部指标项
```

---

## 前端页面

新增独立页面 **"报表目录"**（`CatalogUploadView`），挂在导航栏与"发文任务"平级。

### 页面布局

```
┌─────────────────────────────────────────────────┐
│ 报表目录维护                                      │
├─────────────────────────────────────────────────┤
│ [选择 zip 文件]  来源文件（选填）：____________    │
│ [开始上传解析]                                    │
├─────────────────────────────────────────────────┤
│ 当前版本：251版  导入时间：2026-05-19  共 22 张   │
│ 进度：18 / 22 完成  |  1 失败                    │
│                                                 │
│ ✅ G31  投资业务情况表   168项  变更：新增穿透后列  │
│ ✅ G04  资产质量情况表   203项  变更：调整分档口径  │
│ ⏳ G11_I  解析中...                              │
│ ❌ G19   解析失败  [查看错误]  [重试]             │
│                                                 │
│ [查看已入库报表目录]                              │
└─────────────────────────────────────────────────┘
```

### 前端轮询逻辑

```typescript
// 上传后立即开始轮询
const { batch_id } = await apiClient.uploadCatalogZip(file, sourceRef)

const poll = setInterval(async () => {
  const batch = await apiClient.getCatalogBatch(batch_id)
  batchProgress.value = batch
  if (batch.status === 'DONE' || batch.status === 'PARTIAL_FAIL') {
    clearInterval(poll)
  }
}, 2000)
```

### 新增 API Client 方法

```typescript
uploadCatalogZip(file: File, sourceRef?: string): Promise<CatalogBatch>
getCatalogBatch(batchId: number): Promise<CatalogBatchDetail>
listCatalogBatches(): Promise<CatalogBatch[]>
```

---

## 依赖库

| 库 | 用途 |
|----|------|
| `xlrd` | 读取旧版 .xls（openpyxl 不支持 xls） |
| `openpyxl` | 读取 .xlsx |
| `python-docx` | 读取 .docx |
| `antiword` / `textract` | 读取旧版 .doc（二进制格式，需系统工具） |

> 注意：本地有 .doc 文件（非 .docx），需要额外处理旧格式。建议用 `subprocess` 调用系统 `antiword` 或 `libreoffice --headless` 转换。

---

## 不在本期范围内

- 历史版本 diff（v2 再做）
- 单张报表的手动重新解析入口（v2）
- 与监管发文任务的关联（已有 reg_reporting_change_candidates 承接）
- 报表指标的人工编辑界面
