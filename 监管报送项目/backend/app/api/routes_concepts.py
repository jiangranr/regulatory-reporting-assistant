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
    ConceptMatchRequest,
    ConceptMatchResponse,
    ConceptRead,
    ReviewActionRequest,
)
from app.services.concept_matcher import get_concept_matcher


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
    """文本→概念匹配。多路召回 + 加权聚合，由 ConceptMatcher 统一执行。

    召回路径：
      路 1 alias substring（沿用长别名优先 + span 占用避重叠）
      路 2 definition substring（短/全定义 ≥4 字片段命中，弱信号）
      路 4 embedding 余弦相似度（远程 API，>=0.55 阈值）

    降级策略：
      - embedding API 未配置 / 向量库未建 / API 失败 → 自动退路 1+2
      - 业务方 schema 完全不变

    详见 docs/concept-and-ticket-reuse-design.md §3 补丁 A
    与 app/services/concept_matcher.py
    """
    matcher = get_concept_matcher(session)  # 根据 settings 自动决定 enable_embedding
    hits = matcher.match(
        text=request.text or "",
        scope=request.reporting_system_scope,
        top_k=request.top_k,
    )
    return ConceptMatchResponse(hits=hits)


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
