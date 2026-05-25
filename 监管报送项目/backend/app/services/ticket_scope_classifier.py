from pydantic import BaseModel, Field


SCOPE_RANGE_ADJUSTMENT = "SCOPE_RANGE_ADJUSTMENT"

SCOPE_CONFIRMATION = "SCOPE_CONFIRMATION"
REPORTING_PROCESSING = "REPORTING_PROCESSING"
TEST_ACCEPTANCE = "TEST_ACCEPTANCE"
ARCHIVE_REVIEW = "ARCHIVE_REVIEW"
DATA_MAPPING = "DATA_MAPPING"
SOURCE_SYSTEM_CHANGE = "SOURCE_SYSTEM_CHANGE"
VALIDATION_RULE = "VALIDATION_RULE"
HISTORICAL_DATA_PROCESSING = "HISTORICAL_DATA_PROCESSING"


class TicketScopeDecision(BaseModel):
    ticket_parent_type: str = SCOPE_RANGE_ADJUSTMENT
    required_sub_ticket_types: list[str] = Field(default_factory=list)
    conditional_sub_ticket_types: list[str] = Field(default_factory=list)
    sub_ticket_triggers: dict[str, str] = Field(default_factory=dict)


def classify_scope_range_tickets(
    change_type: str,
    lineage_roles: list[str],
    source_fields: list[str],
    evidence_text: str = "",
) -> TicketScopeDecision:
    required = [
        SCOPE_CONFIRMATION,
        REPORTING_PROCESSING,
        TEST_ACCEPTANCE,
        ARCHIVE_REVIEW,
    ]
    conditional: list[str] = []
    triggers: dict[str, str] = {}
    roles = set(lineage_roles)

    if roles & {"DIMENSION_FIELD", "FILTER_FIELD"}:
        conditional.append(DATA_MAPPING)
        triggers[DATA_MAPPING] = "NEW_DIMENSION_OR_FILTER_FIELD"

    if not source_fields:
        conditional.append(SOURCE_SYSTEM_CHANGE)
        triggers[SOURCE_SYSTEM_CHANGE] = "SOURCE_FIELD_GAP"

    if _mentions_validation(evidence_text):
        conditional.append(VALIDATION_RULE)
        triggers[VALIDATION_RULE] = "VALIDATION_RULE_IMPACT"

    if _mentions_retroactive(evidence_text):
        conditional.append(HISTORICAL_DATA_PROCESSING)
        triggers[HISTORICAL_DATA_PROCESSING] = "RETROACTIVE_RECALCULATION_OR_DIFFERENCE_EXPLANATION"

    return TicketScopeDecision(
        ticket_parent_type=SCOPE_RANGE_ADJUSTMENT,
        required_sub_ticket_types=required,
        conditional_sub_ticket_types=conditional,
        sub_ticket_triggers=triggers,
    )


def _mentions_validation(text: str) -> bool:
    return any(keyword in text for keyword in ("校验", "勾稽", "表内", "表间", "一致性"))


def _mentions_retroactive(text: str) -> bool:
    return any(keyword in text for keyword in ("追溯", "重算", "差异说明", "补报", "更正"))
