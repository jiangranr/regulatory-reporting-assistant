from pydantic import BaseModel

from app.models.enums import RiskLevel
from app.services.reporting_change_extractor import ReportingChangeDraft
from app.services.reporting_seed import ReportingSeedCatalog
from app.services.ticket_scope_classifier import classify_scope_range_tickets


class ReportingImpactDraft(BaseModel):
    reporting_item_code: str
    impact_type: str
    impacted_reporting_field: str = ""
    impacted_source_fields: list[str] = []
    impacted_lineage_roles: list[str] = []
    impact_reason: str
    recommended_action: str
    ticket_parent_type: str = ""
    required_sub_ticket_types: list[str] = []
    conditional_sub_ticket_types: list[str] = []
    sub_ticket_triggers: dict[str, str] = {}
    confidence_level: str = "MEDIUM"
    risk_level: RiskLevel = RiskLevel.MEDIUM


def analyze_reporting_impacts(
    changes: list[ReportingChangeDraft],
    catalog: ReportingSeedCatalog,
) -> list[ReportingImpactDraft]:
    lineage_by_item: dict[str, list[dict[str, str]]] = {}
    for lineage in catalog.lineage:
        lineage_by_item.setdefault(lineage["reporting_item_code"], []).append(lineage)

    item_names = {item["item_code"]: item["item_name"] for item in catalog.reporting_items}

    # 按 reporting_item_code 去重：多个变更命中同一指标时合并为 1 条 impact。
    # 这是数据质量的"二次防线"——当 matcher 因 row_label 缺失而把 16 个不同 cell 折叠到
    # 同一 item 时，避免在影响清单上展示 16 行视觉重复。
    # 代表 change 取置信度最高的；变更总数计入 impact_reason，让用户感知折叠。
    grouped: dict[str, list[ReportingChangeDraft]] = {}
    for change in changes:
        if not change.reporting_item_code:
            continue
        grouped.setdefault(change.reporting_item_code, []).append(change)

    impacts: list[ReportingImpactDraft] = []
    for item_code, group in grouped.items():
        change = max(group, key=lambda c: c.confidence_score)
        signal_count = len(group)
        semantic_impact = _semantic_change_to_impact(change)
        if semantic_impact is not None:
            impacts.append(semantic_impact)
            continue

        lineage_rows = lineage_by_item.get(change.reporting_item_code, [])
        reporting_fields = [
            row["data_field_code"] for row in lineage_rows if row["lineage_role"] == "REPORT_FIELD"
        ]
        source_fields = [
            row["data_field_code"]
            for row in lineage_rows
            if row["lineage_role"] in {"SOURCE_FIELD", "FILTER_FIELD", "DIMENSION_FIELD"}
        ]
        roles = list(dict.fromkeys(row["lineage_role"] for row in lineage_rows))
        item_name = item_names.get(change.reporting_item_code, change.reporting_item_code)
        ticket_scope = classify_scope_range_tickets(
            change_type=change.change_type,
            lineage_roles=roles,
            source_fields=source_fields,
            evidence_text=change.evidence_text,
        )
        impacts.append(
            ReportingImpactDraft(
                reporting_item_code=change.reporting_item_code,
                impact_type="INDICATOR_SCOPE",
                impacted_reporting_field=reporting_fields[0] if reporting_fields else "",
                impacted_source_fields=list(dict.fromkeys(source_fields)),
                impacted_lineage_roles=roles,
                impact_reason=(
                    f"{item_name}发生{change.change_type}"
                    + (f"（合并 {signal_count} 条相关变更信号）" if signal_count > 1 else "")
                    + "，需要复核报送字段、资金同业源字段、交易对手维度、产品口径和加工逻辑。"
                ),
                recommended_action=(
                    "生成口径确认工单、数据映射工单、报送加工工单和回归测试工单；"
                    "重点确认同业交易余额、交易对手机构类型、产品类型、期限和流动性分类口径。"
                ),
                ticket_parent_type=ticket_scope.ticket_parent_type,
                required_sub_ticket_types=ticket_scope.required_sub_ticket_types,
                conditional_sub_ticket_types=ticket_scope.conditional_sub_ticket_types,
                sub_ticket_triggers=ticket_scope.sub_ticket_triggers,
                confidence_level="HIGH" if change.confidence_score >= 0.8 else "MEDIUM",
                risk_level=RiskLevel.HIGH if change.reporting_object_code in {"G24", "G21", "G25"} else RiskLevel.MEDIUM,
            )
        )
    return impacts


def _semantic_change_to_impact(change: ReportingChangeDraft) -> ReportingImpactDraft | None:
    if change.match_status not in {"COMPOSITE_SEMANTIC_MATCH", "SEMANTIC_FIELD_MATCH"}:
        return None
    match = change.composite_match if isinstance(change.composite_match, dict) else {}
    if not match:
        return None

    field_roles: list[tuple[str, str]] = []
    for field in match.get("measure_fields") or []:
        if not isinstance(field, dict):
            continue
        field_code = str(field.get("field_code", "")).strip()
        if not field_code:
            continue
        field_roles.append((field_code, _normalise_semantic_field_role(str(field.get("field_role", "")))))

    known_fields = {field_code for field_code, _role in field_roles}
    for field_code in match.get("measure_field_codes") or []:
        field_code = str(field_code).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((field_code, "SOURCE_FIELD"))
            known_fields.add(field_code)

    conditions = match.get("filter_conditions") or match.get("conditions") or []
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        field_code = str(condition.get("field_code", "")).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((field_code, "FILTER_FIELD"))
            known_fields.add(field_code)

    for field_code in match.get("condition_field_codes") or []:
        field_code = str(field_code).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((field_code, "FILTER_FIELD"))
            known_fields.add(field_code)

    if not field_roles:
        return None

    impacted_fields = [field_code for field_code, _role in field_roles]
    roles = list(dict.fromkeys(role for _field_code, role in field_roles))
    ticket_scope = classify_scope_range_tickets(
        change_type=change.change_type,
        lineage_roles=roles,
        source_fields=impacted_fields,
        evidence_text=change.evidence_text,
    )

    indicator_hint = (
        str(match.get("indicator_hint") or "").strip()
        or change.indicator_hint
        or change.reporting_item_code
    )
    match_type = str(match.get("match_type") or change.match_status)
    if match_type == "SEMANTIC_FIELD_MATCH":
        impact_type = "SEMANTIC_FIELD_SCOPE"
        reason = (
            f"{indicator_hint}未精确落格，已按报表范围内语义字段生成候选影响项，"
            "需要复核字段含义、口径适用范围和后续加工规则。"
        )
    else:
        impact_type = "COMPOSITE_SEMANTIC_SCOPE"
        measure_phrase = str(match.get("measure_phrase") or "度量").strip()
        condition_phrase = str(match.get("condition_phrase") or "分类条件").strip()
        reason = (
            f"{indicator_hint}未精确落格，已按“{condition_phrase} + {measure_phrase}”"
            "生成组合候选影响项，需要复核金额字段、过滤条件和迁移口径。"
        )

    return ReportingImpactDraft(
        reporting_item_code=change.reporting_item_code,
        impact_type=impact_type,
        impacted_reporting_field=indicator_hint,
        impacted_source_fields=impacted_fields,
        impacted_lineage_roles=roles,
        impact_reason=reason,
        recommended_action=(
            "生成口径确认工单、字段映射复核工单、报送加工调整工单和回归测试工单；"
            "保持待确认状态，人工确认后再固化到正式报送口径。"
        ),
        ticket_parent_type=ticket_scope.ticket_parent_type,
        required_sub_ticket_types=ticket_scope.required_sub_ticket_types,
        conditional_sub_ticket_types=ticket_scope.conditional_sub_ticket_types,
        sub_ticket_triggers=ticket_scope.sub_ticket_triggers,
        confidence_level="HIGH" if change.confidence_score >= 0.8 else "MEDIUM",
        risk_level=RiskLevel.MEDIUM,
    )


def _normalise_semantic_field_role(field_role: str) -> str:
    role = field_role.strip().upper()
    if role in {"REPORT_FIELD", "REPORT_MEASURE_FIELD"}:
        return "REPORT_FIELD"
    if role in {"FILTER_FIELD", "CONDITION_FIELD"}:
        return "FILTER_FIELD"
    if role in {"DIMENSION_FIELD"}:
        return "DIMENSION_FIELD"
    return "SOURCE_FIELD"
