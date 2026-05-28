"""历史相似决策档案 service。

设计依据：docs/concept-and-ticket-reuse-design.md §3 补丁 B
        + docs/superpowers/specs/2026-05-27-ticket-governance-workbench-design.md

本期（Task 4）只提供一个稳定 stub：
- 接口签名固定：search_similar_decisions(impacts, top_k) -> dict[reporting_item_code → list[case]]
- 返回 key 覆盖入参 impacts 但 value 全为空 list
- 这样 generator 编排器和 routes_tasks 可以无条件调用，不阻塞上线

W2 阶段会把真实查询接进来：
- 反查 audit_logs（action=TICKET_CLOSED，detail 含 hit_concept_codes）
- join ticket_drafts + impact_items
- 按"概念交集 + 时间衰减 + 严重等级"评分取 top_k

详细查询设计见 concept-and-ticket-reuse-design.md。
"""

from __future__ import annotations

import json

from sqlmodel import Session, select

from app.models.db_models import RegTask, TicketDraft
from app.services.reporting_impact_analyzer import ReportingImpactDraft


def search_similar_decisions(
    impacts: list[ReportingImpactDraft],
    top_k: int = 3,
    session: Session | None = None,
    exclude_task_id: int | None = None,
) -> dict[str, list[dict]]:
    """返回 {reporting_item_code: [历史决策案例, ...]}。

    本期为稳定 stub —— key 来自 impacts，value 全为空 list。
    保持接口稳定，让生成器和路由可以无条件调用。

    后续 W2 真做时，案例 dict 字段建议：
      - ticket_id / task_title / decided_at
      - decision_type / decision_rationale
      - field_adjustments / hit_concept_codes / hit_rule_card_codes
      - reuse_score
    """
    cases: dict[str, list[dict]] = {}
    for impact in impacts:
        code = (impact.reporting_item_code or "").strip()
        if code:
            cases[code] = []
    if session is None or not cases:
        return cases

    tickets = session.exec(
        select(TicketDraft).where(TicketDraft.ticket_role == "CHILD")
    ).all()
    task_ids = {ticket.task_id for ticket in tickets if ticket.task_id != exclude_task_id}
    tasks = session.exec(select(RegTask).where(RegTask.id.in_(task_ids))).all() if task_ids else []
    task_title_by_id = {task.id: task.title for task in tasks if task.id is not None}

    for item_code in cases:
        item_cases: list[dict] = []
        for ticket in tickets:
            if ticket.task_id == exclude_task_id:
                continue
            related_codes = _json_list(ticket.related_impact_codes)
            if item_code not in related_codes:
                continue
            matched_codes = [code for code in related_codes if code == item_code]
            item_cases.append({
                "id": f"TK-{ticket.id}" if ticket.id else f"TASK-{ticket.task_id}",
                "ticket_id": ticket.id,
                "task_title": task_title_by_id.get(ticket.task_id, ""),
                "title": ticket.title,
                "decided_at": ticket.created_at.date().isoformat() if ticket.created_at else "",
                "decision_type": ticket.action_ticket_type or "TICKET_REUSE",
                "decision_rationale": ticket.summary or _first_content_line(ticket.content),
                "matched_item_codes": matched_codes,
                "reuse_score": 92 if ticket.status == "DRAFT" else 96,
            })
            if len(item_cases) >= top_k:
                break
        cases[item_code] = item_cases
    return cases


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _first_content_line(value: str) -> str:
    for line in (value or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if text:
            return text
    return ""
