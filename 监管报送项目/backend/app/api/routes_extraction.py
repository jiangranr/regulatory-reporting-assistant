"""手动抽取流水线接口(P1 最简形态)。

详见 docs/rule-card-and-concept-kb-design.md 第 6 节。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.database import get_session
from app.models.schemas import ExtractionRequest, ExtractionResultRead
from app.services.extract_service import extract_from_document


router = APIRouter(prefix="/api/extraction-jobs", tags=["extraction"])


@router.post("/manual", response_model=ExtractionResultRead)
def trigger_manual_extraction(
    request: ExtractionRequest, session: Session = Depends(get_session)
) -> ExtractionResultRead:
    """从指定文档抽取候选规则卡片 + 候选概念。

    - 全部落 DRAFT,需人工 PATCH /api/rule-cards/{id}/review 决定是否生效
    - MOCK_AI=true 时走 mock(基于段落规则信号词),否则走真 LLM
    - 幂等:同 document_id + 同 card_title 已存在则跳过
    """
    try:
        result = extract_from_document(request.document_id, session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ExtractionResultRead(
        document_id=result.document_id,
        inferred_object_code=result.inferred_object_code,
        rule_cards_created=result.rule_cards_created,
        concepts_created=result.concepts_created,
        aliases_created=result.aliases_created,
        card_concept_links_created=result.card_concept_links_created,
        rule_cards_skipped=result.rule_cards_skipped,
        concepts_skipped=result.concepts_skipped,
        llm_used=result.llm_used,
        error_message=result.error_message,
    )
