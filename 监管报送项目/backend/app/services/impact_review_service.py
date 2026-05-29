import copy
import json
from datetime import datetime
from typing import Any

from app.models.enums import ResponsibleSystem
from app.models.schemas import ReportingImpactItemRead


SYSTEM_LABELS: dict[str, str] = {
    ResponsibleSystem.REG_REPORTING_SYSTEM.value: "监管报送系统",
    ResponsibleSystem.DATA_GOVERNANCE_PLATFORM.value: "数据治理平台",
    ResponsibleSystem.DATA_MART_ETL.value: "数据集市/ETL",
    ResponsibleSystem.SOURCE_SYSTEM.value: "业务源系统",
    ResponsibleSystem.DATA_QUALITY_PLATFORM.value: "数据质量平台",
    ResponsibleSystem.TEST_ACCEPTANCE.value: "测试验收",
    ResponsibleSystem.KNOWLEDGE_ARCHIVE.value: "知识归档",
}


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
    items: list[dict[str, Any]] = []
    for impact in impacts:
        systems: dict[str, dict[str, Any]] = {}
        if impact.impacted_reporting_field:
            _append_field(
                systems,
                ResponsibleSystem.DATA_MART_ETL.value,
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
            system_code = _system_for_lineage_role(role)
            _append_field(
                systems,
                system_code,
                {
                    "field_code": field_code,
                    "field_name": field_code,
                    "lineage_role": role or "SOURCE_FIELD",
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
                "systems": list(systems.values()),
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
            if system_code not in SYSTEM_LABELS:
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
                    "responsible_system_zh": SYSTEM_LABELS[system_code],
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


def _append_field(systems: dict[str, dict[str, Any]], system_code: str, field: dict[str, Any]) -> None:
    system = systems.setdefault(
        system_code,
        {
            "responsible_system": system_code,
            "responsible_system_zh": SYSTEM_LABELS[system_code],
            "fields": [],
        },
    )
    if field["field_code"] not in {f.get("field_code") for f in system["fields"]}:
        system["fields"].append(field)


def _system_for_lineage_role(role: str) -> str:
    if role in {"REPORT_FIELD", "DERIVED_FIELD", "MAPPING_FIELD"}:
        return ResponsibleSystem.DATA_MART_ETL.value
    return ResponsibleSystem.SOURCE_SYSTEM.value
