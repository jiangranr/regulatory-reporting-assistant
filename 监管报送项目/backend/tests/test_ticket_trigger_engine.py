from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_trigger_engine import build_ticket_triggers


def impact(**overrides):
    data = {
        "reporting_item_code": "G31.PART_I.1_0.C_DURATION",
        "impact_type": "INDICATOR_SCOPE",
        "impacted_reporting_field": "rpt_g31.duration",
        "impacted_source_fields": ["risk.duration"],
        "impacted_lineage_roles": ["REPORT_FIELD", "SOURCE_FIELD"],
        "impact_reason": "修正久期发生INDICATOR_ADD，需要复核报送字段。",
        "recommended_action": "复核字段映射。",
        "confidence_level": "HIGH",
    }
    data.update(overrides)
    return ReportingImpactDraft(**data)


def test_data_mapping_trigger_for_report_and_source_fields():
    triggers = build_ticket_triggers([impact()], document_text="")

    assert any(
        trigger.action_type == ActionTicketType.DATA_MAPPING
        and trigger.responsible_system == ResponsibleSystem.DATA_GOVERNANCE_PLATFORM
        for trigger in triggers
    )


def test_source_system_trigger_when_source_fields_missing():
    triggers = build_ticket_triggers([
        impact(impacted_source_fields=[], impacted_lineage_roles=["REPORT_FIELD"])
    ], document_text="")

    assert any(
        trigger.action_type == ActionTicketType.SOURCE_SYSTEM_CHANGE
        and trigger.responsible_system == ResponsibleSystem.SOURCE_SYSTEM
        and "SOURCE_FIELD_GAP" in trigger.trigger_reasons
        for trigger in triggers
    )


def test_validation_trigger_for_cross_table_consistency_text():
    triggers = build_ticket_triggers(
        [impact(reporting_item_code="G24.MAIN.A"), impact(reporting_item_code="G31.PART_I.B")],
        document_text="G24 与 G31 金额关系保持一致，差异超过 5% 须解释。",
    )

    assert any(
        trigger.action_type == ActionTicketType.VALIDATION_RULE
        and trigger.responsible_system == ResponsibleSystem.DATA_QUALITY_PLATFORM
        and "CROSS_REPORT_CONSISTENCY" in trigger.trigger_reasons
        for trigger in triggers
    )


def test_validation_trigger_for_cross_table_consistency_text_with_single_report_code():
    triggers = build_ticket_triggers(
        [impact(reporting_item_code="G31.PART_I.B")],
        document_text="表间一致性校验，差异超过 5% 须解释。",
    )

    assert any(
        trigger.action_type == ActionTicketType.VALIDATION_RULE
        and trigger.responsible_system == ResponsibleSystem.DATA_QUALITY_PLATFORM
        and "CROSS_REPORT_CONSISTENCY" in trigger.trigger_reasons
        for trigger in triggers
    )


def test_related_impact_codes_are_deduplicated_for_every_trigger():
    triggers = build_ticket_triggers(
        [
            impact(reporting_item_code="G31.PART_I.B"),
            impact(reporting_item_code="G31.PART_I.B"),
        ],
        document_text="",
    )

    assert triggers
    assert all(trigger.related_impact_codes == ["G31.PART_I.B"] for trigger in triggers)


def test_whitespace_and_malformed_codes_do_not_create_cross_report_reason():
    triggers = build_ticket_triggers(
        [
            impact(reporting_item_code=" G31.PART"),
            impact(reporting_item_code="G31.PART"),
            impact(reporting_item_code=".BAD"),
        ],
        document_text="校验规则调整。",
    )

    validation_triggers = [
        trigger for trigger in triggers
        if trigger.action_type == ActionTicketType.VALIDATION_RULE
    ]

    assert validation_triggers
    assert all(
        "CROSS_REPORT_CONSISTENCY" not in trigger.trigger_reasons
        for trigger in validation_triggers
    )
