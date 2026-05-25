from sqlmodel import Session, SQLModel, create_engine

from app.models.db_models import (
    RegReportingItem,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingTemplate,
    RegReportingTemplateCell,
    RegReportingVersion,
)
from app.services.item_change_scanner import RevisionCandidate, build_change_summary, scan_and_annotate
from app.services.revision_table_parser import RevisionEntry


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_revision_table_matches_g31_items_by_business_row_alias_from_template_cells():
    session = _session()
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
        object_name="投资业务情况表",
        object_category="业务类",
        report_frequency="季",
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)

    section = RegReportingSection(
        reporting_object_id=obj.id,
        section_code="PART_I",
        section_name="表I",
    )
    session.add(section)
    session.commit()
    session.refresh(section)

    template = RegReportingTemplate(
        reporting_object_id=obj.id,
        template_code="G31.PART_I.251",
        template_name="G31 251",
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    session.add_all([
        RegReportingTemplateCell(template_id=template.id, row_index=7, col_index=0, excel_ref="A8", raw_text="1.0"),
        RegReportingTemplateCell(template_id=template.id, row_index=7, col_index=1, excel_ref="B8", raw_text="1.债券投资合计"),
        RegReportingTemplateCell(template_id=template.id, row_index=8, col_index=0, excel_ref="A9", raw_text="2.0"),
        RegReportingTemplateCell(template_id=template.id, row_index=8, col_index=2, excel_ref="C9", raw_text="1.1国债"),
    ])
    session.add_all([
        RegReportingItem(
            reporting_object_id=obj.id,
            reporting_section_id=section.id,
            item_code="G31.PART_I.1_0.A_穿透前_期末余额",
            item_name="1.0-A",
            row_label="1.0",
            column_label="A·穿透前·期末余额",
            source_cell_ref="D8",
            is_fillable=True,
        ),
        RegReportingItem(
            reporting_object_id=obj.id,
            reporting_section_id=section.id,
            item_code="G31.PART_I.2_0.D_因持有非底层资产而间接持有_期末余额",
            item_name="2.0-D",
            row_label="2.0",
            column_label="D·因持有非底层资产而间接持有·期末余额",
            source_cell_ref="G9",
            is_fillable=True,
        ),
    ])
    session.commit()

    report = scan_and_annotate(
        session,
        object_code="G31",
        revision_entries=[
            RevisionEntry("G31", "PART_I", "债券投资合计", "A_穿透前_期末余额", "MODIFIED", "口径调整"),
            RevisionEntry("G31", "PART_I", "一、国债", "D_因持有非底层资产而间接持有", "MODIFIED", "口径调整"),
        ],
    )

    assert [signal.item_code for signal in report.revision_lane] == [
        "G31.PART_I.1_0.A_穿透前_期末余额",
        "G31.PART_I.2_0.D_因持有非底层资产而间接持有_期末余额",
    ]
    assert len(report.results) == 2


def test_revision_table_keeps_unmatched_new_entries_as_candidates():
    session = _session()
    system = RegReportingSystem(system_code="1104", system_name="1104")
    session.add(system)
    session.commit()
    session.refresh(system)

    version = RegReportingVersion(reporting_system_id=system.id, version_code="251", version_name="251")
    session.add(version)
    session.commit()
    session.refresh(version)

    obj = RegReportingObject(
        reporting_system_id=system.id,
        reporting_version_id=version.id,
        object_code="G31",
        object_name="投资业务情况表",
    )
    session.add(obj)
    session.commit()

    report = scan_and_annotate(
        session,
        object_code="G31",
        revision_entries=[
            RevisionEntry("G31", "PART_II", "底层资产合计", "E_穿透层级", "NEW", "251版新增，记录穿透层数"),
        ],
    )

    assert report.results == []
    assert len(report.revision_candidates) == 1
    candidate = report.revision_candidates[0]
    assert candidate.match_status == "UNMATCHED_NEW"
    assert candidate.table_code == "G31"
    assert candidate.section == "PART_II"
    assert candidate.row_label == "底层资产合计"
    assert candidate.column_label == "E_穿透层级"
    assert candidate.matched_item_code == ""
    assert candidate.evidence == "修订对照表：251版新增，记录穿透层数"


def test_summary_counts_unmatched_revision_changes_as_change_signals():
    summary = build_change_summary(
        results=[],
        revision_candidates=[
            RevisionCandidate(
                table_code="G31",
                section="PART_II",
                row_label="底层资产合计",
                column_label="E_穿透层级",
                change_type="NEW",
                change_desc="251版新增穿透层级",
                match_status="UNMATCHED_NEW",
            ),
            RevisionCandidate(
                table_code="G31",
                section="PART_I",
                row_label="债券投资合计",
                column_label="D_因持有非底层资产而间接持有",
                change_type="MODIFIED",
                change_desc="穿透统计口径调整",
                match_status="UNMATCHED_MODIFIED",
            ),
            RevisionCandidate(
                table_code="G31",
                section="PART_I",
                row_label="债券投资合计",
                column_label="A_穿透前_期末余额",
                change_type="UNCHANGED",
                change_desc="口径无变化",
                match_status="UNMATCHED_UNCHANGED",
            ),
        ],
    )

    assert "识别变更信号 2 条" in summary
    assert "新增 1 条、修改 1 条" in summary
    assert "信号来源：REVISION_TABLE(2条未落格)" in summary
