from app.models.enums import ActionTicketType, ResponsibleRole, ResponsibleSystem
from app.services.ticket_card_builder import TicketTaskCard
from app.services.ticket_quality_checker import check_ticket_card_quality


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
