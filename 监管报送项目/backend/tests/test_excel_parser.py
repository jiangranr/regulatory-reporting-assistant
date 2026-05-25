from pathlib import Path
import pytest
from app.services.excel_parser import parse_excel, ExcelParseResult

G31_XLS = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls")
G31_252_XLS = G31_XLS.with_name("G31(252).xls")


@pytest.mark.skipif(not G31_XLS.exists(), reason="G31 file not available")
def test_parse_g31_basic():
    result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    # G31 有 70 行 × 9 列，template_cells 应超过 100
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


@pytest.mark.skipif(not G31_XLS.exists(), reason="G31 file not available")
def test_parse_g31_item_dimensions_match_items():
    result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    item_codes_from_items = {item["item_code"] for item in result.items}
    item_codes_from_dims = {d["item_code"] for d in result.item_dimensions}
    assert item_codes_from_items == item_codes_from_dims


@pytest.mark.skipif(not G31_XLS.exists(), reason="G31 file not available")
def test_parse_g31_uses_business_rows_and_measure_columns_only():
    result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")

    assert any("资产支持证券" in item["row_label"] for item in result.items)
    assert not any(item["source_cell_ref"].startswith(("A", "B", "C", "I")) for item in result.items)
    assert not any(item["column_label"].startswith("COL_") for item in result.items)
    assert not any("G31投资业务情况表" in item["column_label"] for item in result.items)


@pytest.mark.skipif(
    not G31_XLS.exists() or not G31_252_XLS.exists(),
    reason="G31 251/252 files not available",
)
def test_parse_g31_252_no_longer_contains_asset_backed_security_rows():
    old_result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    new_result = parse_excel(G31_252_XLS, object_code="G31", section_code="PART_I")

    assert any("资产支持证券" in item["row_label"] for item in old_result.items)
    assert not any("资产支持证券" in item["row_label"] for item in new_result.items)


def test_parse_excel_missing_file():
    with pytest.raises(FileNotFoundError):
        parse_excel(Path("/nonexistent/file.xls"), object_code="G99", section_code="PART_I")
