"""测试 item_change_scanner 的 v2 字段维度路径。

覆盖：
  - affected_cells 非空时直接命中（跳过 slug 匹配）
  - 1 个 RevisionEntry 通过 affected_cells 命中多个 cell → 产出多个 RevisionCandidate
  - v2 元数据（revision_id / field_code / change_summary / dimensions）被填充到 candidate
  - affected_cells 为空时回退到老 row+col slug 匹配（向下兼容）
"""
from sqlmodel import Session, SQLModel, create_engine

from app.models.db_models import (
    RegReportingItem,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingVersion,
)
from app.services.item_change_scanner import scan_and_annotate
from app.services.revision_table_parser import RevisionEntry


def _setup_g31_with_items(session: Session) -> None:
    system = RegReportingSystem(system_code="1104", system_name="1104")
    session.add(system)
    session.commit()
    session.refresh(system)

    version = RegReportingVersion(
        reporting_system_id=system.id, version_code="251", version_name="251"
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
        reporting_object_id=obj.id, section_code="PART_I", section_name="表I"
    )
    session.add(section)
    session.commit()
    session.refresh(section)

    # 5 个 D 列 cell，模拟 G31 多行
    for row_n in (1, 2, 3):
        session.add(
            RegReportingItem(
                reporting_object_id=obj.id,
                reporting_section_id=section.id,
                item_code=f"G31.PART_I.{row_n}_0.D_因持有非底层资产而间接持有_期末余额",
                item_name=f"{row_n}.0-D",
                row_label=f"{row_n}.0",
                column_label="D·因持有非底层资产而间接持有·期末余额",
                source_cell_ref=f"G{row_n + 7}",
                is_fillable=True,
            )
        )
    session.commit()


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_affected_cells_directly_hits_multiple_items():
    """v2 字段维度路径：1 条 RevisionEntry 通过 affected_cells 命中 3 个 cell，
    产出 1 条 candidate（带 matched_item_codes 列表）+ 3 条 lane 信号。"""
    session = _session()
    _setup_g31_with_items(session)

    entry = RevisionEntry(
        table_code="G31",
        section="PART_I",
        row_label="",          # 字段维度路径不依赖 row_label
        column_label="",       # 也不依赖 column_label
        change_type="MODIFIED",
        change_desc="",
        revision_id="REV-1104-2026Q1-G31-002",
        regime_version="1104-2026Q1-v2",
        field_code="indirect_holding_balance",
        field_name="因持有非底层资产间接持有期末余额",
        change_dimensions=["口径", "校验规则"],
        change_summary="穿透口径扩展：新增资管/信托/SPV",
        before_value={"口径": "原口径"},
        after_value={"口径": "新口径"},
        regulation_evidence="2026 第 14 号公告 §3.4",
        affected_cells=[
            "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额",
            "G31.PART_I.2_0.D_因持有非底层资产而间接持有_期末余额",
            "G31.PART_I.3_0.D_因持有非底层资产而间接持有_期末余额",
        ],
        effective_date="2026-06-30",
    )

    report = scan_and_annotate(session, object_code="G31", revision_entries=[entry])

    # 字段维度：1 个 entry → 1 个 candidate（带全部命中 cell）
    matched = [c for c in report.revision_candidates if c.match_status == "MATCHED_EXISTING"]
    assert len(matched) == 1
    c = matched[0]
    assert set(c.matched_item_codes) == set(entry.affected_cells)
    assert c.matched_item_code == entry.affected_cells[0]  # 首个命中（兼容字段）

    # candidate 上 v2 元信息齐备
    assert c.revision_id == "REV-1104-2026Q1-G31-002"
    assert c.regime_version == "1104-2026Q1-v2"
    assert c.field_code == "indirect_holding_balance"
    assert c.field_name == "因持有非底层资产间接持有期末余额"
    assert "口径" in c.change_dimensions
    assert "穿透口径扩展" in c.change_summary
    assert c.before_value == {"口径": "原口径"}
    assert c.after_value == {"口径": "新口径"}
    assert "v2 字段维度路径" in c.reason

    # lane 信号仍按 cell 展开（用于 change_status 逐格更新）
    assert len(report.revision_lane) == 3
    lane_codes = {s.item_code for s in report.revision_lane}
    assert lane_codes == set(entry.affected_cells)


def test_affected_cells_empty_falls_back_to_slug_matching():
    """v2 兜底路径：affected_cells 为空时退化到 row+col slug 匹配（保证旧用例不破）。"""
    session = _session()
    _setup_g31_with_items(session)

    entry = RevisionEntry(
        table_code="G31",
        section="PART_I",
        row_label="1.0",
        column_label="D·因持有非底层资产而间接持有·期末余额",
        change_type="MODIFIED",
        change_desc="口径调整",
        # 注意：v2 字段全部留空，模拟"老 6 列 Excel"
        affected_cells=[],
    )

    report = scan_and_annotate(session, object_code="G31", revision_entries=[entry])

    # slug 匹配应命中 1.0-D
    assert len(report.revision_lane) == 1
    assert report.revision_lane[0].item_code == "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额"


def test_affected_cells_with_unknown_codes_falls_back_then_unmatched():
    """affected_cells 给的 item_code DB 里找不到 + row/col 也匹配不到 → UNMATCHED 候选。"""
    session = _session()
    _setup_g31_with_items(session)

    entry = RevisionEntry(
        table_code="G31",
        section="PART_I",
        row_label="不存在的行",
        column_label="不存在的列",
        change_type="NEW",
        change_desc="",
        field_code="bill_investment_balance",
        affected_cells=["G31.PART_I.99_0.NON_EXISTENT_CELL"],
    )

    report = scan_and_annotate(session, object_code="G31", revision_entries=[entry])

    # affected_cells 命中失败 → 走 slug 也失败 → 应该有 UNMATCHED 候选
    assert len(report.revision_candidates) == 1
    assert report.revision_candidates[0].match_status == "UNMATCHED_NEW"
    assert report.revision_candidates[0].field_code == "bill_investment_balance"
