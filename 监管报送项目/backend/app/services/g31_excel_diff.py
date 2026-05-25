"""G31（及其他报表）Excel 版本结构差异检测

将新解析的 ExcelParseResult 与库中现有 RegReportingItem 对比，
检测出新增/删除/标签变化的指标格，便于后续更新 change_status。

差异检测策略：
  - 以 (row_slug, col_slug) 作为匹配键（item_code 的后两段）
  - NEW：新 Excel 中有但库里没有的
  - REMOVED：库里有但新 Excel 中没有的
  - UNCHANGED：完全相同
  - LABEL_CHANGED：位置相同但 row_label 或 column_label 有变化
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.db_models import RegReportingItem, RegReportingObject
from app.services.excel_parser import ExcelParseResult
from app.services.reporting_item_scope import filter_analysis_items


@dataclass
class ExcelDiffEntry:
    item_code: str
    row_label: str
    column_label: str
    diff_type: str   # NEW / REMOVED / LABEL_CHANGED / UNCHANGED
    old_row_label: str = ""
    old_col_label: str = ""
    evidence: str = ""


def _slugify(text: str) -> str:
    text = re.sub(r'[^\w一-鿿]', '_', text.strip())
    text = re.sub(r'_+', '_', text).strip('_')
    return text[:40] if text else "UNKNOWN"


def diff_excel_with_db(
    session: Session,
    object_code: str,
    new_result: ExcelParseResult,
) -> list[ExcelDiffEntry]:
    """
    比对新 Excel 与库中现有 items，返回差异列表。
    只对可参与影响分析的指标格做比对：
    - is_fillable=True：业务可填指标
    - is_derived=True：派生/合计指标
    结构性单元格保留在 template_cells，但不计入业务指标差异。
    """
    obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == object_code)
    ).first()
    if obj is None:
        # 库中无该报表：全部视为 NEW
        return [
            ExcelDiffEntry(
                item_code=item["item_code"],
                row_label=item["row_label"],
                column_label=item["column_label"],
                diff_type="NEW",
                evidence="库中无此报表，全部指标视为新增",
            )
            for item in new_result.items
            if _is_analysis_item_dict(item)
        ]

    db_items = filter_analysis_items(session.exec(
        select(RegReportingItem).where(
            RegReportingItem.reporting_object_id == obj.id,
        )
    ).all())

    # 构建库中已有指标的 (row_slug, col_slug) → item 映射
    db_key_map: dict[tuple[str, str], RegReportingItem] = {}
    for db_item in db_items:
        row_slug = _slugify(db_item.row_label)
        col_slug = _slugify(db_item.column_label)
        db_key_map[(row_slug, col_slug)] = db_item

    # 构建新 Excel 中指标的映射
    new_key_map: dict[tuple[str, str], dict] = {}
    for item in new_result.items:
        if not _is_analysis_item_dict(item):
            continue
        row_slug = _slugify(item["row_label"])
        col_slug = _slugify(item["column_label"])
        new_key_map[(row_slug, col_slug)] = item

    diffs: list[ExcelDiffEntry] = []

    # 新增（在新 Excel 有、库中无）
    for key, item in new_key_map.items():
        if key not in db_key_map:
            diffs.append(ExcelDiffEntry(
                item_code=item["item_code"],
                row_label=item["row_label"],
                column_label=item["column_label"],
                diff_type="NEW",
                evidence=f"新版 Excel 新增：行[{item['row_label']}] 列[{item['column_label']}]",
            ))

    # 删除（库中有、新 Excel 无）
    for key, db_item in db_key_map.items():
        if key not in new_key_map:
            diffs.append(ExcelDiffEntry(
                item_code=db_item.item_code,
                row_label=db_item.row_label,
                column_label=db_item.column_label,
                diff_type="REMOVED",
                evidence=f"库中指标在新版 Excel 中消失：行[{db_item.row_label}] 列[{db_item.column_label}]",
            ))

    # 标签变化（同 slug 键但 label 文字不同）
    for key in new_key_map.keys() & db_key_map.keys():
        new_item = new_key_map[key]
        db_item = db_key_map[key]
        label_changed = (
            new_item["row_label"] != db_item.row_label
            or new_item["column_label"] != db_item.column_label
        )
        if label_changed:
            diffs.append(ExcelDiffEntry(
                item_code=db_item.item_code,
                row_label=new_item["row_label"],
                column_label=new_item["column_label"],
                diff_type="LABEL_CHANGED",
                old_row_label=db_item.row_label,
                old_col_label=db_item.column_label,
                evidence=(
                    f"标签变化：行 [{db_item.row_label}→{new_item['row_label']}] "
                    f"列 [{db_item.column_label}→{new_item['column_label']}]"
                ),
            ))

    return diffs


def _is_analysis_item_dict(item: dict) -> bool:
    return bool(item.get("is_fillable", False) or item.get("is_derived", False))


def summarise_diff(diffs: list[ExcelDiffEntry]) -> str:
    """生成可读的差异摘要文字。"""
    by_type: dict[str, int] = {}
    for d in diffs:
        by_type[d.diff_type] = by_type.get(d.diff_type, 0) + 1

    parts = []
    if by_type.get("NEW"):
        parts.append(f"新增 {by_type['NEW']} 个指标格")
    if by_type.get("REMOVED"):
        parts.append(f"删除 {by_type['REMOVED']} 个指标格")
    if by_type.get("LABEL_CHANGED"):
        parts.append(f"标签变化 {by_type['LABEL_CHANGED']} 个")
    return "；".join(parts) if parts else "与库中版本结构完全一致，无差异"
