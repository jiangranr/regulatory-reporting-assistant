"""注册具体业务路径的 executor。

每个 executor 接受 case 的 `inputs` dict，调用真实业务函数，
返回 list[dict]（每条是一个 signal-like 字典，可用 framework 断言）。

新增 target 模板：

    @register_target("my_path")
    def _my_path(inputs: dict) -> list[dict]:
        result = call_some_service(inputs["foo"])
        return [s.model_dump() for s in result.signals]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

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

from .framework import register_target

# 项目根路径（用于解析 case 里的相对路径）
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / raw).resolve()


def _session_with_template_seed(
    parse_result: ExcelParseResult,
    *,
    object_code: str,
    version_code: str,
) -> Session:
    """基于 baseline xls 解析结果，构造一个含模板/指标/单元格的内存 DB。

    与 `tests/test_g31_excel_diff.py::_session_with_g31_items` 等价，
    但抽出来供 eval framework 复用（不污染 unit test 的命名空间）。
    """

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    system = RegReportingSystem(system_code="1104", system_name="1104")
    session.add(system)
    session.commit()
    session.refresh(system)

    version = RegReportingVersion(
        reporting_system_id=system.id,
        version_code=version_code,
        version_name=version_code,
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    obj = RegReportingObject(
        reporting_system_id=system.id,
        reporting_version_id=version.id,
        object_code=object_code,
        object_name=object_code,
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

    # 把 baseline xls 的 template_cells 落进 DB，让 diff 路径能命中"老版表样"
    template = RegReportingTemplate(
        reporting_object_id=obj.id,
        template_code=f"{object_code}.PART_I.{version_code}",
        template_name=f"{object_code} {version_code}",
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    for cell in parse_result.template_cells:
        session.add(
            RegReportingTemplateCell(
                template_id=template.id,
                sheet_name=cell["sheet_name"],
                row_index=int(cell["row_index"]),
                col_index=int(cell["col_index"]),
                excel_ref=cell["excel_ref"],
                raw_text=cell["raw_text"],
                cell_type=cell["cell_type"],
                style_json=cell["style_json"],
                merge_json=cell["merge_json"],
            )
        )

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


@register_target("triplet_excel_diff")
def _run_triplet_excel_diff(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """新版 xls vs 数据库 baseline 的 diff 路径（不调 LLM，纯规则）。

    inputs 期望字段：
      object_code: str            报表代码，如 "G31"
      baseline_file: str          老版表样 xls（相对项目根或绝对路径），用作 DB seed
      template_file: str          新版表样 xls，传给 diff 函数
      baseline_version: str=251   老版版本号（仅用于 DB 标识）
    """

    object_code = inputs["object_code"]
    baseline_path = _resolve_path(inputs["baseline_file"])
    new_path = _resolve_path(inputs["template_file"])
    baseline_version = inputs.get("baseline_version", "baseline")

    if not baseline_path.exists():
        raise FileNotFoundError(f"baseline_file 不存在: {baseline_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"template_file 不存在: {new_path}")

    baseline_parse = parse_excel(baseline_path, object_code)
    session = _session_with_template_seed(
        baseline_parse,
        object_code=object_code,
        version_code=baseline_version,
    )

    new_parse = parse_excel(new_path, object_code)
    diffs = diff_excel_with_db(session, object_code, new_parse)

    # 把 ExcelDiffEntry 转成 signal-like dict（对齐 routes_documents._excel_diffs_to_profile_signals
    # 的关键字段，便于断言）
    _ = select  # 触发 import（避免 ruff 抱怨）
    signals: list[dict[str, Any]] = []
    diff_type_map = {
        "REMOVED": "DELETE",
        "NEW": "ADD",
        "LABEL_CHANGED": "MODIFY",
    }
    for diff in diffs:
        change_type = diff_type_map.get(diff.diff_type, "UNCLEAR")
        indicator_hint = f"{diff.row_label} × {diff.column_label}".strip(" ×")
        signals.append(
            {
                "table_code": object_code,
                "section_hint": "PART_I",
                "indicator_hint": indicator_hint,
                "change_type": change_type,
                "evidence_text": diff.row_label or diff.column_label or "",
                "item_code": diff.item_code,
                "row_label": diff.row_label,
                "column_label": diff.column_label,
                "diff_type": diff.diff_type,
            }
        )
    return signals
