"""indicator_qa_tools.py

指标问答 Agent 的工具层。
每个工具是一个纯函数，接受参数+session，返回结构化 dict。
Agent 编排层（indicator_qa_agent.py）决定调用哪些工具。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.db_models import (
    DataFieldCatalog,
    DataSystemCatalog,
    RegReportingChangeCandidate,
    RegReportingItem,
    RegReportingObject,
    ReportingItemLineage,
    TicketDraft,
)
from app.services.embedding_indexer import search_instruction_chunks
from app.services.source_recommender import recommend_source


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def search_instruction_rag(
    query: str,
    object_codes: list[str] | None = None,
    top_k: int = 5,
    session: Session = None,  # type: ignore[assignment]
    keyword_hint: str = "",
) -> list[dict]:
    """三级级联检索填报说明切片。

    keyword_hint: 指标中文名（如"修正久期"），Level 1 精确匹配用。

    Returns:
        list of {chunk_text, source_label, reporting_object_code, field_tag, item_name, score, match_type}
    """
    return search_instruction_chunks(
        query=query,
        object_codes=object_codes,
        top_k=top_k,
        session=session,
        item_name_hint=keyword_hint,
    )


def get_item_lineage(item_code: str, session: Session) -> dict:
    """查询指标的血缘路径。

    Returns:
        {item_code, item_name, fields: [{field_code, field_name, table_name, system_name, lineage_role, mapping_status}]}
    """
    item = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code == item_code)
    ).first()
    if not item or not item.id:
        return {"item_code": item_code, "item_name": "", "fields": [], "found": False}

    lineages = session.exec(
        select(ReportingItemLineage).where(
            ReportingItemLineage.reporting_item_id == item.id,
            ReportingItemLineage.mapping_status.in_(["SEED_CONFIRMED", "CONFIRMED"]),
        )
    ).all()

    fields = []
    for lin in lineages:
        field = session.get(DataFieldCatalog, lin.data_field_id)
        if not field:
            continue
        sys = session.get(DataSystemCatalog, field.data_system_id)
        fields.append({
            "field_code": field.field_code,
            "field_name": field.field_name,
            "table_name": field.table_name,
            "system_name": sys.system_name if sys else "",
            "system_code": sys.system_code if sys else "",
            "lineage_role": lin.lineage_role,
            "mapping_status": lin.mapping_status,
            "business_meaning": field.business_meaning or "",
        })

    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "fields": fields,
        "found": True,
    }


def get_regulatory_changes(item_code: str, session: Session) -> list[dict]:
    """查询该指标的近期监管变更记录（来自 RegReportingChangeCandidate + TicketDraft）。

    Returns:
        list of {change_type, change_summary, created_at, ticket_id, ticket_title}
    """
    candidates = session.exec(
        select(RegReportingChangeCandidate).where(
            RegReportingChangeCandidate.reporting_item_code == item_code
        ).order_by(RegReportingChangeCandidate.created_at.desc())
    ).all()

    results = []
    for c in candidates[:5]:  # 只取最近 5 条
        ticket = None
        # 找关联工单（通过 task_id 和 reporting_item_code 推断）
        ticket_match = session.exec(
            select(TicketDraft).where(
                TicketDraft.task_id == c.task_id,
                TicketDraft.related_impact_codes.contains(item_code),
            )
        ).first()
        results.append({
            "change_type": c.change_type,
            "change_summary": c.change_summary or c.evidence_text or "",
            "before_after": c.before_after_snapshot or "{}",
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "ticket_id": ticket_match.id if ticket_match else None,
            "ticket_title": ticket_match.title if ticket_match else "",
        })
    return results


def get_related_tickets(item_code: str, session: Session) -> list[dict]:
    """查询历史工单中涉及该指标的已闭合记录。

    Returns:
        list of {ticket_id, title, status, action_ticket_type, summary}
    """
    tickets = session.exec(
        select(TicketDraft).where(
            TicketDraft.related_impact_codes.contains(item_code)
        ).order_by(TicketDraft.created_at.desc())
    ).all()

    return [
        {
            "ticket_id": t.id,
            "title": t.title,
            "status": t.status,
            "action_ticket_type": t.action_ticket_type,
            "summary": t.summary or "",
        }
        for t in tickets[:5]
    ]


def get_item_basic_info(item_code: str, session: Session) -> dict:
    """查询指标基本信息。

    Returns:
        {item_code, item_name, object_code, object_name, unit, frequency, found}
    """
    item = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code == item_code)
    ).first()
    if not item:
        return {"item_code": item_code, "found": False}

    obj = session.get(RegReportingObject, item.reporting_object_id)
    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "object_code": obj.object_code if obj else "",
        "object_name": obj.object_name if obj else "",
        "unit": item.unit if hasattr(item, "unit") else "万元",
        "found": True,
    }


def recommend_item_source(item_code: str, item_name: str, definition: str, session: Session) -> dict:
    """为新增指标推荐数据来源（供排查模式和问答 Agent 使用）。"""
    result = recommend_source(item_code, item_name, definition, session)
    return {
        "candidates": [
            {
                "field_code": c.field_code,
                "field_name": c.field_name,
                "system_name": c.system_name,
                "reasoning": c.reasoning,
            }
            for c in result.candidates
        ],
        "unresolved": result.unresolved,
    }
