# 报表目录 Zip 上传与解析 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支持业务人员上传监管报表目录 zip 包，后台自动解析 Excel 表样 + Doc 填报说明，批量入库报表指标结构并生成 LLM 变更摘要。

**Architecture:** 用户 POST zip → 后端立即创建 `reg_catalog_batches` 记录并返回 `batch_id` → FastAPI `BackgroundTasks` 逐表处理（zip_scanner → excel_parser → doc_parser → catalog_ingestor 写库）→ 前端每 2 秒轮询 `GET /api/catalog/batches/{batch_id}` 查看进度。

**Tech Stack:** Python 3.11, FastAPI BackgroundTasks, SQLModel/MySQL, xlrd（.xls）, openpyxl（.xlsx）, python-docx（.docx）, soffice（.doc 旧格式转换）, Anthropic LLM（变更摘要）

---

## 文件清单

| 操作 | 路径 | 职责 |
|------|------|------|
| MODIFY | `app/models/db_models.py` | 新增 7 个模型类，扩展 2 个现有模型 |
| MODIFY | `app/models/schemas.py` | 新增 CatalogBatch / BatchItem 响应 schema |
| CREATE | `app/services/zip_scanner.py` | zip 解压 + 目录扫描 → `ReportFileSet` 列表 |
| CREATE | `app/services/excel_parser.py` | xls/xlsx → template_cells / dimension_members / items |
| CREATE | `app/services/doc_parser.py` | doc/docx 文本提取 + LLM 变更摘要 |
| CREATE | `app/services/catalog_ingestor.py` | 编排三个解析器，管理事务写库，更新 batch 进度 |
| CREATE | `app/api/routes_catalog.py` | POST /upload-zip, GET /batches, GET /batches/{id} |
| MODIFY | `app/main.py` | 注册 routes_catalog router |
| CREATE | `tests/test_zip_scanner.py` | zip 扫描单元测试 |
| CREATE | `tests/test_excel_parser.py` | Excel 解析单元测试（用真实 G31 文件） |
| CREATE | `tests/test_doc_parser.py` | Doc 解析单元测试（mock LLM） |
| CREATE | `tests/test_catalog_api.py` | API 集成测试（TestClient + SQLite） |

---

## Task 1: 新增数据库模型

**Files:**
- Modify: `app/models/db_models.py`

- [ ] **Step 1: 在 db_models.py 末尾追加 7 个新模型类**

在文件末尾（`class ReviewRecord` 之后）追加：

```python
class RegCatalogBatch(SQLModel, table=True):
    __tablename__ = "reg_catalog_batches"

    id: int | None = Field(default=None, primary_key=True)
    batch_code: str = Field(index=True, unique=True)
    source_zip_filename: str = ""
    source_document_ref: str = ""
    version_label: str = ""
    total_count: int = 0
    done_count: int = 0
    fail_count: int = 0
    status: str = "PENDING"   # PENDING / PROCESSING / DONE / PARTIAL_FAIL
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class RegCatalogBatchItem(SQLModel, table=True):
    __tablename__ = "reg_catalog_batch_items"

    id: int | None = Field(default=None, primary_key=True)
    batch_id: int = Field(index=True)
    object_code: str = Field(index=True)
    change_type: str = ""          # NEW / MODIFIED / INSTRUCTION_ONLY
    table_category: str = ""
    excel_filename: str = ""
    doc_filename: str = ""
    parse_status: str = "PENDING"  # PENDING / PARSING / DONE / FAILED
    parse_error: str = Field(default="", sa_column=Column(Text))
    change_summary: str = Field(default="", sa_column=Column(Text))
    items_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None


class RegReportingTemplate(SQLModel, table=True):
    __tablename__ = "reg_reporting_templates"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    batch_item_id: int | None = Field(default=None, index=True)
    template_code: str = Field(index=True, unique=True)
    template_name: str
    version_label: str = ""
    sheet_name: str = ""
    source_file: str = Field(default="", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingTemplateCell(SQLModel, table=True):
    __tablename__ = "reg_reporting_template_cells"

    id: int | None = Field(default=None, primary_key=True)
    template_id: int = Field(index=True)
    sheet_name: str = ""
    row_index: int = 0
    col_index: int = 0
    excel_ref: str = ""            # "D8"
    raw_text: str = Field(default="", sa_column=Column(Text))
    cell_type: str = ""            # FILLABLE / DERIVED / NO_DATA / HEADER
    style_json: str = Field(default="{}", sa_column=Column(Text))
    merge_json: str = Field(default="{}", sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingDimension(SQLModel, table=True):
    __tablename__ = "reg_reporting_dimensions"

    id: int | None = Field(default=None, primary_key=True)
    reporting_object_id: int = Field(index=True)
    dimension_code: str = Field(index=True, unique=True)
    dimension_name: str
    axis: str = "ROW"              # ROW / COLUMN
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingDimensionMember(SQLModel, table=True):
    __tablename__ = "reg_reporting_dimension_members"

    id: int | None = Field(default=None, primary_key=True)
    dimension_id: int = Field(index=True)
    member_code: str = Field(index=True, unique=True)
    member_name: str
    parent_member_id: int | None = None
    level_no: int = 1
    display_order: int = 0
    source_cell_ref: str = ""
    metadata_json: str = Field(default="{}", sa_column=Column(Text))
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RegReportingItemDimension(SQLModel, table=True):
    __tablename__ = "reg_reporting_item_dimensions"

    id: int | None = Field(default=None, primary_key=True)
    reporting_item_id: int = Field(index=True)
    dimension_id: int = Field(index=True)
    member_id: int = Field(index=True)
    axis: str = "ROW"              # ROW / COLUMN
    display_order: int = 0
```

- [ ] **Step 2: 扩展 RegReportingItem 模型（在现有字段后追加）**

找到 `class RegReportingItem(SQLModel, table=True):` 定义，在 `status: str = "ACTIVE"` 行之后、`created_at` 之前追加：

```python
    # 新增字段（catalog zip 上传后填充）
    batch_item_id: int | None = Field(default=None, index=True)
    change_status: str = ""        # NEW / MODIFIED / UNCHANGED
    source_cell_ref: str = ""      # "D8"
    cell_role: str = ""            # FILLABLE / DERIVED / NO_DATA
    is_fillable: bool = True
    is_derived: bool = False
    data_type: str = "DECIMAL"
```

- [ ] **Step 3: 扩展 RegReportingObject 模型（在现有字段后追加）**

找到 `class RegReportingObject(SQLModel, table=True):` 定义，在 `status: str = "ACTIVE"` 行之后、`created_at` 之前追加：

```python
    # 新增字段（catalog zip 上传后填充）
    change_type: str = ""          # NEW / MODIFIED
    table_category: str = ""       # 目录文件夹名
    current_version_label: str = ""  # "251"
    latest_batch_item_id: int | None = None
```

- [ ] **Step 4: 启动后端，确认新表自动建立**

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run uvicorn app.main:app --reload
```

访问 http://127.0.0.1:8000/docs 无报错即可。然后检查 MySQL：

```bash
mysql -ureg_user -preg_pass_123 reg_reporting -e "SHOW TABLES LIKE 'reg_catalog%'; SHOW TABLES LIKE 'reg_reporting_template%'; SHOW TABLES LIKE 'reg_reporting_dim%'; SHOW TABLES LIKE 'reg_reporting_item_dim%';"
```

期望输出包含：`reg_catalog_batches`, `reg_catalog_batch_items`, `reg_reporting_templates`, `reg_reporting_template_cells`, `reg_reporting_dimensions`, `reg_reporting_dimension_members`, `reg_reporting_item_dimensions`

---

## Task 2: zip_scanner 服务

**Files:**
- Create: `app/services/zip_scanner.py`
- Create: `tests/test_zip_scanner.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_zip_scanner.py`：

```python
import io
import zipfile
from pathlib import Path

import pytest

from app.services.zip_scanner import (
    detect_change_type,
    extract_object_code,
    extract_version_label,
    scan_zip,
)


def test_detect_change_type_new():
    assert detect_change_type("1.新增报表（基础类、业务类、支持发展类）") == "NEW"


def test_detect_change_type_modified():
    assert detect_change_type("2.修订报表（基础类、业务类、支持发展类）") == "MODIFIED"


def test_detect_change_type_instruction_only():
    assert detect_change_type("5.填报说明及其他调整") == "INSTRUCTION_ONLY"


def test_detect_change_type_default():
    assert detect_change_type("6.分支机构报表") == "NEW"


def test_extract_version_label():
    assert extract_version_label("G31(251).xls") == "251"
    assert extract_version_label("G31填报说明（251）.doc") == "251"
    assert extract_version_label("G31.xls") == ""


def test_extract_object_code():
    assert extract_object_code("G31") == "G31"
    assert extract_object_code("G01_IV") == "G01_IV"
    assert extract_object_code("G11_I") == "G11_I"
    assert extract_object_code("S73养老领域相关情况统计表") == "S73"


def test_scan_zip(tmp_path: Path):
    # 构造测试 zip
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls", b"fake_xls")
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc", b"fake_doc")
        zf.writestr("1.新增报表（基础类、业务类、支持发展类）/G51境外业务/G51(251).xlsx", b"fake_xlsx")

    extract_to = tmp_path / "extracted"
    version_label, file_sets = scan_zip(zip_path, extract_to)

    assert version_label == "251"
    assert len(file_sets) == 2

    g31 = next(fs for fs in file_sets if fs.object_code == "G31")
    assert g31.change_type == "MODIFIED"
    assert g31.excel_path is not None
    assert g31.doc_path is not None

    g51 = next(fs for fs in file_sets if fs.object_code == "G51")
    assert g51.change_type == "NEW"
    assert g51.excel_path is not None
    assert g51.doc_path is None
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run pytest tests/test_zip_scanner.py -v 2>&1 | head -30
```

期望：`ModuleNotFoundError: No module named 'app.services.zip_scanner'`

- [ ] **Step 3: 实现 zip_scanner.py**

新建 `app/services/zip_scanner.py`：

```python
"""zip 目录扫描：解压 zip 包并识别每张报表的 Excel + Doc 文件对。"""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReportFileSet:
    object_code: str       # "G31"
    change_type: str       # "NEW" | "MODIFIED" | "INSTRUCTION_ONLY"
    table_category: str    # 顶层目录名，如"2.修订报表（基础类、业务类、支持发展类）"
    excel_path: Path | None
    doc_path: Path | None
    version_label: str     # "251"


def detect_change_type(folder_name: str) -> str:
    """从顶层目录名关键词推断 change_type，不做全匹配。"""
    if "新增" in folder_name:
        return "NEW"
    if "修订" in folder_name:
        return "MODIFIED"
    if "填报说明" in folder_name:
        return "INSTRUCTION_ONLY"
    return "NEW"


def extract_version_label(filename: str) -> str:
    """从文件名括号内提取版本号。'G31(251).xls' → '251'"""
    match = re.search(r'[（(](\d+)[）)]', filename)
    return match.group(1) if match else ""


def extract_object_code(folder_name: str) -> str:
    """从报表子文件夹名提取报表代码。'G31'、'S73养老…' → 'G31'、'S73'"""
    match = re.match(r'^([A-Z]\d+(?:_[A-Z0-9]+)?)', folder_name.strip())
    return match.group(1) if match else folder_name.strip()


def scan_zip(zip_path: Path, extract_to: Path) -> tuple[str, list[ReportFileSet]]:
    """
    解压 zip 并扫描目录结构，返回 (version_label, 报表文件集列表)。

    期望目录结构：
      <category_folder>/         ← 顶层：含"新增"/"修订"等关键词
        <report_folder>/         ← 报表代码目录，如 G31/
          G31(251).xls
          G31填报说明（251）.doc
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    file_sets: list[ReportFileSet] = []
    version_label = ""

    for category_dir in sorted(extract_to.iterdir()):
        if not category_dir.is_dir():
            continue

        change_type = detect_change_type(category_dir.name)

        for report_dir in sorted(category_dir.iterdir()):
            if not report_dir.is_dir():
                continue

            object_code = extract_object_code(report_dir.name)
            excel_path: Path | None = None
            doc_path: Path | None = None

            for f in report_dir.iterdir():
                if not f.is_file():
                    continue
                suffix = f.suffix.lower()
                if suffix in (".xls", ".xlsx") and excel_path is None:
                    excel_path = f
                    if not version_label:
                        version_label = extract_version_label(f.name)
                elif suffix in (".doc", ".docx") and doc_path is None:
                    doc_path = f
                    if not version_label:
                        version_label = extract_version_label(f.name)

            if excel_path or doc_path:
                file_sets.append(ReportFileSet(
                    object_code=object_code,
                    change_type=change_type,
                    table_category=category_dir.name,
                    excel_path=excel_path,
                    doc_path=doc_path,
                    version_label=version_label,
                ))

    return version_label, file_sets
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
uv run pytest tests/test_zip_scanner.py -v
```

期望：`6 passed`

---

## Task 3: excel_parser 服务

**Files:**
- Create: `app/services/excel_parser.py`
- Create: `tests/test_excel_parser.py`

G31(251).xls 颜色索引：`46=DERIVED(紫)`, `22=NO_DATA(灰)`, `9=FILLABLE(白)`, `64=auto默认`。

- [ ] **Step 1: 写失败测试（用真实 G31 文件）**

新建 `tests/test_excel_parser.py`：

```python
from pathlib import Path
import pytest
from app.services.excel_parser import parse_excel, ExcelParseResult

G31_XLS = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls")


@pytest.mark.skipif(not G31_XLS.exists(), reason="G31 file not available")
def test_parse_g31_basic():
    result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    # 模板单元格：G31 有 70 行 × 9 列
    assert len(result.template_cells) > 100
    # 至少有可填报指标项
    fillable = [item for item in result.items if item["cell_role"] == "FILLABLE"]
    assert len(fillable) > 10
    # 至少有派生指标项
    derived = [item for item in result.items if item["cell_role"] == "DERIVED"]
    assert len(derived) > 5
    # 有行维度成员
    row_members = [m for m in result.dimension_members if m["axis"] == "ROW"]
    assert len(row_members) > 5
    # 有列维度成员
    col_members = [m for m in result.dimension_members if m["axis"] == "COLUMN"]
    assert len(col_members) > 3


@pytest.mark.skipif(not G31_XLS.exists(), reason="G31 file not available")
def test_parse_g31_item_codes():
    result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    item_codes = {item["item_code"] for item in result.items}
    # item_code 格式：G31.PART_I.{row_slug}.{col_slug}
    assert any(code.startswith("G31.PART_I.") for code in item_codes)


def test_parse_excel_missing_file():
    with pytest.raises(FileNotFoundError):
        parse_excel(Path("/nonexistent/file.xls"), object_code="G99", section_code="PART_I")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_excel_parser.py -v 2>&1 | head -20
```

期望：`ModuleNotFoundError: No module named 'app.services.excel_parser'`

- [ ] **Step 3: 实现 excel_parser.py**

新建 `app/services/excel_parser.py`：

```python
"""Excel 表样解析器：从 .xls/.xlsx 提取 template_cells / dimension_members / reporting_items。"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import xlrd


# xlrd 颜色索引映射（基于 G31(251).xls 实测）
_DERIVED_COLOR_INDICES = {46}   # 紫色/lavender → DERIVED
_NO_DATA_COLOR_INDICES = {22}   # 灰色 → NO_DATA
_FILLABLE_COLOR_INDICES = {9}   # 纯白（显式） → FILLABLE
# color=64 为 auto（默认无填充），根据位置判断


@dataclass
class ExcelParseResult:
    template_cells: list[dict] = field(default_factory=list)
    dimension_members: list[dict] = field(default_factory=list)
    items: list[dict] = field(default_factory=list)
    item_dimensions: list[dict] = field(default_factory=list)


def _col_letter(col_idx: int) -> str:
    """0-based 列索引 → Excel 列字母。0→A, 3→D"""
    result = ""
    n = col_idx + 1
    while n:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _excel_ref(row: int, col: int) -> str:
    """0-based (row, col) → Excel 引用。(7, 3) → 'D8'"""
    return f"{_col_letter(col)}{row + 1}"


def _slugify(text: str) -> str:
    """将中文标签转为 item_code 片段。"""
    text = re.sub(r'[^\w一-鿿]', '_', text.strip())
    text = re.sub(r'_+', '_', text).strip('_')
    return text[:40] if text else "UNKNOWN"


def _cell_role_from_color(color_index: int, row: int, data_row_start: int,
                          col: int, data_col_start: int) -> str:
    """根据颜色索引和位置推断单元格角色。"""
    if color_index in _NO_DATA_COLOR_INDICES:
        return "NO_DATA"
    if color_index in _DERIVED_COLOR_INDICES:
        return "DERIVED"
    if color_index in _FILLABLE_COLOR_INDICES:
        return "FILLABLE"
    # color=64（auto）：在数据区域内视为 FILLABLE，否则 HEADER
    if row >= data_row_start and col >= data_col_start:
        return "FILLABLE"
    return "HEADER"


def _detect_data_boundary(sheet: xlrd.sheet.Sheet) -> tuple[int, int]:
    """
    自动检测数据区域起始行和起始列。
    启发式：找到第一行有数字值（ctype=2）的行，以及包含数字的最小列。
    """
    data_row_start = 7   # 默认（G31 数据从第 8 行起，0-indexed=7）
    data_col_start = 3   # 默认（G31 数据从 D 列起，0-indexed=3）

    for r in range(min(sheet.nrows, 20)):
        for c in range(sheet.ncols):
            cell = sheet.cell(r, c)
            if cell.ctype == xlrd.XL_CELL_NUMBER:
                data_row_start = r
                data_col_start = c
                return data_row_start, data_col_start

    return data_row_start, data_col_start


def parse_excel(
    file_path: Path,
    object_code: str,
    section_code: str = "PART_I",
) -> ExcelParseResult:
    """
    解析 .xls 文件，返回 ExcelParseResult。

    当前支持 .xls（xlrd）。.xlsx 文件在后续步骤中用 openpyxl 支持。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".xlsx":
        return _parse_xlsx(file_path, object_code, section_code)

    # .xls 使用 xlrd（需要 formatting_info=True 读取颜色）
    wb = xlrd.open_workbook(str(file_path), formatting_info=True)
    sheet = wb.sheet_by_index(0)
    sheet_name = sheet.name

    result = ExcelParseResult()
    data_row_start, data_col_start = _detect_data_boundary(sheet)

    # ── 1. 提取所有 template_cells ──────────────────────────────────────────
    merge_map: dict[tuple[int, int], dict] = {}
    for r1, r2, c1, c2 in sheet.merged_cells:
        for r in range(r1, r2):
            for c in range(c1, c2):
                merge_map[(r, c)] = {"r1": r1, "r2": r2, "c1": c1, "c2": c2}

    for row in range(sheet.nrows):
        for col in range(sheet.ncols):
            cell = sheet.cell(row, col)
            try:
                xfi = sheet.cell_xf_index(row, col)
                xf = wb.xf_list[xfi]
                color_index = xf.background.pattern_colour_index
            except Exception:
                color_index = 64

            role = _cell_role_from_color(color_index, row, data_row_start, col, data_col_start)
            raw_text = str(cell.value).strip() if cell.value else ""

            style = {"color_index": color_index, "role": role}
            merge = merge_map.get((row, col), {})

            result.template_cells.append({
                "sheet_name": sheet_name,
                "row_index": row,
                "col_index": col,
                "excel_ref": _excel_ref(row, col),
                "raw_text": raw_text,
                "cell_type": role,
                "style_json": json.dumps(style),
                "merge_json": json.dumps(merge),
            })

    # ── 2. 提取列维度成员（列头：data_row_start 以上的行，data_col_start 以右）──
    col_labels: dict[int, str] = {}  # col_idx → label
    for col in range(data_col_start, sheet.ncols):
        label_parts = []
        for row in range(data_row_start):
            cell = sheet.cell(row, col)
            txt = str(cell.value).strip() if cell.value else ""
            if txt:
                label_parts.append(txt)
        label = "·".join(label_parts) if label_parts else f"COL_{col}"
        col_labels[col] = label
        col_slug = _slugify(label)
        result.dimension_members.append({
            "member_code": f"{object_code}.{section_code}.COL.{col_slug}",
            "member_name": label,
            "axis": "COLUMN",
            "display_order": col - data_col_start,
            "source_cell_ref": _excel_ref(data_row_start - 1, col),
        })

    # ── 3. 提取行维度成员（行标签：data_col_start-1 列，data_row_start 以下）──
    row_labels: dict[int, str] = {}  # row_idx → label
    label_col = data_col_start - 1  # 行标签通常在数据列左侧一列
    if label_col < 0:
        label_col = 0

    for row in range(data_row_start, sheet.nrows):
        cell = sheet.cell(row, label_col)
        label = str(cell.value).strip() if cell.value else f"ROW_{row}"
        row_labels[row] = label
        row_slug = _slugify(label)
        result.dimension_members.append({
            "member_code": f"{object_code}.{section_code}.ROW.{row_slug}",
            "member_name": label,
            "axis": "ROW",
            "display_order": row - data_row_start,
            "source_cell_ref": _excel_ref(row, label_col),
        })

    # ── 4. 生成 reporting_items（数据区域内非 NO_DATA 单元格）────────────────
    for row in range(data_row_start, sheet.nrows):
        row_label = row_labels.get(row, f"ROW_{row}")
        row_slug = _slugify(row_label)

        for col in range(data_col_start, sheet.ncols):
            col_label = col_labels.get(col, f"COL_{col}")
            col_slug = _slugify(col_label)

            # 取 template_cell 中已计算的 role
            tc_idx = row * sheet.ncols + col
            if tc_idx < len(result.template_cells):
                role = result.template_cells[tc_idx]["cell_type"]
            else:
                role = "NO_DATA"

            if role == "NO_DATA":
                continue

            item_code = f"{object_code}.{section_code}.{row_slug}.{col_slug}"
            item_name = f"{row_label}-{col_label}"

            result.items.append({
                "item_code": item_code,
                "item_name": item_name,
                "source_cell_ref": _excel_ref(row, col),
                "cell_role": role,
                "row_label": row_label,
                "column_label": col_label,
                "is_fillable": role == "FILLABLE",
                "is_derived": role == "DERIVED",
                "data_type": "DECIMAL",
                "item_type": "DERIVED" if role == "DERIVED" else "MEASURE",
            })

            # item_dimensions：每个 item 关联一个 ROW 成员和一个 COLUMN 成员
            result.item_dimensions.append({
                "item_code": item_code,
                "row_member_code": f"{object_code}.{section_code}.ROW.{row_slug}",
                "col_member_code": f"{object_code}.{section_code}.COL.{col_slug}",
            })

    return result


def _parse_xlsx(file_path: Path, object_code: str, section_code: str) -> ExcelParseResult:
    """解析 .xlsx 文件（用 openpyxl）。颜色检测用 RGB 值。"""
    import openpyxl
    from openpyxl.styles.colors import COLOR_INDEX

    wb = openpyxl.load_workbook(str(file_path), data_only=True)
    ws = wb.active
    if ws is None:
        return ExcelParseResult()

    result = ExcelParseResult()
    sheet_name = ws.title

    def _openpyxl_role(cell) -> str:
        fill = cell.fill
        if fill and fill.fgColor and fill.fgColor.type == "rgb":
            rgb = fill.fgColor.rgb.upper()
            # 灰色系
            if rgb in ("FFBFBFBF", "FF808080", "FFC0C0C0", "FFD9D9D9"):
                return "NO_DATA"
            # 紫色/lavender 系
            if rgb in ("FFCC99FF", "FF9966FF", "FFCCAAFF"):
                return "DERIVED"
        return "FILLABLE"

    # 简化：只提取 template_cells 和 items，不做维度树（xlsx 用于新增报表）
    for row in ws.iter_rows():
        for cell in row:
            r, c = cell.row - 1, cell.column - 1
            role = _openpyxl_role(cell)
            raw_text = str(cell.value).strip() if cell.value is not None else ""
            result.template_cells.append({
                "sheet_name": sheet_name,
                "row_index": r,
                "col_index": c,
                "excel_ref": _excel_ref(r, c),
                "raw_text": raw_text,
                "cell_type": role,
                "style_json": "{}",
                "merge_json": "{}",
            })

    return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
uv run pytest tests/test_excel_parser.py -v
```

期望：`3 passed`（test_parse_g31_basic, test_parse_g31_item_codes, test_parse_excel_missing_file）

---

## Task 4: doc_parser 服务

**Files:**
- Create: `app/services/doc_parser.py`
- Create: `tests/test_doc_parser.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_doc_parser.py`：

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.doc_parser import extract_doc_text, generate_change_summary

G31_DOC = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc")


@pytest.mark.skipif(not G31_DOC.exists(), reason="G31 doc not available")
def test_extract_doc_text_returns_nonempty():
    text = extract_doc_text(G31_DOC)
    assert isinstance(text, str)
    assert len(text) > 100   # 填报说明不会少于 100 个字符


def test_extract_doc_text_missing_file():
    text = extract_doc_text(Path("/nonexistent/file.doc"))
    assert text == ""


@pytest.mark.asyncio
async def test_generate_change_summary_mocked():
    fake_summary = "本次修订：新增穿透后列，调整期末余额口径。"
    with patch("app.services.doc_parser.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(return_value=fake_summary)
        summary = await generate_change_summary("some long doc text", object_code="G31")
    assert summary == fake_summary


@pytest.mark.asyncio
async def test_generate_change_summary_llm_fail_returns_empty():
    with patch("app.services.doc_parser.LLMClient") as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.complete = AsyncMock(side_effect=Exception("LLM timeout"))
        summary = await generate_change_summary("some text", object_code="G31")
    assert summary == ""
```

- [ ] **Step 2: 安装 pytest-asyncio（如未安装）**

```bash
uv add --dev pytest-asyncio
```

在 `pyproject.toml` 的 `[tool.pytest.ini_options]` 下添加：

```toml
asyncio_mode = "auto"
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
uv run pytest tests/test_doc_parser.py -v 2>&1 | head -20
```

期望：`ModuleNotFoundError: No module named 'app.services.doc_parser'`

- [ ] **Step 4: 实现 doc_parser.py**

新建 `app/services/doc_parser.py`：

```python
"""Doc 填报说明解析器：提取文本 + LLM 变更摘要。支持 .docx 和旧版 .doc。"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.llm_client import LLMClient


def extract_doc_text(file_path: Path) -> str:
    """
    从 .doc 或 .docx 文件提取纯文本。

    - .docx：使用 python-docx
    - .doc：优先使用 soffice (LibreOffice) 转换，失败则返回空字符串
    """
    if not file_path.exists():
        return ""

    suffix = file_path.suffix.lower()

    if suffix == ".docx":
        return _extract_docx(file_path)
    elif suffix == ".doc":
        return _extract_doc_via_soffice(file_path)
    return ""


def _extract_docx(file_path: Path) -> str:
    try:
        from docx import Document
        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


def _extract_doc_via_soffice(file_path: Path) -> str:
    """使用 LibreOffice headless 将 .doc 转为 txt，再读取文本。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return ""

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "txt:Text",
                 "--outdir", tmp_dir, str(file_path)],
                capture_output=True, text=True, timeout=60,
            )
            txt_file = Path(tmp_dir) / (file_path.stem + ".txt")
            if txt_file.exists():
                return txt_file.read_text(encoding="utf-8", errors="ignore")
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


async def generate_change_summary(full_text: str, object_code: str) -> str:
    """
    调用 LLM，从填报说明全文中提取本次版本的变更要点。
    LLM 调用失败时静默返回空字符串，不阻塞入库流程。
    """
    if not full_text.strip():
        return ""

    prompt = f"""以下是监管报表 {object_code} 的填报说明全文。
请提取本次版本修订的变更要点，以简洁的要点列表形式输出（不超过 200 字）。
如果文中没有明确的变更说明，输出"无明确变更说明"。

填报说明：
{full_text[:3000]}
"""
    try:
        client = LLMClient()
        return await client.complete(prompt)
    except Exception:
        return ""
```

- [ ] **Step 5: 检查 LLMClient 接口是否有 `complete` 方法**

```bash
grep -n "def complete\|async def complete" /Users/jiangqiuping/webproject/监管报送项目/backend/app/services/llm_client.py
```

如果 LLMClient 的方法名不是 `complete`，在 `doc_parser.py` 中对应修改调用方式。

- [ ] **Step 6: 运行测试，确认通过**

```bash
uv run pytest tests/test_doc_parser.py -v
```

期望：`4 passed`

---

## Task 5: catalog_ingestor 服务（编排层）

**Files:**
- Create: `app/services/catalog_ingestor.py`

- [ ] **Step 1: 实现 catalog_ingestor.py**

新建 `app/services/catalog_ingestor.py`：

```python
"""
catalog_ingestor：编排 zip_scanner / excel_parser / doc_parser，管理事务写库，更新 batch 进度。
"""
import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.database import engine
from app.models.db_models import (
    RegCatalogBatch,
    RegCatalogBatchItem,
    RegReportingDimension,
    RegReportingDimensionMember,
    RegReportingInstruction,
    RegReportingItem,
    RegReportingItemDimension,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingTemplate,
    RegReportingTemplateCell,
    RegReportingVersion,
)
from app.services import doc_parser, excel_parser, zip_scanner


def create_batch(session: Session, zip_filename: str, source_doc_ref: str) -> RegCatalogBatch:
    """创建 batch 记录（PENDING 状态），立即提交，供前端获取 batch_id。"""
    batch = RegCatalogBatch(
        batch_code=f"BATCH_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6].upper()}",
        source_zip_filename=zip_filename,
        source_document_ref=source_doc_ref,
        status="PENDING",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def _get_or_create_system(session: Session) -> RegReportingSystem:
    """获取或创建 1104 报送体系记录。"""
    sys = session.exec(select(RegReportingSystem).where(
        RegReportingSystem.system_code == "1104"
    )).first()
    if sys:
        return sys
    sys = RegReportingSystem(
        system_code="1104",
        system_name="1104 非现场监管报表",
        regulator="国家金融监督管理总局",
    )
    session.add(sys)
    session.commit()
    session.refresh(sys)
    return sys


def _get_or_create_version(session: Session, system_id: int, version_label: str) -> RegReportingVersion:
    ver = session.exec(select(RegReportingVersion).where(
        RegReportingVersion.reporting_system_id == system_id,
        RegReportingVersion.version_code == version_label,
    )).first()
    if ver:
        return ver
    ver = RegReportingVersion(
        reporting_system_id=system_id,
        version_code=version_label,
        version_name=f"1104 第{version_label}版",
        effective_date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    session.add(ver)
    session.commit()
    session.refresh(ver)
    return ver


def _upsert_reporting_object(
    session: Session,
    object_code: str,
    system_id: int,
    version_id: int,
    change_type: str,
    table_category: str,
    version_label: str,
    batch_item_id: int,
) -> RegReportingObject:
    obj = session.exec(select(RegReportingObject).where(
        RegReportingObject.object_code == object_code
    )).first()
    if obj:
        obj.change_type = change_type
        obj.table_category = table_category
        obj.current_version_label = version_label
        obj.latest_batch_item_id = batch_item_id
    else:
        obj = RegReportingObject(
            reporting_system_id=system_id,
            reporting_version_id=version_id,
            object_code=object_code,
            object_name=object_code,  # 后续可从 Excel 标题行更新
            change_type=change_type,
            table_category=table_category,
            current_version_label=version_label,
            latest_batch_item_id=batch_item_id,
        )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def _write_excel_results(
    session: Session,
    parse_result: excel_parser.ExcelParseResult,
    object_id: int,
    batch_item_id: int,
    object_code: str,
    version_label: str,
) -> int:
    """将 ExcelParseResult 写入数据库，返回写入的 item 数量。"""
    # 1. 获取或创建 section
    section = session.exec(select(RegReportingSection).where(
        RegReportingSection.reporting_object_id == object_id,
        RegReportingSection.section_code == "PART_I",
    )).first()
    if not section:
        section = RegReportingSection(
            object_code=object_code,
            reporting_object_id=object_id,
            section_code="PART_I",
            section_name="主表",
            display_order=1,
        )
        session.add(section)
        session.commit()
        session.refresh(section)

    # 2. 创建 template
    template_code = f"{object_code}.PART_I.{version_label}"
    tpl = session.exec(select(RegReportingTemplate).where(
        RegReportingTemplate.template_code == template_code
    )).first()
    if not tpl:
        tpl = RegReportingTemplate(
            reporting_object_id=object_id,
            batch_item_id=batch_item_id,
            template_code=template_code,
            template_name=f"{object_code} 主表 {version_label}版",
            version_label=version_label,
            sheet_name="Sheet1",
        )
        session.add(tpl)
        session.commit()
        session.refresh(tpl)

    # 3. 批量写 template_cells
    for tc in parse_result.template_cells:
        cell = RegReportingTemplateCell(
            template_id=tpl.id,
            **{k: v for k, v in tc.items()},
        )
        session.add(cell)
    session.commit()

    # 4. 写 dimensions + dimension_members
    row_dim = session.exec(select(RegReportingDimension).where(
        RegReportingDimension.dimension_code == f"{object_code}.PART_I.ROW"
    )).first()
    if not row_dim:
        row_dim = RegReportingDimension(
            reporting_object_id=object_id,
            dimension_code=f"{object_code}.PART_I.ROW",
            dimension_name="行项目",
            axis="ROW",
        )
        session.add(row_dim)
        session.commit()
        session.refresh(row_dim)

    col_dim = session.exec(select(RegReportingDimension).where(
        RegReportingDimension.dimension_code == f"{object_code}.PART_I.COL"
    )).first()
    if not col_dim:
        col_dim = RegReportingDimension(
            reporting_object_id=object_id,
            dimension_code=f"{object_code}.PART_I.COL",
            dimension_name="列指标",
            axis="COLUMN",
        )
        session.add(col_dim)
        session.commit()
        session.refresh(col_dim)

    member_id_map: dict[str, int] = {}
    for m in parse_result.dimension_members:
        dim_id = row_dim.id if m["axis"] == "ROW" else col_dim.id
        existing = session.exec(select(RegReportingDimensionMember).where(
            RegReportingDimensionMember.member_code == m["member_code"]
        )).first()
        if not existing:
            member = RegReportingDimensionMember(
                dimension_id=dim_id,
                member_code=m["member_code"],
                member_name=m["member_name"],
                display_order=m["display_order"],
                source_cell_ref=m["source_cell_ref"],
            )
            session.add(member)
            session.commit()
            session.refresh(member)
            member_id_map[m["member_code"]] = member.id
        else:
            member_id_map[m["member_code"]] = existing.id

    # 5. 写 reporting_items + item_dimensions
    item_count = 0
    for item_data, dim_data in zip(parse_result.items, parse_result.item_dimensions):
        existing_item = session.exec(select(RegReportingItem).where(
            RegReportingItem.item_code == item_data["item_code"]
        )).first()
        if existing_item:
            continue  # 已存在则跳过（避免重复导入冲突）

        item = RegReportingItem(
            reporting_object_id=object_id,
            reporting_section_id=section.id,
            batch_item_id=batch_item_id,
            item_code=item_data["item_code"],
            item_name=item_data["item_name"],
            item_type=item_data["item_type"],
            row_label=item_data["row_label"],
            column_label=item_data["column_label"],
            source_cell_ref=item_data["source_cell_ref"],
            cell_role=item_data["cell_role"],
            is_fillable=item_data["is_fillable"],
            is_derived=item_data["is_derived"],
            data_type=item_data["data_type"],
            change_status="NEW",
        )
        session.add(item)
        session.commit()
        session.refresh(item)

        # item_dimensions
        row_member_id = member_id_map.get(dim_data["row_member_code"])
        col_member_id = member_id_map.get(dim_data["col_member_code"])
        if row_member_id:
            session.add(RegReportingItemDimension(
                reporting_item_id=item.id,
                dimension_id=row_dim.id,
                member_id=row_member_id,
                axis="ROW",
            ))
        if col_member_id:
            session.add(RegReportingItemDimension(
                reporting_item_id=item.id,
                dimension_id=col_dim.id,
                member_id=col_member_id,
                axis="COLUMN",
            ))
        session.commit()
        item_count += 1

    return item_count


async def process_catalog_zip(batch_id: int, zip_path: Path, extract_to: Path) -> None:
    """
    后台任务主入口：逐表解析并写库，更新 batch / batch_item 进度。
    使用独立 Session（不依赖请求上下文）。
    """
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if not batch:
            return
        batch.status = "PROCESSING"
        session.add(batch)
        session.commit()

    # 扫描目录
    try:
        version_label, file_sets = zip_scanner.scan_zip(zip_path, extract_to)
    except Exception as e:
        with Session(engine) as session:
            batch = session.get(RegCatalogBatch, batch_id)
            if batch:
                batch.status = "PARTIAL_FAIL"
                batch.finished_at = datetime.utcnow()
                session.add(batch)
                session.commit()
        return

    # 更新 batch 基本信息 + 创建 batch_items
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if not batch:
            return
        batch.version_label = version_label
        batch.total_count = len(file_sets)
        session.add(batch)

        sys_obj = _get_or_create_system(session)
        ver_obj = _get_or_create_version(session, sys_obj.id, version_label)

        batch_items: list[RegCatalogBatchItem] = []
        for fs in file_sets:
            bi = RegCatalogBatchItem(
                batch_id=batch_id,
                object_code=fs.object_code,
                change_type=fs.change_type,
                table_category=fs.table_category,
                excel_filename=str(fs.excel_path.name) if fs.excel_path else "",
                doc_filename=str(fs.doc_path.name) if fs.doc_path else "",
                parse_status="PENDING",
            )
            session.add(bi)
            batch_items.append(bi)
        session.commit()
        for bi in batch_items:
            session.refresh(bi)

    # 逐表处理
    for fs, bi_stub in zip(file_sets, batch_items):
        with Session(engine) as session:
            bi = session.get(RegCatalogBatchItem, bi_stub.id)
            if not bi:
                continue
            bi.parse_status = "PARSING"
            session.add(bi)
            session.commit()

        try:
            # Excel 解析
            excel_result = excel_parser.ExcelParseResult()
            if fs.excel_path and fs.change_type != "INSTRUCTION_ONLY":
                excel_result = excel_parser.parse_excel(
                    fs.excel_path, object_code=fs.object_code
                )

            # Doc 解析 + LLM 摘要
            full_text = ""
            change_summary = ""
            if fs.doc_path:
                full_text = doc_parser.extract_doc_text(fs.doc_path)
                change_summary = await doc_parser.generate_change_summary(
                    full_text, object_code=fs.object_code
                )

            # 写库
            with Session(engine) as session:
                sys_obj = _get_or_create_system(session)
                ver_obj = _get_or_create_version(session, sys_obj.id, version_label)
                bi = session.get(RegCatalogBatchItem, bi_stub.id)
                if not bi:
                    continue

                rep_obj = _upsert_reporting_object(
                    session,
                    object_code=fs.object_code,
                    system_id=sys_obj.id,
                    version_id=ver_obj.id,
                    change_type=fs.change_type,
                    table_category=fs.table_category,
                    version_label=version_label,
                    batch_item_id=bi.id,
                )

                if full_text:
                    existing_instr = session.exec(
                        select(RegReportingInstruction).where(
                            RegReportingInstruction.object_code == fs.object_code
                        )
                    ).first()
                    if not existing_instr:
                        session.add(RegReportingInstruction(
                            object_code=fs.object_code,
                            reporting_object_id=rep_obj.id,
                            instruction_text=full_text,
                            source_reference=str(fs.doc_path.name) if fs.doc_path else "",
                        ))

                item_count = 0
                if excel_result.items:
                    item_count = _write_excel_results(
                        session, excel_result, rep_obj.id, bi.id, fs.object_code, version_label
                    )

                bi.parse_status = "DONE"
                bi.change_summary = change_summary
                bi.items_count = item_count
                bi.finished_at = datetime.utcnow()
                session.add(bi)

                batch = session.get(RegCatalogBatch, batch_id)
                if batch:
                    batch.done_count += 1
                session.commit()

        except Exception as exc:
            with Session(engine) as session:
                bi = session.get(RegCatalogBatchItem, bi_stub.id)
                if bi:
                    bi.parse_status = "FAILED"
                    bi.parse_error = str(exc)[:500]
                    bi.finished_at = datetime.utcnow()
                    session.add(bi)
                batch = session.get(RegCatalogBatch, batch_id)
                if batch:
                    batch.fail_count += 1
                session.commit()

    # 最终更新 batch 状态
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if batch:
            batch.status = "DONE" if batch.fail_count == 0 else "PARTIAL_FAIL"
            batch.finished_at = datetime.utcnow()
            session.add(batch)
            session.commit()

    # 清理临时目录
    import shutil as _shutil
    _shutil.rmtree(extract_to, ignore_errors=True)
    zip_path.unlink(missing_ok=True)
```

- [ ] **Step 2: 检查 RegReportingInstruction 模型字段是否有 `object_code` 和 `reporting_object_id`**

```bash
grep -A 15 "class RegReportingInstruction" /Users/jiangqiuping/webproject/监管报送项目/backend/app/models/db_models.py
```

如果缺少 `object_code` 或 `reporting_object_id`，在模型中补充：

```python
object_code: str = Field(default="", index=True)
reporting_object_id: int | None = Field(default=None, index=True)
instruction_text: str = Field(default="", sa_column=Column(Text))
source_reference: str = ""
```

---

## Task 6: API 路由 + 注册到 main.py

**Files:**
- Create: `app/api/routes_catalog.py`
- Modify: `app/main.py`
- Create: `tests/test_catalog_api.py`

- [ ] **Step 1: 写 API 失败测试**

新建 `tests/test_catalog_api.py`：

```python
import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app


def _make_test_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls", b"fake")
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc", b"fake doc")
        zf.writestr("1.新增报表（基础类、业务类、支持发展类）/G51境外业务/G51(251).xlsx", b"fake")
    return buf.getvalue()


def test_upload_zip_returns_batch_id():
    client = TestClient(app)
    zip_bytes = _make_test_zip()
    response = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("test_catalog.zip", zip_bytes, "application/zip")},
        data={"source_document_ref": "测试文件"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "batch_id" in data
    assert data["version_label"] == "251"
    assert data["total_count"] == 2
    assert data["status"] == "PROCESSING"


def test_get_batch_detail():
    client = TestClient(app)
    zip_bytes = _make_test_zip()
    upload_resp = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("test_catalog.zip", zip_bytes, "application/zip")},
    )
    batch_id = upload_resp.json()["batch_id"]

    detail_resp = client.get(f"/api/catalog/batches/{batch_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == batch_id
    assert "items" in data


def test_list_batches():
    client = TestClient(app)
    response = client.get("/api/catalog/batches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_non_zip_returns_400():
    client = TestClient(app)
    response = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("readme.txt", b"not a zip", "text/plain")},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
uv run pytest tests/test_catalog_api.py -v 2>&1 | head -20
```

期望：`404 Not Found`（路由尚未注册）

- [ ] **Step 3: 实现 routes_catalog.py**

新建 `app/api/routes_catalog.py`：

```python
"""报表目录维护接口：zip 上传、批次查询。"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.db_models import RegCatalogBatch, RegCatalogBatchItem
from app.services.catalog_ingestor import create_batch, process_catalog_zip

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.post("/upload-zip", status_code=status.HTTP_201_CREATED)
async def upload_catalog_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_document_ref: str = Form(default=""),
    session: Session = Depends(get_session),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式文件")

    content = await file.read()
    if len(content) < 4 or content[:4] != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="文件不是有效的 zip 格式")

    # 保存 zip 到临时文件（BackgroundTask 异步处理，不能使用 with 上下文）
    tmp_dir = Path(tempfile.mkdtemp(prefix="catalog_batch_"))
    zip_path = tmp_dir / (file.filename or "upload.zip")
    zip_path.write_bytes(content)
    extract_to = tmp_dir / "extracted"

    batch = create_batch(session, zip_filename=file.filename or "", source_doc_ref=source_document_ref)

    # 扫描 zip 以提前知道 total_count 和 version_label（同步快速扫描）
    from app.services.zip_scanner import scan_zip as _quick_scan
    try:
        version_label, file_sets = _quick_scan(zip_path, extract_to)
        batch.version_label = version_label
        batch.total_count = len(file_sets)
        batch.status = "PROCESSING"
        session.add(batch)
        session.commit()
        session.refresh(batch)
    except Exception:
        pass

    background_tasks.add_task(process_catalog_zip, batch.id, zip_path, extract_to)

    return {
        "batch_id": batch.id,
        "batch_code": batch.batch_code,
        "version_label": batch.version_label,
        "total_count": batch.total_count,
        "status": batch.status,
    }


@router.get("/batches")
def list_batches(session: Session = Depends(get_session)) -> list[dict]:
    batches = session.exec(
        select(RegCatalogBatch).order_by(RegCatalogBatch.created_at.desc())  # type: ignore[arg-type]
    ).all()
    return [
        {
            "id": b.id,
            "batch_code": b.batch_code,
            "version_label": b.version_label,
            "source_zip_filename": b.source_zip_filename,
            "total_count": b.total_count,
            "done_count": b.done_count,
            "fail_count": b.fail_count,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@router.get("/batches/{batch_id}")
def get_batch_detail(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = session.get(RegCatalogBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = session.exec(
        select(RegCatalogBatchItem).where(RegCatalogBatchItem.batch_id == batch_id)
    ).all()

    return {
        "id": batch.id,
        "batch_code": batch.batch_code,
        "version_label": batch.version_label,
        "source_zip_filename": batch.source_zip_filename,
        "source_document_ref": batch.source_document_ref,
        "total_count": batch.total_count,
        "done_count": batch.done_count,
        "fail_count": batch.fail_count,
        "status": batch.status,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
        "items": [
            {
                "id": item.id,
                "object_code": item.object_code,
                "change_type": item.change_type,
                "table_category": item.table_category,
                "parse_status": item.parse_status,
                "parse_error": item.parse_error,
                "change_summary": item.change_summary,
                "items_count": item.items_count,
            }
            for item in items
        ],
    }
```

- [ ] **Step 4: 注册路由到 main.py**

在 `app/main.py` 中：

```python
# 顶部 import 区块加入：
from app.api import routes_catalog

# create_app 函数内，api.include_router(routes_tasks.router) 之后加入：
api.include_router(routes_catalog.router)
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
uv run pytest tests/test_catalog_api.py -v
```

期望：`4 passed`

- [ ] **Step 6: 全量测试，确认无回归**

```bash
uv run pytest -q 2>&1 | tail -10
```

期望：无新增失败

---

## Task 7: 端到端验证（真实 G31 zip）

- [ ] **Step 1: 打包真实 G31 目录为 zip**

```bash
cd "/Users/jiangqiuping/webproject/监管报送项目/一表通"
zip -r /tmp/test_catalog_g31.zip "附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/"
```

- [ ] **Step 2: 启动后端**

```bash
cd /Users/jiangqiuping/webproject/监管报送项目/backend
uv run uvicorn app.main:app --reload
```

- [ ] **Step 3: 上传 zip，获取 batch_id**

```bash
curl -s -X POST http://127.0.0.1:8000/api/catalog/upload-zip \
  -F "file=@/tmp/test_catalog_g31.zip" \
  -F "source_document_ref=金发〔2024〕39号" | python3 -m json.tool
```

期望：返回 `{ "batch_id": N, "version_label": "251", "total_count": 1, "status": "PROCESSING" }`

- [ ] **Step 4: 轮询进度，等待 DONE**

```bash
# 替换 N 为上一步返回的 batch_id
curl -s http://127.0.0.1:8000/api/catalog/batches/N | python3 -m json.tool
```

期望：`status = "DONE"`，`items[0].parse_status = "DONE"`，`items[0].items_count > 50`，`items[0].change_summary` 非空

- [ ] **Step 5: 验证数据库写入**

```bash
mysql -ureg_user -preg_pass_123 reg_reporting -e "
SELECT object_code, change_type, current_version_label, latest_batch_item_id FROM reg_reporting_objects WHERE object_code='G31';
SELECT COUNT(*) as item_count FROM reg_reporting_items WHERE item_code LIKE 'G31.%';
SELECT COUNT(*) as cell_count FROM reg_reporting_template_cells tc JOIN reg_reporting_templates t ON tc.template_id=t.id WHERE t.template_code LIKE 'G31.%';
SELECT COUNT(*) as member_count FROM reg_reporting_dimension_members dm JOIN reg_reporting_dimensions d ON dm.dimension_id=d.id WHERE d.reporting_object_id IN (SELECT id FROM reg_reporting_objects WHERE object_code='G31');
"
```

期望：item_count > 50, cell_count > 100, member_count > 10
