from pydantic import BaseModel

from app.services.ticket_card_builder import TicketTaskCard

_EXPECTED_AFFECTED_ASSET_KEYS = (
    "reporting_item_codes",
    "reporting_fields",
    "source_fields",
    "lineage_roles",
)


class TicketQualityResult(BaseModel):
    score: int
    flags: list[str]


def check_ticket_card_quality(card: TicketTaskCard) -> TicketQualityResult:
    score = 100
    flags: list[str] = []

    score = _deduct_if_missing(card.summary, score, flags, "MISSING_SUMMARY")
    score = _deduct_if_missing(
        _has_expected_affected_assets(card.affected_assets),
        score,
        flags,
        "MISSING_AFFECTED_ASSETS",
    )
    score = _deduct_if_missing(card.must_do, score, flags, "MISSING_MUST_DO")
    score = _deduct_if_missing(card.acceptance_criteria, score, flags, "MISSING_ACCEPTANCE_CRITERIA")
    score = _deduct_if_missing(card.output_artifacts, score, flags, "MISSING_OUTPUT_ARTIFACTS")
    score = _deduct_if_missing(card.evidence_refs, score, flags, "MISSING_EVIDENCE_REFS")
    score = _deduct_if_missing(card.responsible_system, score, flags, "MISSING_RESPONSIBLE_SYSTEM")

    if len(card.must_do) > 5:
        flags.append("MUST_DO_TOO_LONG")
        score -= 10

    return TicketQualityResult(score=max(score, 0), flags=flags)


def _deduct_if_missing(value, score: int, flags: list[str], flag: str) -> int:
    if value:
        return score
    flags.append(flag)
    return score - 15


def _has_expected_affected_assets(affected_assets: dict) -> bool:
    return any(affected_assets.get(key) for key in _EXPECTED_AFFECTED_ASSET_KEYS)
