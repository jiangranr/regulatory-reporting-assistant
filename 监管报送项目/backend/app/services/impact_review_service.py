import copy
import json
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.db_models import DataFieldCatalog, RegReportingItem, ReportingItemLineage
from app.models.enums import ResponsibleSystem
from app.models.schemas import ReportingImpactItemRead


# 旧抽象桶标签 —— 测试验收/归档支持单仍走这套映射；新分桶不依赖它。
SYSTEM_LABELS: dict[str, str] = {
    ResponsibleSystem.REG_REPORTING_SYSTEM.value: "监管报送系统",
    ResponsibleSystem.DATA_GOVERNANCE_PLATFORM.value: "数据治理平台",
    ResponsibleSystem.DATA_MART_ETL.value: "数据集市/ETL",
    ResponsibleSystem.SOURCE_SYSTEM.value: "业务源系统",
    ResponsibleSystem.DATA_QUALITY_PLATFORM.value: "数据质量平台",
    ResponsibleSystem.TEST_ACCEPTANCE.value: "测试验收",
    ResponsibleSystem.KNOWLEDGE_ARCHIVE.value: "知识归档",
}

# 当某条 lineage 缺 system_code（旧 impact 记录、语义匹配 fallback 等），
# 暂时归入 UNKNOWN 桶，让用户能看到并主动 reset_to_baseline。
_UNKNOWN_SYSTEM_CODE = "UNKNOWN"
_UNKNOWN_SYSTEM_NAME = "系统待确认"


def parse_review_content(value: str | dict | None) -> dict:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not value:
        return {"version": "v1", "items": []}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {"version": "v1", "items": []}
    return loaded if isinstance(loaded, dict) else {"version": "v1", "items": []}


def dump_review_content(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def build_baseline_from_impacts(impacts: list[ReportingImpactItemRead]) -> dict:
    """按真实 system_code 把 impact 字段分桶给前端复核。

    分桶完全依赖 impact.impacted_source_field_details[].system_code，那个字段
    由 analyzer 从 catalog.lineage 的 4 表 join（含 data_system_catalog）填充。
    REPORT_FIELD 也并入 details 列表，所以 rpt_xxx 字段会自然归到 RPT 系统桶。

    旧 impact 记录 details 为空时，所有字段落到 UNKNOWN 桶，让用户主动
    reset_to_baseline 触发重新分析。
    """
    items: list[dict[str, Any]] = []
    for impact in impacts:
        systems: dict[str, dict[str, Any]] = {}
        details = list(impact.impacted_source_field_details or [])

        # 1) 优先按 details 分桶（新路径，含 system_code）
        seen_codes: set[str] = set()
        for detail in details:
            code = str(detail.get("code") or "").strip()
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            role = detail.get("role") or ""
            _append_field(
                systems,
                detail,
                {
                    "field_code": code,
                    "field_name": detail.get("name") or code,
                    "lineage_role": role,
                    "source": "AI",
                    "selected": True,
                    "edited": False,
                    "removed": False,
                    "is_required": role == "REPORT_FIELD",
                },
            )

        # 2) 回退：details 缺失时按扁平 impacted_reporting_field/source_fields 兜底，
        #    全部归 UNKNOWN，避免数据不全导致 UI 空白。
        if not details:
            if impact.impacted_reporting_field:
                _append_unknown_field(
                    systems,
                    {
                        "field_code": impact.impacted_reporting_field,
                        "field_name": impact.impacted_reporting_field,
                        "lineage_role": "REPORT_FIELD",
                        "source": "AI",
                        "selected": True,
                        "edited": False,
                        "removed": False,
                        "is_required": True,
                    },
                )
            roles = impact.impacted_lineage_roles or []
            aligned_roles = roles if len(roles) == len(impact.impacted_source_fields) else []
            for index, field_code in enumerate(impact.impacted_source_fields):
                role = aligned_roles[index] if aligned_roles else "SOURCE_FIELD"
                _append_unknown_field(
                    systems,
                    {
                        "field_code": field_code,
                        "field_name": field_code,
                        "lineage_role": role,
                        "source": "AI",
                        "selected": True,
                        "edited": False,
                        "removed": False,
                        "is_required": False,
                    },
                )

        items.append(
            {
                "reporting_item_code": impact.reporting_item_code,
                "reporting_item_name": impact.reporting_item_code,
                "removed": False,
                "business_note": "",
                # 桶按 system_code 字典序输出，保证 UI 稳定
                "systems": [systems[code] for code in sorted(systems.keys())],
            }
        )
    return {"version": "v1", "items": items}


def reset_to_baseline(baseline: dict) -> dict:
    review = copy.deepcopy(baseline)
    for item in review.get("items", []):
        item["removed"] = False
        item["business_note"] = ""
        for system in item.get("systems", []):
            for field in system.get("fields", []):
                field["selected"] = True
                field["removed"] = False
                field["edited"] = False
    return review


def compute_stats(review: dict) -> dict:
    items = [item for item in review.get("items", []) if isinstance(item, dict)]
    systems = [
        system
        for item in items
        for system in item.get("systems", [])
        if isinstance(system, dict)
    ]
    fields = [
        field
        for system in systems
        for field in system.get("fields", [])
        if isinstance(field, dict)
    ]
    return {
        "total_items": len(items),
        "total_systems": len({system.get("responsible_system") for system in systems if system.get("responsible_system")}),
        "selected_fields": len([field for field in fields if field.get("selected") and not field.get("removed")]),
        "business_added_fields": len([field for field in fields if field.get("source") == "BUSINESS"]),
        "business_removed_fields": len([field for field in fields if field.get("removed") or not field.get("selected")]),
    }


def selected_fields_by_system(review: dict) -> dict[str, dict]:
    """把选中字段按 system_code 重新分组，给工单子单生成使用。

    保留 system_type/owner_team，让 routes_tasks 推 action_type 和 owner 时
    不用再去查 DB。
    """
    grouped: dict[str, dict] = {}
    for item in review.get("items", []):
        if not isinstance(item, dict) or item.get("removed"):
            continue
        item_code = str(item.get("reporting_item_code") or "").strip()
        item_name = str(item.get("reporting_item_name") or item_code).strip()
        note = str(item.get("business_note") or "").strip()
        for system in item.get("systems", []):
            if not isinstance(system, dict):
                continue
            system_code = str(system.get("responsible_system") or "").strip()
            if not system_code:
                continue
            fields = [
                field
                for field in system.get("fields", [])
                if isinstance(field, dict) and field.get("selected") and not field.get("removed")
            ]
            if not fields:
                continue
            bucket = grouped.setdefault(
                system_code,
                {
                    "responsible_system": system_code,
                    "responsible_system_zh": system.get("responsible_system_zh") or system_code,
                    "system_type": system.get("system_type") or "",
                    "owner_team": system.get("owner_team") or "",
                    "items": [],
                    "business_notes": [],
                },
            )
            bucket["items"].append(
                {
                    "reporting_item_code": item_code,
                    "reporting_item_name": item_name,
                    "fields": copy.deepcopy(fields),
                }
            )
            if note and note not in bucket["business_notes"]:
                bucket["business_notes"].append(note)
    return grouped


def now_utc() -> datetime:
    return datetime.utcnow()


def apply_confirmed_review_to_lineage(review: dict, session: Session) -> dict:
    """审核确认后将 review 结果写回 ReportingItemLineage。

    Returns: {confirmed_count, retired_count, created_count}
    """
    confirmed_count = 0
    retired_count = 0
    created_count = 0

    for item in review.get("items", []):
        if not isinstance(item, dict):
            continue
        item_code = str(item.get("reporting_item_code") or "").strip()
        if not item_code:
            continue

        reg_item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        if reg_item is None or reg_item.id is None:
            continue

        # 整个指标被删除 → 所有血缘退役
        if item.get("removed"):
            for lin in session.exec(
                select(ReportingItemLineage).where(
                    ReportingItemLineage.reporting_item_id == reg_item.id
                )
            ).all():
                if lin.mapping_status != "RETIRED":
                    lin.mapping_status = "RETIRED"
                    session.add(lin)
                    retired_count += 1
            continue

        for system in item.get("systems", []):
            if not isinstance(system, dict):
                continue
            for field in system.get("fields", []):
                if not isinstance(field, dict):
                    continue
                field_code = str(field.get("field_code") or "").strip()
                if not field_code:
                    continue

                data_field = session.exec(
                    select(DataFieldCatalog).where(DataFieldCatalog.field_code == field_code)
                ).first()
                if data_field is None or data_field.id is None:
                    continue

                lineage_role = str(field.get("lineage_role") or "SOURCE_FIELD").strip()
                is_selected = field.get("selected", True)
                is_removed = field.get("removed", False)
                source = str(field.get("source") or "AI").strip()

                existing = session.exec(
                    select(ReportingItemLineage).where(
                        ReportingItemLineage.reporting_item_id == reg_item.id,
                        ReportingItemLineage.data_field_id == data_field.id,
                        ReportingItemLineage.lineage_role == lineage_role,
                    )
                ).first()

                if is_removed or not is_selected:
                    if existing and existing.mapping_status != "RETIRED":
                        existing.mapping_status = "RETIRED"
                        session.add(existing)
                        retired_count += 1
                elif source == "BUSINESS" and existing is None:
                    session.add(ReportingItemLineage(
                        reporting_item_id=reg_item.id,
                        data_field_id=data_field.id,
                        lineage_role=lineage_role,
                        mapping_status="CONFIRMED",
                        confidence_level="HIGH",
                        evidence="业务人员审核确认新增",
                    ))
                    created_count += 1
                else:
                    if existing:
                        if existing.mapping_status != "CONFIRMED":
                            existing.mapping_status = "CONFIRMED"
                            session.add(existing)
                            confirmed_count += 1
                    else:
                        session.add(ReportingItemLineage(
                            reporting_item_id=reg_item.id,
                            data_field_id=data_field.id,
                            lineage_role=lineage_role,
                            mapping_status="CONFIRMED",
                            confidence_level="MEDIUM",
                        ))
                        created_count += 1

    session.commit()
    return {
        "confirmed_count": confirmed_count,
        "retired_count": retired_count,
        "created_count": created_count,
    }


def _append_field(
    systems: dict[str, dict[str, Any]],
    detail: dict[str, Any],
    field: dict[str, Any],
) -> None:
    system_code = (detail.get("system_code") or "").strip() or _UNKNOWN_SYSTEM_CODE
    system_name = (detail.get("system_name") or "").strip() or (
        _UNKNOWN_SYSTEM_NAME if system_code == _UNKNOWN_SYSTEM_CODE else system_code
    )
    system = systems.setdefault(
        system_code,
        {
            "responsible_system": system_code,
            "responsible_system_zh": system_name,
            "system_type": (detail.get("system_type") or "").strip(),
            "owner_team": (detail.get("owner_team") or "").strip(),
            "fields": [],
        },
    )
    if field["field_code"] not in {f.get("field_code") for f in system["fields"]}:
        system["fields"].append(field)


def _append_unknown_field(
    systems: dict[str, dict[str, Any]],
    field: dict[str, Any],
) -> None:
    _append_field(
        systems,
        {"system_code": _UNKNOWN_SYSTEM_CODE, "system_name": _UNKNOWN_SYSTEM_NAME},
        field,
    )
