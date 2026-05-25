"""报送规则卡片接口。

P0 仅暴露列表 + 详情读端口，写操作走种子或后续 P1 抽取流水线。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from datetime import datetime

from app.core.database import get_session
from app.models.db_models import (
    RegConcept,
    RegReportingRuleCard,
    RegReportingRuleCardConceptMap,
)
from app.models.schemas import ReviewActionRequest, RuleCardRead


router = APIRouter(prefix="/api/rule-cards", tags=["rule-cards"])


@router.get("", response_model=list[RuleCardRead])
def list_rule_cards(
    reporting_object_code: str | None = None,
    reporting_item_code: str | None = None,
    card_level: str | None = None,
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[RuleCardRead]:
    query = select(RegReportingRuleCard)
    if reporting_object_code:
        query = query.where(RegReportingRuleCard.reporting_object_code == reporting_object_code)
    if reporting_item_code:
        query = query.where(RegReportingRuleCard.reporting_item_code == reporting_item_code)
    if card_level:
        query = query.where(RegReportingRuleCard.card_level == card_level)
    if status:
        query = query.where(RegReportingRuleCard.status == status)
    else:
        query = query.where(RegReportingRuleCard.status != "ARCHIVED")
    query = query.order_by(RegReportingRuleCard.card_code)
    cards = list(session.exec(query).all())
    return _enrich_with_concepts(cards, session)


@router.get("/{card_id}", response_model=RuleCardRead)
def get_rule_card(card_id: int, session: Session = Depends(get_session)) -> RuleCardRead:
    card = session.get(RegReportingRuleCard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Rule card not found")
    enriched = _enrich_with_concepts([card], session)
    return enriched[0]


@router.patch("/{card_id}/review", response_model=RuleCardRead)
def review_rule_card(
    card_id: int,
    request: ReviewActionRequest,
    session: Session = Depends(get_session),
) -> RuleCardRead:
    """人工复核候选卡片。

    - ACCEPT: status=ACTIVE, review_status=CONFIRMED
    - REJECT: status=ARCHIVED, review_status=REJECTED
    - HOLD:   保留 DRAFT, review_status=PENDING (仅记录 reviewer/comment)
    """
    card = session.get(RegReportingRuleCard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Rule card not found")

    action = (request.action or "").upper()
    if action == "ACCEPT":
        card.status = "ACTIVE"
        card.review_status = "CONFIRMED"
    elif action == "REJECT":
        card.status = "ARCHIVED"
        card.review_status = "REJECTED"
    elif action == "HOLD":
        card.review_status = "PENDING"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    if request.reviewer:
        card.updated_by = request.reviewer
    card.updated_at = datetime.utcnow()
    session.add(card)
    session.commit()
    session.refresh(card)
    enriched = _enrich_with_concepts([card], session)
    return enriched[0]


def _enrich_with_concepts(
    cards: list[RegReportingRuleCard], session: Session
) -> list[RuleCardRead]:
    if not cards:
        return []
    card_ids = [c.id for c in cards if c.id is not None]
    rows = list(
        session.exec(
            select(RegReportingRuleCardConceptMap, RegConcept)
            .where(RegReportingRuleCardConceptMap.card_id.in_(card_ids))
            .where(RegConcept.id == RegReportingRuleCardConceptMap.concept_id)
        ).all()
    )
    codes_by_card: dict[int, list[str]] = {}
    for mapping, concept in rows:
        codes_by_card.setdefault(mapping.card_id, []).append(concept.concept_code)
    results: list[RuleCardRead] = []
    for card in cards:
        related = codes_by_card.get(card.id or 0, [])
        results.append(
            RuleCardRead.model_validate(
                {**card.model_dump(), "related_concept_codes": related}
            )
        )
    return results
