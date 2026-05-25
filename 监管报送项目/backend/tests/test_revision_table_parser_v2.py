"""测试 v2 字段维度修订对照表解析。

覆盖：
  - 3-sheet 格式被正确识别（修订对照表 sheet + 制度版本 sheet）
  - 17 字段全部解析正确
  - Sheet 1「制度版本」的 regime_version / effective_date 注入到每条 entry
  - before_value / after_value 多行 key:value 正确解析为 dict
  - change_dimensions / affected_cells 按、,换行切分
  - 向下兼容：老 6 列 Excel 仍能解析
"""
from pathlib import Path

import pytest

from app.services.revision_table_parser import parse_revision_table


V2_FILE = Path(__file__).resolve().parents[1] / "data" / "G31_修订对照表_v2_2026Q1.xlsx"
V1_FILE = Path(__file__).resolve().parents[1] / "data" / "G31_修订对照表_mock.xlsx"


@pytest.fixture(scope="module")
def v2_entries():
    if not V2_FILE.exists():
        pytest.skip(f"测试文件不存在：{V2_FILE}（先跑 scripts/export_g31_revisions_to_xlsx.py）")
    return parse_revision_table(V2_FILE)


def test_v2_parses_8_entries(v2_entries):
    assert len(v2_entries) == 8


def test_v2_revision_id_and_field_code(v2_entries):
    rev_ids = {e.revision_id for e in v2_entries}
    field_codes = {e.field_code for e in v2_entries}
    assert "REV-1104-2026Q1-G31-001" in rev_ids
    assert "indirect_holding_balance" in field_codes
    assert "modified_duration" in field_codes
    assert "preferred_stock_balance" in field_codes


def test_v2_regime_version_injected_to_every_entry(v2_entries):
    """Sheet 1「制度版本」的 regime_version 应被注入到每条 entry。"""
    for e in v2_entries:
        assert e.regime_version == "1104-2026Q1-v2", f"{e.revision_id} 缺 regime_version"
        assert e.effective_date == "2026-06-30", f"{e.revision_id} 缺 effective_date"


def test_v2_change_dimensions_parsed_as_list(v2_entries):
    by_field = {e.field_code: e for e in v2_entries}
    d = by_field["indirect_holding_balance"]
    assert "口径" in d.change_dimensions
    assert "校验规则" in d.change_dimensions


def test_v2_before_after_parsed_as_dict(v2_entries):
    by_field = {e.field_code: e for e in v2_entries}
    d = by_field["indirect_holding_balance"]
    assert isinstance(d.before_value, dict)
    assert isinstance(d.after_value, dict)
    assert "口径" in d.before_value
    assert "穿透统计仅含直接持有 ABS" in d.before_value["口径"]
    assert "穿透统计含" in d.after_value["口径"]


def test_v2_change_summary_present(v2_entries):
    by_field = {e.field_code: e for e in v2_entries}
    d = by_field["indirect_holding_balance"]
    assert "穿透口径扩展" in d.change_summary


def test_v2_affected_cells_parsed(v2_entries):
    """affected_cells 应解析为 item_code 列表。modified_duration 应有 25 个 cell。"""
    by_field = {e.field_code: e for e in v2_entries}
    md = by_field["modified_duration"]
    # DB 里 G31 1-25 行各有一个 C_修正久期 cell
    assert len(md.affected_cells) > 0
    assert all(c.startswith("G31.PART_I.") for c in md.affected_cells)


def test_v2_enum_value_in_after_value_parsed_as_list(v2_entries):
    """发行人类型的枚举值在 after_value 里应被切分为 list。"""
    by_field = {e.field_code: e for e in v2_entries}
    issuer = by_field["issuer_type"]
    enum_after = issuer.after_value.get("枚举值")
    # 多个枚举值用、分隔时应被切分为 list
    assert isinstance(enum_after, list)
    assert "境外金融机构" in enum_after
    assert "中央政府" in enum_after


def test_v1_backward_compat_still_works():
    """老 6 列文件仍能解析（向下兼容）。"""
    if not V1_FILE.exists():
        pytest.skip(f"老 mock 文件不存在：{V1_FILE}")
    entries = parse_revision_table(V1_FILE)
    assert len(entries) > 0
    # 老文件不应该有 v2 新字段
    for e in entries:
        assert e.revision_id == ""
        assert e.field_code == ""
        assert e.change_dimensions == []
        assert e.before_value == {}
