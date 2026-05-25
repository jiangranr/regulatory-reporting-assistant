"""监管报送概念知识库接口。

P0 提供:
- GET  /api/concepts          列表(filter: type/scope/keyword)
- GET  /api/concepts/{id}     详情(含 aliases + 关联报送项)
- POST /api/concepts/match    文本→命中概念,用于影响分析的概念辐射
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from datetime import datetime

from app.core.database import get_session
from app.models.db_models import (
    RegConcept,
    RegConceptAlias,
    RegConceptReportingItemMap,
)
from app.models.schemas import (
    ConceptMatchHit,
    ConceptMatchRequest,
    ConceptMatchResponse,
    ConceptRead,
    ReviewActionRequest,
)


router = APIRouter(prefix="/api/concepts", tags=["concepts"])


@router.get("", response_model=list[ConceptRead])
def list_concepts(
    concept_type: str | None = None,
    reporting_system_scope: str | None = None,
    keyword: str | None = None,
    status: str = "ACTIVE",
    session: Session = Depends(get_session),
) -> list[ConceptRead]:
    query = select(RegConcept).where(RegConcept.status == status)
    if concept_type:
        query = query.where(RegConcept.concept_type == concept_type)
    if reporting_system_scope:
        query = query.where(RegConcept.reporting_system_scope == reporting_system_scope)
    if keyword:
        like = f"%{keyword}%"
        query = query.where(
            (RegConcept.canonical_name.like(like))
            | (RegConcept.short_definition.like(like))
        )
    query = query.order_by(RegConcept.concept_code)
    concepts = list(session.exec(query).all())
    return _enrich(concepts, session)


@router.get("/{concept_id}", response_model=ConceptRead)
def get_concept(concept_id: int, session: Session = Depends(get_session)) -> ConceptRead:
    concept = session.get(RegConcept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return _enrich([concept], session)[0]


@router.patch("/{concept_id}/review", response_model=ConceptRead)
def review_concept(
    concept_id: int,
    request: ReviewActionRequest,
    session: Session = Depends(get_session),
) -> ConceptRead:
    """人工复核候选概念。

    - ACCEPT: status=ACTIVE (生效进概念库)
    - REJECT: status=DEPRECATED (软删除)
    - HOLD:   保留 DRAFT
    """
    concept = session.get(RegConcept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    action = (request.action or "").upper()
    if action == "ACCEPT":
        concept.status = "ACTIVE"
    elif action == "REJECT":
        concept.status = "DEPRECATED"
    elif action == "HOLD":
        concept.status = "DRAFT"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")

    if request.reviewer:
        concept.reviewed_by = request.reviewer
    concept.updated_at = datetime.utcnow()
    session.add(concept)
    session.commit()
    session.refresh(concept)
    return _enrich([concept], session)[0]


@router.post("/match", response_model=ConceptMatchResponse)
def match_concepts(
    request: ConceptMatchRequest, session: Session = Depends(get_session)
) -> ConceptMatchResponse:
    """从文本中匹配概念(基于 alias 的关键词匹配,P0 不做语义检索)。

    匹配规则:
    1. 取所有 ACTIVE 概念的 aliases
    2. 在 text 中 substring 搜索,记录命中位置
    3. 同一概念多次命中只保留首次
    4. 长别名优先(避免短词把长词盖住)
    """
    text = request.text or ""
    if not text:
        return ConceptMatchResponse(hits=[])

    concept_query = select(RegConcept).where(RegConcept.status == "ACTIVE")
    if request.reporting_system_scope:
        concept_query = concept_query.where(
            (RegConcept.reporting_system_scope == request.reporting_system_scope)
            | (RegConcept.reporting_system_scope == "CROSS")
        )
    concepts = list(session.exec(concept_query).all())
    concept_by_id = {c.id: c for c in concepts if c.id is not None}
    if not concept_by_id:
        return ConceptMatchResponse(hits=[])

    aliases = list(
        session.exec(
            select(RegConceptAlias).where(
                RegConceptAlias.concept_id.in_(concept_by_id.keys())
            )
        ).all()
    )
    # 长别名优先匹配(避免"同业融入"先匹掉而漏了"同业融入余额")
    aliases.sort(key=lambda a: len(a.alias_text), reverse=True)

    matched_concept_ids: dict[int, ConceptMatchHit] = {}
    consumed_spans: list[tuple[int, int]] = []  # 已匹配的 (start, end),避免别名重叠

    for alias in aliases:
        if alias.concept_id in matched_concept_ids:
            continue
        offset = text.find(alias.alias_text)
        if offset < 0:
            continue
        end = offset + len(alias.alias_text)
        # 若该范围已被更长别名占用,跳过
        if any(s <= offset < e or s < end <= e for s, e in consumed_spans):
            continue
        concept = concept_by_id.get(alias.concept_id)
        if concept is None:
            continue
        matched_concept_ids[alias.concept_id] = ConceptMatchHit(
            concept_code=concept.concept_code,
            canonical_name=concept.canonical_name,
            matched_alias=alias.alias_text,
            match_offset=offset,
            match_length=len(alias.alias_text),
        )
        consumed_spans.append((offset, end))

    hit_concept_ids = list(matched_concept_ids.keys())
    item_maps = list(
        session.exec(
            select(RegConceptReportingItemMap).where(
                RegConceptReportingItemMap.concept_id.in_(hit_concept_ids)
            )
        ).all()
    )
    items_by_concept: dict[int, list[str]] = {}
    for mapping in item_maps:
        items_by_concept.setdefault(mapping.concept_id, []).append(
            mapping.reporting_item_code
        )

    hits: list[ConceptMatchHit] = []
    for cid, hit in matched_concept_ids.items():
        hit.related_reporting_item_codes = items_by_concept.get(cid, [])
        hits.append(hit)

    # 按 match_offset 排序,top_k 截断
    hits.sort(key=lambda h: h.match_offset)
    return ConceptMatchResponse(hits=hits[: request.top_k])


def _enrich(concepts: list[RegConcept], session: Session) -> list[ConceptRead]:
    if not concepts:
        return []
    ids = [c.id for c in concepts if c.id is not None]
    alias_rows = list(
        session.exec(
            select(RegConceptAlias).where(RegConceptAlias.concept_id.in_(ids))
        ).all()
    )
    aliases_by_concept: dict[int, list[str]] = {}
    for row in alias_rows:
        aliases_by_concept.setdefault(row.concept_id, []).append(row.alias_text)

    item_rows = list(
        session.exec(
            select(RegConceptReportingItemMap).where(
                RegConceptReportingItemMap.concept_id.in_(ids)
            )
        ).all()
    )
    items_by_concept: dict[int, list[str]] = {}
    for row in item_rows:
        items_by_concept.setdefault(row.concept_id, []).append(row.reporting_item_code)

    results: list[ConceptRead] = []
    for concept in concepts:
        cid = concept.id or 0
        results.append(
            ConceptRead.model_validate(
                {
                    **concept.model_dump(),
                    "aliases": sorted(set(aliases_by_concept.get(cid, []))),
                    "related_reporting_item_codes": sorted(
                        set(items_by_concept.get(cid, []))
                    ),
                }
            )
        )
    return results
