from app.models.enums import ActionTicketType, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_card_builder import build_ticket_card
from app.services.ticket_trigger_engine import TicketTrigger


def impact(**overrides):
    data = {
        "reporting_item_code": "G31.PART_I.1_0.C_DURATION",
        "reporting_item_name": "修正久期",
        "impact_type": "INDICATOR_SCOPE",
        "impacted_reporting_field": "rpt_g31.duration",
        "impacted_reporting_field_name": "G31 修正久期",
        "impacted_source_fields": ["risk.duration", "trade.duration"],
        "impacted_source_field_details": [
            {"code": "risk.duration", "name": "风险久期", "role": "SOURCE_FIELD"},
            {"code": "trade.duration", "name": "交易久期", "role": "SOURCE_FIELD"},
        ],
        "impacted_lineage_roles": ["REPORT_FIELD", "SOURCE_FIELD"],
        "impact_reason": "修正久期发生INDICATOR_ADD，需要复核报送字段。",
        "recommended_action": "复核字段映射。",
        "confidence_level": "HIGH",
    }
    data.update(overrides)
    return ReportingImpactDraft(**data)


def test_builds_data_mapping_card_from_trigger_and_impact():
    trigger = TicketTrigger(
        action_type=ActionTicketType.DATA_MAPPING,
        responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
        trigger_reasons=["REPORT_OR_SOURCE_FIELD_IMPACT"],
        related_impact_codes=["G31.PART_I.1_0.C_DURATION"],
    )

    card = build_ticket_card(
        trigger=trigger,
        impacts=[
            impact(),
            impact(
                reporting_item_code="G31.PART_I.9_9.IGNORED",
                impacted_reporting_field="rpt_g31.ignored",
                impacted_source_fields=["ignored.field"],
            ),
        ],
        historical_cases=[
            {"case_id": "CASE-1"},
            {"case_id": "CASE-2"},
            {"case_id": "CASE-3"},
            {"case_id": "CASE-4"},
        ],
    )

    assert card.summary == "确认受影响报送项的数据映射和血缘口径。"
    assert card.responsible_system == ResponsibleSystem.DATA_GOVERNANCE_PLATFORM
    assert card.affected_assets["reporting_items"] == [
        {"code": "G31.PART_I.1_0.C_DURATION", "name": "修正久期"}
    ]
    assert card.affected_assets["reporting_fields"] == [
        {"code": "rpt_g31.duration", "name": "G31 修正久期"}
    ]
    assert card.affected_assets["source_fields"] == [
        {"code": "risk.duration", "name": "风险久期", "role": "SOURCE_FIELD"},
        {"code": "trade.duration", "name": "交易久期", "role": "SOURCE_FIELD"},
    ]
    assert card.affected_assets["lineage_roles"] == ["REPORT_FIELD", "SOURCE_FIELD"]
    assert len(card.must_do) <= 5
    assert "形成可复用的数据映射记录" in card.output_artifacts
    assert card.historical_cases == [
        {"case_id": "CASE-1"},
        {"case_id": "CASE-2"},
        {"case_id": "CASE-3"},
    ]
