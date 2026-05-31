"""routes_indicator_qa.py

指标问答 Agent API 端点。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.db_models import RegReportingItem, RegReportingObject
from app.services.indicator_qa_agent import (
    QARequest,
    QAResponse,
    run_indicator_qa,
    run_indicator_qa_stream,
)

router = APIRouter(prefix="/api/indicator-qa", tags=["indicator-qa"])


@router.post("/ask")
def ask_indicator(
    question: str,
    item_code: str | None = None,
    anomaly_value: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    """指标问答入口。

    - question: 自然语言问题，如"G31 修正久期怎么计算"或"修正久期这期取值异常"
    - item_code: 已知指标编码（可选，Agent 会从 question 中自动提取）
    - anomaly_value: 异常数值描述（可选，如"从 3.2 变成 5.8"）
    """
    req = QARequest(
        question=question,
        item_code=item_code,
        anomaly_value=anomaly_value,
    )
    resp = run_indicator_qa(req, session)
    return _serialize_response(resp)


@router.post("/ask/stream")
def ask_indicator_stream(
    question: str,
    item_code: str | None = None,
    anomaly_value: str | None = None,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """流式指标问答。返回 text/event-stream，事件格式见 run_indicator_qa_stream。"""
    req = QARequest(question=question, item_code=item_code, anomaly_value=anomaly_value)
    return StreamingResponse(
        run_indicator_qa_stream(req, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 禁止 nginx 缓冲
        },
    )


@router.get("/items")
def list_queryable_items(
    object_code: str | None = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    """返回可查询的指标列表（用于前端下拉选择）。"""
    stmt = select(RegReportingItem)
    if object_code:
        obj = session.exec(
            select(RegReportingObject).where(RegReportingObject.object_code == object_code)
        ).first()
        if obj and obj.id:
            stmt = stmt.where(RegReportingItem.reporting_object_id == obj.id)

    items = session.exec(stmt.order_by(RegReportingItem.item_code)).all()
    return [
        {"item_code": i.item_code, "item_name": i.item_name}
        for i in items
        if i.item_code and i.item_name
    ]


def _serialize_response(resp: QAResponse) -> dict:
    return {
        "mode": resp.mode,
        "item_code": resp.item_code,
        "item_name": resp.item_name,
        # 解释模式：把 chunk_text 统一改名为 text，并透传 match_type / item_name / field_tag
        "instruction_excerpts": [
            {
                "text": ex.get("chunk_text", ex.get("text", "")),
                "source_label": ex.get("source_label", ""),
                "item_name": ex.get("item_name", ""),
                "field_tag": ex.get("field_tag", ""),
                "match_type": ex.get("match_type", "semantic"),
                "score": ex.get("score"),
            }
            for ex in (resp.instruction_excerpts or [])
        ],
        "plain_explanation": resp.plain_explanation,
        "key_points": resp.key_points,
        # 排查模式
        "hypotheses": [
            {
                "label": h.label,
                "status": h.status,
                "evidence": h.evidence,
                "action": h.action,
            }
            for h in resp.hypotheses
        ],
        # 通用
        "lineage_fields": resp.lineage_fields,
        "related_tickets": resp.related_tickets,
        "error": resp.error,
    }
