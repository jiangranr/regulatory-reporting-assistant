from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.db_models import (
    RegReportingItem,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingTemplate,
    RegReportingTemplateCell,
    RegReportingVersion,
)
from app.services.excel_parser import ExcelParseResult, parse_excel
from app.services.g31_excel_diff import diff_excel_with_db


G31_XLS = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls")
G31_252_XLS = G31_XLS.with_name("G31(252).xls")


def _session_with_g31_items(parse_result: ExcelParseResult) -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    system = RegReportingSystem(system_code="1104", system_name="1104")
    session.add(system)
    session.commit()
    session.refresh(system)

    version = RegReportingVersion(
        reporting_system_id=system.id,
        version_code="251",
        version_name="251",
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    obj = RegReportingObject(
        reporting_system_id=system.id,
        reporting_version_id=version.id,
        object_code="G31",
        object_name="G31",
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)

    section = RegReportingSection(
        reporting_object_id=obj.id,
        section_code="PART_I",
        section_name="PART_I",
    )
    session.add(section)
    session.commit()
    session.refresh(section)

    for item in parse_result.items:
        session.add(
            RegReportingItem(
                reporting_object_id=obj.id,
                reporting_section_id=section.id,
                item_code=item["item_code"],
                item_name=item["item_name"],
                row_label=item["row_label"],
                column_label=item["column_label"],
                source_cell_ref=item["source_cell_ref"],
                cell_role=item["cell_role"],
                is_fillable=item["is_fillable"],
                is_derived=item["is_derived"],
            )
        )
    session.commit()
    return session


def _session_with_legacy_numeric_g31_items(parse_result: ExcelParseResult) -> Session:
    session = _session_with_g31_items(ExcelParseResult())
    obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == "G31")
    ).first()
    section = session.exec(
        select(RegReportingSection).where(RegReportingSection.reporting_object_id == obj.id)
    ).first()

    template = RegReportingTemplate(
        reporting_object_id=obj.id,
        template_code="G31.PART_I.251",
        template_name="G31 251",
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    row_number_by_index: dict[int, str] = {}
    for cell in parse_result.template_cells:
        row_index = int(cell["row_index"])
        if int(cell["col_index"]) == 0 and str(cell["raw_text"]).strip():
            row_number_by_index[row_index] = str(cell["raw_text"]).strip()
        session.add(
            RegReportingTemplateCell(
                template_id=template.id,
                sheet_name=cell["sheet_name"],
                row_index=row_index,
                col_index=int(cell["col_index"]),
                excel_ref=cell["excel_ref"],
                raw_text=cell["raw_text"],
                cell_type=cell["cell_type"],
                style_json=cell["style_json"],
                merge_json=cell["merge_json"],
            )
        )
    session.commit()

    for item in parse_result.items:
        row_index = int(item["source_cell_ref"][1:]) - 1
        legacy_row_label = row_number_by_index.get(row_index, item["row_label"])
        session.add(
            RegReportingItem(
                reporting_object_id=obj.id,
                reporting_section_id=section.id,
                item_code=f"LEGACY.{item['item_code']}",
                item_name=item["item_name"],
                row_label=legacy_row_label,
                column_label=item["column_label"],
                source_cell_ref=item["source_cell_ref"],
                cell_role=item["cell_role"],
                is_fillable=item["is_fillable"],
                is_derived=item["is_derived"],
            )
        )
    session.add(
        RegReportingItem(
            reporting_object_id=obj.id,
            reporting_section_id=section.id,
            item_code="LEGACY.STRUCT.COL_1",
            item_name="legacy structure column",
            row_label="1.0",
            column_label="COL_1",
            source_cell_ref="B8",
            cell_role="FILLABLE",
            is_fillable=True,
            is_derived=False,
        )
    )
    session.add(
        RegReportingItem(
            reporting_object_id=obj.id,
            reporting_section_id=section.id,
            item_code="LEGACY.FOOTER.FILLER",
            item_name="legacy footer row",
            row_label="填表人：",
            column_label="A·穿透前·期末余额",
            source_cell_ref="D66",
            cell_role="FILLABLE",
            is_fillable=True,
            is_derived=False,
        )
    )
    session.commit()
    return session


@pytest.mark.skipif(
    not G31_XLS.exists() or not G31_252_XLS.exists(),
    reason="G31 251/252 files not available",
)
def test_g31_252_diff_reports_asset_backed_security_deletions_not_renumbering_noise():
    old_result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    new_result = parse_excel(G31_252_XLS, object_code="G31", section_code="PART_I")
    session = _session_with_g31_items(old_result)

    try:
        diffs = diff_excel_with_db(session, "G31", new_result)
    finally:
        session.close()

    assert diffs
    assert {diff.diff_type for diff in diffs} == {"REMOVED"}
    assert all(
        any(keyword in diff.row_label for keyword in ("资产支持", "信贷资产证券化"))
        for diff in diffs
    )
    assert not any("单位：万元" in diff.column_label for diff in diffs)
    assert not any("外国债券" in diff.row_label for diff in diffs)


@pytest.mark.skipif(
    not G31_XLS.exists() or not G31_252_XLS.exists(),
    reason="G31 251/252 files not available",
)
def test_g31_252_diff_uses_template_row_aliases_for_legacy_numeric_catalog():
    old_result = parse_excel(G31_XLS, object_code="G31", section_code="PART_I")
    new_result = parse_excel(G31_252_XLS, object_code="G31", section_code="PART_I")
    session = _session_with_legacy_numeric_g31_items(old_result)

    try:
        diffs = diff_excel_with_db(session, "G31", new_result)
    finally:
        session.close()

    assert diffs
    assert {diff.diff_type for diff in diffs} == {"REMOVED"}
    assert all(
        any(keyword in diff.row_label for keyword in ("资产支持", "信贷资产证券化"))
        for diff in diffs
    )
    assert not any("单位：万元" in diff.column_label for diff in diffs)
    assert not any("外国债券" in diff.row_label for diff in diffs)
