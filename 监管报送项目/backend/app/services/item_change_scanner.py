"""指标变更扫描引擎

协调三路信号源，按优先级更新 RegReportingItem.change_status：
  1. 修订对照表（最高优先级，精确匹配）
  2. Excel 结构差异（次优，基于 slug 键）
  3. 填报说明语义/关键词扫描（最低，模糊匹配）

同一指标格若被多个信号源命中，取最高优先级的信号。
为支持前端"三路漏斗"可视化，扫描结果同时返回每一路的原始命中明细
以及最终被合并采纳/被覆盖的关系。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.db_models import RegReportingItem, RegReportingObject, RegReportingTemplate, RegReportingTemplateCell
from app.services.composite_signal_matcher import build_composite_match, build_semantic_field_match
from app.services.g31_excel_diff import ExcelDiffEntry
from app.services.reporting_item_scope import filter_analysis_items
from app.services.revision_table_parser import RevisionEntry


@dataclass
class ItemChangeResult:
    item_code: str
    row_label: str
    column_label: str
    old_status: str
    new_status: str
    source: str      # REVISION_TABLE | EXCEL_DIFF | INSTRUCTION
    confidence: float
    evidence: str
    overridden_sources: list[str] = field(default_factory=list)  # 其他命中过但被覆盖的源


@dataclass
class LaneSignal:
    """单路信号源的原始命中（未经优先级合并）。"""
    item_code: str
    row_label: str
    column_label: str
    change_type: str    # NEW / MODIFIED / DELETED / UNCHANGED
    confidence: float
    evidence: str
    won: bool = False   # 是否在最终合并中胜出


@dataclass
class RevisionCandidate:
    """修订对照表逐条识别结果。
    每个 RevisionEntry 产出 1 个 RevisionCandidate（不再按 cell fan-out）。
    匹配到多个 cell 时，全部塞进 matched_item_codes 列表，matched_item_code 取首个（兼容）。
    """
    table_code: str
    section: str
    row_label: str
    column_label: str
    change_type: str
    change_desc: str
    match_status: str
    matched_item_code: str = ""                                   # 首个命中（兼容老代码）
    confidence: float = 0.0
    evidence: str = ""
    reason: str = ""

    # —— v2 字段维度新增 ——
    revision_id: str = ""
    regime_version: str = ""
    field_code: str = ""
    field_name: str = ""
    change_dimensions: list[str] = field(default_factory=list)
    change_summary: str = ""
    before_value: dict = field(default_factory=dict)
    after_value: dict = field(default_factory=dict)
    regulation_evidence: str = ""
    evidence_source_ref: str = ""
    affected_cells: list[str] = field(default_factory=list)
    effective_date: str = ""
    matched_item_codes: list[str] = field(default_factory=list)   # 所有命中（v2 新增）
    composite_match: dict = field(default_factory=dict)


@dataclass
class ScanReport:
    results: list[ItemChangeResult]
    revision_lane: list[LaneSignal]
    excel_lane: list[LaneSignal]
    instruction_lane: list[LaneSignal]
    revision_candidates: list[RevisionCandidate] = field(default_factory=list)


_PRIORITY = {"REVISION_TABLE": 3, "EXCEL_DIFF": 2, "INSTRUCTION": 1}


def _slugify(text: str) -> str:
    text = re.sub(r'[^\w一-鿿]', '_', text.strip())
    text = re.sub(r'_+', '_', text).strip('_')
    return text[:40] if text else "UNKNOWN"


def _normalise_row_label(text: str) -> str:
    """Remove display numbering so revision-table business names can match parsed rows."""
    label = re.sub(r"\s+", "", text.strip())
    label = re.sub(r"^其中[:：]?", "", label)
    label = re.sub(r"^\d+(?:\.\d+)*[、.．]?", "", label)
    label = re.sub(r"^[一二三四五六七八九十]+[、.．]", "", label)
    label = re.sub(r"^[（(][一二三四五六七八九十]+[）)]", "", label)
    return label


def _normalise_column_label(text: str) -> str:
    label = re.sub(r"\s+", "", text.strip())
    label = label.replace("·", "_").replace("：", "_").replace(":", "_")
    label = re.sub(r"^单位_万元_", "", label)
    return label


def _row_match_slugs(text: str) -> set[str]:
    labels = {text, _normalise_row_label(text)}
    expanded: set[str] = set()
    for label in labels:
        if not label:
            continue
        expanded.add(label)
        if label.endswith("债券"):
            expanded.add(label[:-1])
        elif label.endswith("债"):
            expanded.add(f"{label}券")
    return {_slugify(label) for label in expanded if label}


def _column_match_slugs(text: str) -> set[str]:
    label = _normalise_column_label(text)
    labels = {text, label}
    slug = _slugify(label)
    if slug.startswith("单位_万元_"):
        labels.add(slug.removeprefix("单位_万元_"))
    if slug.endswith("_期末余额"):
        labels.add(slug.removesuffix("_期末余额"))
    return {_slugify(label) for label in labels if label}


def _cell_ref_to_indexes(cell_ref: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"([A-Z]+)(\d+)", (cell_ref or "").upper())
    if not match:
        return None
    col_letters, row_text = match.groups()
    col = 0
    for char in col_letters:
        col = col * 26 + (ord(char) - ord("A") + 1)
    return int(row_text) - 1, col - 1


def _add_slug_mapping(
    slug_map: dict[tuple[str, str], RegReportingItem],
    row_slugs: set[str],
    col_slugs: set[str],
    item: RegReportingItem,
) -> None:
    for row_slug in row_slugs:
        for col_slug in col_slugs:
            slug_map.setdefault((row_slug, col_slug), item)


def _build_revision_slug_map(
    session: Session,
    obj: RegReportingObject,
    db_items: list[RegReportingItem],
) -> dict[tuple[str, str], RegReportingItem]:
    """Build exact and alias keys for revision-table row/column matching.

    G31 source templates keep row numbers in column A and business row names in
    column B/C. Older parsed items therefore have row_label like "1.0". This
    map augments those items with same-row business labels from template cells.
    """
    slug_map: dict[tuple[str, str], RegReportingItem] = {}
    source_ref_by_item: dict[str, tuple[int, int]] = {}
    for item in db_items:
        col_slugs = _column_match_slugs(item.column_label)
        _add_slug_mapping(slug_map, _row_match_slugs(item.row_label), col_slugs, item)
        indexes = _cell_ref_to_indexes(item.source_cell_ref)
        if indexes:
            source_ref_by_item[item.item_code] = indexes

    if not source_ref_by_item:
        return slug_map

    template_ids = [
        template.id
        for template in session.exec(
            select(RegReportingTemplate).where(
                RegReportingTemplate.reporting_object_id == obj.id,
                RegReportingTemplate.status == "ACTIVE",
            )
        ).all()
        if template.id is not None
    ]
    if not template_ids:
        return slug_map

    row_indexes = {row for row, _ in source_ref_by_item.values()}
    template_cells = session.exec(
        select(RegReportingTemplateCell).where(
            RegReportingTemplateCell.template_id.in_(template_ids),
            RegReportingTemplateCell.row_index.in_(row_indexes),
        )
    ).all()
    row_texts: dict[int, list[RegReportingTemplateCell]] = {}
    for cell in template_cells:
        if cell.raw_text.strip():
            row_texts.setdefault(cell.row_index, []).append(cell)

    for item in db_items:
        source_indexes = source_ref_by_item.get(item.item_code)
        if not source_indexes:
            continue
        row_index, source_col = source_indexes
        col_slugs = _column_match_slugs(item.column_label)
        for cell in row_texts.get(row_index, []):
            if cell.col_index >= source_col:
                continue
            if cell.raw_text.strip() == item.row_label.strip():
                continue
            _add_slug_mapping(slug_map, _row_match_slugs(cell.raw_text), col_slugs, item)

    return slug_map


def _diff_type_to_change_status(diff_type: str) -> str:
    mapping = {
        "NEW": "NEW",
        "REMOVED": "DELETED",
        "LABEL_CHANGED": "MODIFIED",
        "UNCHANGED": "UNCHANGED",
    }
    return mapping.get(diff_type, "UNCHANGED")


def _scan_instruction_text(
    instruction_text: str,
    db_items: list[RegReportingItem],
) -> list[LaneSignal]:
    """轻量级填报说明扫描：句子粒度匹配指标 row_label / column_label。

    不依赖 LLM，给三路融合 demo 提供可重现的 INSTRUCTION lane 数据。
    若同一指标在多个句子被提及，只保留置信度最高的一条。
    """
    if not instruction_text:
        return []

    sentences = re.split(r'[。；\n]+', instruction_text)
    hits: dict[str, LaneSignal] = {}

    for item in db_items:
        row = (item.row_label or "").strip()
        col = (item.column_label or "").strip()
        if len(row) < 2 and len(col) < 2:
            continue
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            row_hit = len(row) >= 2 and row in s
            col_hit = len(col) >= 2 and col in s
            if not (row_hit or col_hit):
                continue
            # 行列同时命中置信度更高
            conf = 0.75 if (row_hit and col_hit) else 0.55
            evidence = s[:80]
            existing = hits.get(item.item_code)
            if existing is None or conf > existing.confidence:
                hits[item.item_code] = LaneSignal(
                    item_code=item.item_code,
                    row_label=item.row_label,
                    column_label=item.column_label,
                    change_type="MODIFIED",
                    confidence=conf,
                    evidence=f"填报说明：{evidence}",
                )
    return list(hits.values())


def scan_and_annotate(
    session: Session,
    object_code: str,
    revision_entries: list[RevisionEntry] | None = None,
    excel_diffs: list[ExcelDiffEntry] | None = None,
    instruction_text: str | None = None,
) -> ScanReport:
    """
    根据信号源更新 change_status，返回三路扫描报告。
    幂等：重复调用效果相同（只会覆盖为新状态，不累加）。
    """
    obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == object_code)
    ).first()
    if obj is None:
        return ScanReport(results=[], revision_lane=[], excel_lane=[], instruction_lane=[])

    db_items = filter_analysis_items(session.exec(
        select(RegReportingItem).where(
            RegReportingItem.reporting_object_id == obj.id
        )
    ).all())

    code_map: dict[str, RegReportingItem] = {}
    for item in db_items:
        code_map[item.item_code] = item
    slug_map = _build_revision_slug_map(session, obj, db_items)

    # 三路原始命中
    revision_lane: list[LaneSignal] = []
    excel_lane: list[LaneSignal] = []
    instruction_lane: list[LaneSignal] = []
    revision_candidates: list[RevisionCandidate] = []

    # 每个 item_code 被哪些源命中过（用于 overridden 关系）
    hits_by_item: dict[str, list[tuple[str, str, float, str]]] = {}

    def _record(item: RegReportingItem, source: str, change_type: str, conf: float, evidence: str) -> LaneSignal:
        signal = LaneSignal(
            item_code=item.item_code,
            row_label=item.row_label,
            column_label=item.column_label,
            change_type=change_type,
            confidence=conf,
            evidence=evidence,
        )
        hits_by_item.setdefault(item.item_code, []).append((source, change_type, conf, evidence))
        return signal

    # ── 信号源 1：修订对照表 ───────────────────────────────────────────────────
    if revision_entries:
        for entry in revision_entries:
            if entry.table_code.upper() != object_code.upper():
                continue

            # v2 字段维度数据汇总（candidate 上要带的所有 v2 元信息）
            evidence_text = entry.change_summary or entry.change_desc or entry.regulation_evidence or entry.change_type
            v2_meta = {
                "revision_id": entry.revision_id,
                "regime_version": entry.regime_version,
                "field_code": entry.field_code,
                "field_name": entry.field_name,
                "change_dimensions": list(entry.change_dimensions),
                "change_summary": entry.change_summary,
                "before_value": dict(entry.before_value),
                "after_value": dict(entry.after_value),
                "regulation_evidence": entry.regulation_evidence,
                "evidence_source_ref": entry.evidence_source_ref,
                "affected_cells": list(entry.affected_cells),
                "effective_date": entry.effective_date,
            }

            # 优先路径：affected_cells 非空 → 直接按 item_code 命中（最准，跳过 slug 匹配）
            matched_items: list[RegReportingItem] = []
            if entry.affected_cells:
                for cell_code in entry.affected_cells:
                    item = code_map.get(cell_code)
                    if item is not None:
                        matched_items.append(item)

            # 兜底路径：affected_cells 为空或没命中 → 走原有 row+col slug 匹配
            if not matched_items:
                for rslug in _row_match_slugs(entry.row_label):
                    for cslug in _column_match_slugs(entry.column_label):
                        m = slug_map.get((rslug, cslug))
                        if m is not None:
                            matched_items.append(m)
                            break
                    if matched_items:
                        break

            if matched_items:
                # 1 个 RevisionEntry → 1 个 RevisionCandidate（field-level），但 lane 信号仍按 cell 展开
                matched_codes = [m.item_code for m in matched_items]
                revision_candidates.append(RevisionCandidate(
                    table_code=entry.table_code,
                    section=entry.section,
                    row_label=entry.row_label,
                    column_label=entry.column_label,
                    change_type=entry.change_type,
                    change_desc=entry.change_desc,
                    match_status="MATCHED_EXISTING",
                    matched_item_code=matched_codes[0],
                    matched_item_codes=matched_codes,
                    confidence=0.95,
                    evidence=f"修订对照表：{evidence_text}",
                    reason=(
                        f"按 affected_cells 直接命中 {len(matched_codes)} 个系统指标格（v2 字段维度路径）"
                        if entry.affected_cells
                        else f"按表号、业务行名/同排表样别名、列标识归一化匹配到 {len(matched_codes)} 个系统已有指标格"
                    ),
                    **v2_meta,
                ))
                # lane 信号：仍按 cell 展开，让 change_status 能逐格更新
                for matched in matched_items:
                    revision_lane.append(_record(
                        matched, "REVISION_TABLE", entry.change_type, 0.95,
                        f"修订对照表：{evidence_text}",
                    ))
            else:
                indicator_hint = entry.field_name or entry.row_label
                composite_match = build_composite_match(
                    session=session,
                    table_code=entry.table_code,
                    indicator_hint=indicator_hint,
                    evidence_text=evidence_text,
                )
                if composite_match is not None:
                    revision_candidates.append(RevisionCandidate(
                        table_code=entry.table_code,
                        section=entry.section,
                        row_label=entry.row_label,
                        column_label=entry.column_label,
                        change_type=entry.change_type,
                        change_desc=entry.change_desc,
                        match_status=composite_match.match_type,
                        matched_item_codes=composite_match.reporting_item_codes,
                        confidence=composite_match.confidence,
                        evidence=f"修订对照表：{evidence_text}",
                        reason="未精确落格，但命中“分类概念 + 度量概念”组合规则，需人工确认。",
                        composite_match=composite_match.to_dict(),
                        **v2_meta,
                    ))
                    continue
                semantic_field_match = build_semantic_field_match(
                    session=session,
                    table_code=entry.table_code,
                    indicator_hint=indicator_hint,
                    evidence_text=evidence_text,
                )
                if semantic_field_match is not None:
                    revision_candidates.append(RevisionCandidate(
                        table_code=entry.table_code,
                        section=entry.section,
                        row_label=entry.row_label,
                        column_label=entry.column_label,
                        change_type=entry.change_type,
                        change_desc=entry.change_desc,
                        match_status=semantic_field_match.match_type,
                        matched_item_codes=semantic_field_match.reporting_item_codes,
                        confidence=semantic_field_match.confidence,
                        evidence=f"修订对照表：{evidence_text}",
                        reason="未精确落格，但命中报表范围内的维度/过滤字段语义候选，需人工确认。",
                        composite_match=semantic_field_match.to_dict(),
                        **v2_meta,
                    ))
                    continue
                revision_candidates.append(RevisionCandidate(
                    table_code=entry.table_code,
                    section=entry.section,
                    row_label=entry.row_label,
                    column_label=entry.column_label,
                    change_type=entry.change_type,
                    change_desc=entry.change_desc,
                    match_status=f"UNMATCHED_{entry.change_type}",
                    matched_item_codes=[],
                    confidence=0.70 if entry.change_type == "NEW" else 0.55,
                    evidence=f"修订对照表：{evidence_text}",
                    reason="修订对照表已识别，但未匹配到系统已有指标格；可作为新增/待确认候选进入人工或LLM复核",
                    **v2_meta,
                ))

    # ── 信号源 2：Excel 结构差异 ──────────────────────────────────────────────
    if excel_diffs:
        for diff in excel_diffs:
            matched = code_map.get(diff.item_code)
            if matched is None:
                rslug = _slugify(diff.row_label)
                cslug = _slugify(diff.column_label)
                matched = slug_map.get((rslug, cslug))
            if matched:
                excel_lane.append(_record(
                    matched, "EXCEL_DIFF",
                    _diff_type_to_change_status(diff.diff_type),
                    0.80, diff.evidence,
                ))

    # ── 信号源 3：填报说明关键词扫描 ───────────────────────────────────────────
    if instruction_text:
        instruction_lane = _scan_instruction_text(instruction_text, db_items)
        for sig in instruction_lane:
            hits_by_item.setdefault(sig.item_code, []).append(
                ("INSTRUCTION", sig.change_type, sig.confidence, sig.evidence),
            )

    # ── 优先级合并 ──────────────────────────────────────────────────────────
    results: list[ItemChangeResult] = []
    winners_by_item: dict[str, str] = {}  # item_code -> 胜出 source
    for item_code, hits in hits_by_item.items():
        # 取最高优先级
        winner = max(hits, key=lambda h: _PRIORITY.get(h[0], 0))
        source, new_status, conf, evidence = winner
        winners_by_item[item_code] = source
        overridden = [s for (s, _, _, _) in hits if s != source]
        db_item = code_map.get(item_code)
        if db_item is None:
            continue
        old_status = db_item.change_status or ""
        if old_status != new_status:
            db_item.change_status = new_status
            session.add(db_item)
        results.append(ItemChangeResult(
            item_code=item_code,
            row_label=db_item.row_label,
            column_label=db_item.column_label,
            old_status=old_status,
            new_status=new_status,
            source=source,
            confidence=conf,
            evidence=evidence,
            overridden_sources=overridden,
        ))

    # 标记 won
    for lane, src_key in (
        (revision_lane, "REVISION_TABLE"),
        (excel_lane, "EXCEL_DIFF"),
        (instruction_lane, "INSTRUCTION"),
    ):
        for sig in lane:
            sig.won = winners_by_item.get(sig.item_code) == src_key

    session.commit()
    return ScanReport(
        results=results,
        revision_lane=revision_lane,
        excel_lane=excel_lane,
        instruction_lane=instruction_lane,
        revision_candidates=revision_candidates,
    )


def build_change_summary(
    results: list[ItemChangeResult],
    revision_candidates: list[RevisionCandidate] | None = None,
) -> str:
    """生成指标级变更扫描的摘要文字。"""
    revision_candidates = revision_candidates or []
    label_map = {"NEW": "新增", "MODIFIED": "修改", "DELETED": "删除", "UNCHANGED": "无变化"}
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r.new_status] = by_status.get(r.new_status, 0) + 1

    parts = []
    for status in ("NEW", "MODIFIED", "DELETED", "UNCHANGED"):
        count = by_status.get(status, 0)
        if count:
            parts.append(f"{label_map.get(status, status)} {count} 个")
    source_counts: dict[str, int] = {}
    for r in results:
        source_counts[r.source] = source_counts.get(r.source, 0) + 1

    candidate_desc = ""
    unmatched_change_count = 0
    if revision_candidates:
        unmatched = [c for c in revision_candidates if c.match_status.startswith("UNMATCHED_")]
        unmatched_new = [c for c in unmatched if c.change_type == "NEW"]
        unmatched_changes = [c for c in unmatched if c.change_type in {"NEW", "MODIFIED", "DELETED"}]
        unmatched_change_count = len(unmatched_changes)
        unmatched_by_type: dict[str, int] = {}
        for candidate in unmatched_changes:
            unmatched_by_type[candidate.change_type] = unmatched_by_type.get(candidate.change_type, 0) + 1
        change_parts = [
            f"{label_map.get(status, status)} {unmatched_by_type[status]} 条"
            for status in ("NEW", "MODIFIED", "DELETED")
            if unmatched_by_type.get(status)
        ]
        change_desc = f"识别变更信号 {unmatched_change_count} 条"
        if change_parts:
            change_desc = f"{change_desc}（{'、'.join(change_parts)}）"
        candidate_desc = (
            f"识别修订对照表候选 {len(revision_candidates)} 条，"
            f"其中未落格 {len(unmatched)} 条、新增候选 {len(unmatched_new)} 条；"
            f"{change_desc}。"
        )

    status_desc = "、".join(parts) if parts else "暂无已落格变更"
    source_desc_parts = [f"{k}({v}条已落格)" for k, v in source_counts.items()]
    if unmatched_change_count:
        source_desc_parts.append(f"REVISION_TABLE({unmatched_change_count}条未落格)")
    source_suffix = f"信号来源：{'；'.join(source_desc_parts)}" if source_desc_parts else "信号来源：无变更信号"
    return f"扫描命中 {len(results)} 个指标格：{status_desc}。{candidate_desc}{source_suffix}"
