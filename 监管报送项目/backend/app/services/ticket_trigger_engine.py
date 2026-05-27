from dataclasses import dataclass, field

from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft


@dataclass(frozen=True)
class TicketTrigger:
    action_type: ActionTicketType
    responsible_system: ResponsibleSystem
    trigger_reasons: list[str] = field(default_factory=list)
    related_impact_codes: list[str] = field(default_factory=list)


def build_ticket_triggers(
    impacts: list[ReportingImpactDraft],
    document_text: str,
) -> list[TicketTrigger]:
    candidates: list[TicketTrigger] = []

    impact_codes = [impact.reporting_item_code for impact in impacts if impact.reporting_item_code]
    roles = {role for impact in impacts for role in impact.impacted_lineage_roles}
    has_source_gap = any(
        impact.reporting_item_code and not impact.impacted_source_fields
        for impact in impacts
    )
    text = document_text or ""

    if impact_codes:
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.SCOPE_CONFIRM,
            responsible_system=ResponsibleSystem.REG_REPORTING_SYSTEM,
            trigger_reasons=["REPORTING_ITEM_SCOPE_CHANGE"],
            related_impact_codes=impact_codes,
        ))

    if roles & {"REPORT_FIELD", "SOURCE_FIELD", "DIMENSION_FIELD", "FILTER_FIELD"}:
        reasons = ["REPORT_OR_SOURCE_FIELD_IMPACT"]
        if roles & {"DIMENSION_FIELD", "FILTER_FIELD"}:
            reasons.append("DIMENSION_OR_FILTER_FIELD_IMPACT")
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.DATA_MAPPING,
            responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
            trigger_reasons=reasons,
            related_impact_codes=impact_codes,
        ))

    if has_source_gap:
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.SOURCE_SYSTEM_CHANGE,
            responsible_system=ResponsibleSystem.SOURCE_SYSTEM,
            trigger_reasons=["SOURCE_FIELD_GAP"],
            related_impact_codes=impact_codes,
        ))

    if _mentions_processing(text):
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.REPORT_PROCESSING,
            responsible_system=ResponsibleSystem.DATA_MART_ETL,
            trigger_reasons=["PROCESSING_LOGIC_IMPACT"],
            related_impact_codes=impact_codes,
        ))

    if _mentions_validation(text) or _is_cross_report(impact_codes):
        reasons = ["VALIDATION_RULE_IMPACT"]
        if _is_cross_report(impact_codes):
            reasons.append("CROSS_REPORT_CONSISTENCY")
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.VALIDATION_RULE,
            responsible_system=ResponsibleSystem.DATA_QUALITY_PLATFORM,
            trigger_reasons=reasons,
            related_impact_codes=impact_codes,
        ))

    if _mentions_retroactive(text):
        candidates.append(TicketTrigger(
            action_type=ActionTicketType.HISTORICAL_DATA,
            responsible_system=ResponsibleSystem.REG_REPORTING_SYSTEM,
            trigger_reasons=["RETROACTIVE_OR_FIRST_REPORTING"],
            related_impact_codes=impact_codes,
        ))

    candidates.append(TicketTrigger(
        action_type=ActionTicketType.TEST_ACCEPTANCE,
        responsible_system=ResponsibleSystem.TEST_ACCEPTANCE,
        trigger_reasons=["REGRESSION_ACCEPTANCE_REQUIRED"],
        related_impact_codes=impact_codes,
    ))
    candidates.append(TicketTrigger(
        action_type=ActionTicketType.ARCHIVE_REVIEW,
        responsible_system=ResponsibleSystem.KNOWLEDGE_ARCHIVE,
        trigger_reasons=["GOVERNANCE_ARCHIVE_REQUIRED"],
        related_impact_codes=impact_codes,
    ))

    return _deduplicate_triggers(candidates)


def _deduplicate_triggers(candidates: list[TicketTrigger]) -> list[TicketTrigger]:
    grouped: dict[tuple[ActionTicketType, ResponsibleSystem], TicketTrigger] = {}
    for trigger in candidates:
        key = (trigger.action_type, trigger.responsible_system)
        if key not in grouped:
            grouped[key] = trigger
            continue
        existing = grouped[key]
        grouped[key] = TicketTrigger(
            action_type=existing.action_type,
            responsible_system=existing.responsible_system,
            trigger_reasons=list(dict.fromkeys(existing.trigger_reasons + trigger.trigger_reasons)),
            related_impact_codes=list(dict.fromkeys(existing.related_impact_codes + trigger.related_impact_codes)),
        )
    return list(grouped.values())


def _mentions_processing(text: str) -> bool:
    return any(keyword in text for keyword in ("加工逻辑", "汇总", "调度", "ETL", "SQL", "内部数据加工"))


def _mentions_validation(text: str) -> bool:
    return any(keyword in text for keyword in ("校验", "勾稽", "一致性", "差异超过", "表内", "表间"))


def _mentions_retroactive(text: str) -> bool:
    return any(keyword in text for keyword in ("追溯", "补报", "重算", "首次按新口径报送", "历史数据"))


def _is_cross_report(impact_codes: list[str]) -> bool:
    object_codes = {code.split(".")[0] for code in impact_codes if "." in code}
    return len(object_codes) >= 2
