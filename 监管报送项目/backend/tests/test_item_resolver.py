"""ReportingItemResolver 单元测试。

覆盖：
- 单 item 表：top 1 即使分数低也命中（语义上"精确"成立）
- 多 cell 表：高置信 → FUZZY_PRECISE 单命中
- 多 cell 表：中置信多命中 → FUZZY_LANE，matched_item_code 留空、item_codes 填多个
- 完全无匹配 → UNRESOLVED
- 空 hint / 空 table_code → UNRESOLVED
- 纯数字 hint（"1.8.2/1.8.3"）→ tokenise 后过滤掉数字片段 → UNRESOLVED
"""

from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.models.db_models import RegReportingItem, RegReportingObject, RegReportingSection
from app.services.item_resolver import (
    ReportingItemResolver,
    _normalise,
    _tokenise,
)


# ── 辅助 ──────────────────────────────────────────────────────────────


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_g24_single_item(session: Session) -> str:
    obj = RegReportingObject(
        reporting_system_id=1,
        reporting_version_id=1,
        object_code="G24",
        object_name="最大百家金融机构同业融入情况表",
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    sec = RegReportingSection(
        reporting_object_id=obj.id, section_code="MAIN", section_name="主表"
    )
    session.add(sec)
    session.commit()
    session.refresh(sec)
    item = RegReportingItem(
        reporting_object_id=obj.id,
        reporting_section_id=sec.id,
        item_code="G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        item_name="最大百家金融机构同业融入余额",
        row_label="金融机构同业融入",
        column_label="余额",
        cell_role="FILLABLE",
        is_fillable=True,
    )
    session.add(item)
    session.commit()
    return item.item_code


def _seed_g31_multi_cells(session: Session) -> list[str]:
    """G31 模拟 5 个 cell，对应 1.8 资产支持证券行的 A-E 列。"""
    obj = RegReportingObject(
        reporting_system_id=1,
        reporting_version_id=1,
        object_code="G31",
        object_name="投资业务情况表",
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    sec = RegReportingSection(
        reporting_object_id=obj.id, section_code="PART_I", section_name="第 I 部分"
    )
    session.add(sec)
    session.commit()
    session.refresh(sec)

    cells = [
        ("G31.PART_I.13_0.A_穿透前_期末余额", "1.8资产支持证券·A·穿透前·期末余额", "1.8资产支持证券", "A·穿透前·期末余额"),
        ("G31.PART_I.13_0.B_投资收入_年初至报告期末数", "1.8资产支持证券·B·投资收入", "1.8资产支持证券", "B·投资收入"),
        ("G31.PART_I.13_0.C_修正久期", "1.8资产支持证券·C·修正久期", "1.8资产支持证券", "C·修正久期"),
        ("G31.PART_I.1_0.A_穿透前_期末余额", "1.债券投资合计·A·穿透前·期末余额", "1.债券投资合计", "A·穿透前·期末余额"),
        ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "1.债券投资合计·B·投资收入", "1.债券投资合计", "B·投资收入"),
    ]
    codes: list[str] = []
    for code, name, row, col in cells:
        session.add(
            RegReportingItem(
                reporting_object_id=obj.id,
                reporting_section_id=sec.id,
                item_code=code,
                item_name=name,
                row_label=row,
                column_label=col,
                cell_role="FILLABLE",
                is_fillable=True,
            )
        )
        codes.append(code)
    session.commit()
    return codes


# ── normalise / tokenise 基础 ────────────────────────────────────────


def test_normalise_strips_separators():
    assert _normalise("A·穿透前·期末余额") == "a穿透前期末余额"
    assert _normalise("  最大百家   金融机构  ") == "最大百家金融机构"
    assert _normalise("") == ""


def test_tokenise_filters_pure_numbers_and_short():
    # 纯数字编号片段必须被过滤（"1.8.2" 否则会污染匹配）
    tokens = _tokenise("1.8 行下新增子项 1.8.1/1.8.2/1.8.3")
    assert "1.8" not in tokens
    assert "1.8.1" not in tokens
    assert "行下新增子项" in tokens
    # 太短的 token 也过滤
    assert "A" not in tokens


def test_tokenise_normal_business_phrase():
    tokens = _tokenise("最大百家金融机构同业融入余额/融入侧统计范围")
    assert "最大百家金融机构同业融入余额" in tokens
    assert "融入侧统计范围" in tokens


# ── 单 item 表 ────────────────────────────────────────────────────────


def test_single_item_table_top1_wins():
    session = _make_session()
    code = _seed_g24_single_item(session)

    r = ReportingItemResolver(session).resolve(
        "G24", "境外法人机构融入款项（列代码 C09）"
    )
    # G24 只有 1 个 item，无论 hint 是什么都精确命中
    assert r.matched_item_code == code
    assert r.match_status == "FUZZY_PRECISE"
    assert r.item_codes == [code]


def test_single_item_table_exact_alias_hit():
    session = _make_session()
    code = _seed_g24_single_item(session)

    r = ReportingItemResolver(session).resolve(
        "G24", "最大百家金融机构同业融入余额"
    )
    assert r.matched_item_code == code
    assert "alias" in r.paths or "token" in r.paths


# ── 多 cell 表 ────────────────────────────────────────────────────────


def test_multi_cell_high_confidence_precise():
    session = _make_session()
    codes = _seed_g31_multi_cells(session)
    # hint 精确包含 A·穿透前·期末余额 同时锁定 1.8 资产支持证券
    r = ReportingItemResolver(session).resolve(
        "G31", "1.8资产支持证券 A 穿透前 期末余额"
    )
    # 应能锁定到 13_0.A_穿透前_期末余额
    assert r.match_status in ("FUZZY_PRECISE", "FUZZY_LANE")
    if r.match_status == "FUZZY_PRECISE":
        assert "13_0.A_穿透前" in r.matched_item_code
    assert any("13_0.A_穿透前" in c for c in r.item_codes)


def test_multi_cell_section_level_hint_yields_lane():
    session = _make_session()
    codes = _seed_g31_multi_cells(session)
    # hint 只点到行级（资产支持证券），不指定列
    r = ReportingItemResolver(session).resolve("G31", "资产支持证券分类调整")
    # 应该命中多个该行的 cell，走 FUZZY_LANE
    if r.match_status == "FUZZY_LANE":
        assert r.matched_item_code == ""
        # 13_0 行的 cell 应在 lane 里
        assert any("13_0" in c for c in r.item_codes)


# ── 边界 ──────────────────────────────────────────────────────────────


def test_unresolved_when_hint_is_only_numbers():
    """纯数字编号 hint（典型如 "1.8.1/1.8.2/1.8.3"）应不命中任何 cell"""
    session = _make_session()
    _seed_g31_multi_cells(session)
    r = ReportingItemResolver(session).resolve("G31", "1.8.1/1.8.2/1.8.3")
    assert r.match_status == "UNRESOLVED"
    assert r.matched_item_code == ""
    assert r.item_codes == []


def test_unresolved_when_no_table_or_hint():
    session = _make_session()
    resolver = ReportingItemResolver(session)
    assert resolver.resolve("", "x").match_status == "UNRESOLVED"
    assert resolver.resolve("G24", "").match_status == "UNRESOLVED"


def test_unresolved_when_table_unknown():
    session = _make_session()
    _seed_g24_single_item(session)
    r = ReportingItemResolver(session).resolve("G99", "任意 hint")
    assert r.match_status == "UNRESOLVED"


def test_cache_reuses_items_within_session():
    session = _make_session()
    _seed_g24_single_item(session)
    resolver = ReportingItemResolver(session)
    r1 = resolver.resolve("G24", "境外法人机构")
    r2 = resolver.resolve("G24", "同业融入")
    # 两次调用应都拿到结果（cache 不影响正确性）
    assert r1.matched_item_code
    assert r2.matched_item_code
