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

from app.services.reporting_impact_analyzer import ReportingImpactDraft


def search_similar_decisions(
    impacts: list[ReportingImpactDraft],
    top_k: int = 3,
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
    _ = top_k  # reserved for future use
    cases: dict[str, list[dict]] = {}
    for impact in impacts:
        code = (impact.reporting_item_code or "").strip()
        if code:
            cases[code] = []
    return cases
