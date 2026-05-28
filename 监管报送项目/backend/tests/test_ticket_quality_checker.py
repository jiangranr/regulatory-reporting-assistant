from app.models.enums import ActionTicketType, ResponsibleRole, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_card_builder import TicketTaskCard, build_ticket_card
from app.services.ticket_quality_checker import check_ticket_card_quality
from app.services.ticket_trigger_engine import TicketTrigger


def test_quality_checker_flags_missing_required_card_sections():
    card = TicketTaskCard(
        action_type=ActionTicketType.DATA_MAPPING,
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
        summary="确认受影响报送项的数据映射和血缘口径。",
        affected_assets={},
        must_do=["核对字段映射。"],
        must_confirm=["确认源字段语义。"],
        output_artifacts=["形成可复用的数据映射记录"],
        acceptance_criteria=[],
        blockers=[],
        evidence_refs=[],
    )

    result = check_ticket_card_quality(card)

    assert result.score < 100
    assert "MISSING_AFFECTED_ASSETS" in result.flags
    assert "MISSING_ACCEPTANCE_CRITERIA" in result.flags
    assert "MISSING_EVIDENCE_REFS" in result.flags


def test_quality_checker_flags_builder_card_with_empty_asset_lists():
    trigger = TicketTrigger(
        action_type=ActionTicketType.DATA_MAPPING,
        responsible_system=ResponsibleSystem.DATA_GOVERNANCE_PLATFORM,
        trigger_reasons=["REPORT_OR_SOURCE_FIELD_IMPACT"],
        related_impact_codes=["G31.NON_MATCHING_CODE"],
    )
    card = build_ticket_card(
        trigger=trigger,
        impacts=[
            ReportingImpactDraft(
                reporting_item_code="G31.PART_I.1_0.C_DURATION",
                impact_type="INDICATOR_SCOPE",
                impacted_reporting_field="rpt_g31.duration",
                impacted_source_fields=["risk.duration"],
                impacted_lineage_roles=["REPORT_FIELD"],
                impact_reason="修正久期发生INDICATOR_ADD，需要复核报送字段。",
                recommended_action="复核字段映射。",
                confidence_level="HIGH",
            )
        ],
        historical_cases=[],
    )

    result = check_ticket_card_quality(card)

    assert card.affected_assets == {
        "reporting_items": [],
        "reporting_fields": [],
        "source_fields": [],
        "lineage_roles": [],
    }
    assert result.score < 100
    assert "MISSING_AFFECTED_ASSETS" in result.flags
