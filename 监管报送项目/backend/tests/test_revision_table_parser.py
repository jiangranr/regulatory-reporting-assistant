from pathlib import Path

import openpyxl

from app.services.revision_table_parser import parse_revision_table


def test_parse_revision_table_supports_header_synonyms(tmp_path: Path):
    path = tmp_path / "revision.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["报表", "部分", "指标项目", "指标字段", "调整类型", "调整说明"])
    ws.append(["G31", "PART_II", "底层资产合计", "E_穿透层级", "新增", "251版新增穿透层级"])
    wb.save(path)

    entries = parse_revision_table(path)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.table_code == "G31"
    assert entry.section == "PART_II"
    assert entry.row_label == "底层资产合计"
    assert entry.column_label == "E_穿透层级"
    assert entry.change_type == "NEW"
    assert entry.change_desc == "251版新增穿透层级"
