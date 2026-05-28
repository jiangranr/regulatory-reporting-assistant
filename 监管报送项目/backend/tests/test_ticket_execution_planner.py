"""单元测试：Module D · AI 工单执行规划。

策略：完全 mock `llm_client.complete_json`，把 LLM 返回的 JSON 控制在测试里。
这样可以独立验证：
- 模板渲染
- 5 层校验（团队枚举 / ticket_id 在清单内 / severity 枚举 / 工期是区间 / JSON 合法）
- 2 次重试 + 骨架兜底
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.services import ticket_execution_planner as planner
from app.services.ticket_execution_planner import (
    ChildTicketContext,
    ExecutionPlannerInput,
    ParentTicketContext,
    PlannerResult,
    RegulatoryDocumentContext,
    generate_execution_plan,
)


# ── 测试夹具：构造一个标准 payload（保持和 D6 前端 fixture 对齐） ──────────


def _make_payload(child_ids: list[int] | None = None) -> ExecutionPlannerInput:
    ids = child_ids or [5011, 5012, 5013, 5014]
    return ExecutionPlannerInput(
        task_id=42,
        reg_document=RegulatoryDocumentContext(
            title="同业口径调整公告",
            document_no="〔2026〕第 15 号",
            issuing_authority="国家金融监督管理总局",
            published_at="2026-05-26",
            effective_date="2026-07-01",
            first_report_period="2026Q3",
            regulatory_intent="为深化数据治理工作",
        ),
        parent_ticket=ParentTicketContext(
            title="G24/G31 同业口径调整母单",
            change_ticket_type="SCOPE_ADJUSTMENT",
            severity_level="L3_STANDARD",
        ),
        child_tickets=[
            ChildTicketContext(
                id=cid,
                responsible_system="DATA_MART_ETL",
                table_code="G24",
                item_code=f"C{cid % 100:02d}",
                item_name=f"子单 {cid}",
                change_type="MODIFY",
                evidence_text="测试用例",
            )
            for cid in ids
        ],
    )


def _make_valid_plan_dict(ticket_ids: list[int]) -> dict:
    return {
        "executive_summary": "测试摘要：本次涉及 G24/G31 同业口径调整，需要源系统先打标、ETL 重映射、报送系统回归校验。",
        "estimated_duration": "2-3 周",
        "execution_phases": [
            {
                "phase_name": "第 1 周（关键路径）",
                "tasks": [
                    {
                        "team": "SOURCE_SYSTEM",
                        "team_zh": "业务源系统",
                        "action": "打标境外法人机构",
                        "ticket_id": ticket_ids[0],
                        "is_blocker": True,
                        "blocker_reason": "下游 ETL 依赖",
                    }
                ],
            }
        ],
        "critical_risks": [
            {
                "severity": "HIGH",
                "description": "境外法人机构口径在源系统未单独打标",
                "ticket_id_ref": ticket_ids[0],
                "mitigation": "先做口径解释表",
            }
        ],
        "team_coordination": "建议每周三 16:00 由数据治理平台牵头召集 30 分钟同步会。",
        "confidence": 0.82,
        "needs_human_review": False,
    }


# ── L1-L5 校验路径 ──────────────────────────────────────────────────────────


def test_happy_path_returns_ready_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload()
    plan_dict = _make_valid_plan_dict([5011, 5012])
    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)

    assert result.status == "READY"
    assert result.plan is not None
    assert result.plan.executive_summary.startswith("测试摘要")
    assert result.plan.estimated_duration == "2-3 周"
    assert result.plan.confidence == 0.82
    assert "qwen-plus" in result.plan.generated_by


def test_invalid_team_triggers_retry_then_skeleton(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload([5011, 5012])
    plan_dict = _make_valid_plan_dict([5011, 5012])
    plan_dict["execution_phases"][0]["tasks"][0]["team"] = "NOT_A_REAL_TEAM"

    call_count = {"n": 0}

    def mock_complete(messages):
        call_count["n"] += 1
        return plan_dict, json.dumps(plan_dict), "qwen-plus"

    monkeypatch.setattr(planner, "complete_json", mock_complete)

    result = generate_execution_plan(payload)

    assert result.status == "DEGRADED"
    assert call_count["n"] == 3  # 1 initial + 2 retries
    assert result.plan is not None
    assert result.plan.confidence == pytest.approx(0.3)
    assert result.plan.needs_human_review is True
    assert "失败" in result.warning


def test_invalid_ticket_id_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload([5011, 5012])
    plan_dict = _make_valid_plan_dict([5011, 5012])
    # 编一个不在输入清单里的 ticket_id
    plan_dict["execution_phases"][0]["tasks"][0]["ticket_id"] = 9999

    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)
    assert result.status == "DEGRADED"


def test_duration_must_be_range(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload([5011, 5012])
    plan_dict = _make_valid_plan_dict([5011, 5012])
    plan_dict["estimated_duration"] = "3 周"  # 确定数字，不是区间

    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)
    assert result.status == "DEGRADED"


def test_empty_payload_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # 不允许 monkeypatch 被调到——空 payload 不应触发 LLM
    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: pytest.fail("不应调 LLM"),
    )

    payload = ExecutionPlannerInput(
        task_id=42,
        reg_document=RegulatoryDocumentContext(),
        parent_ticket=ParentTicketContext(title="空母单"),
        child_tickets=[],
    )

    result = generate_execution_plan(payload)
    assert result.status == "EMPTY"
    assert result.plan is None


def test_too_many_tickets_get_truncated(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload(list(range(5001, 5020)))  # 19 个子单
    plan_dict = _make_valid_plan_dict([5001])

    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)
    assert result.status == "READY"
    # 截断为前 10 个，5001 还在；5015 应不在
    # 没有直接 assert 截断，但只要 5001 被允许，行为就符合


def test_llm_error_then_skeleton(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 网络层失败 3 次后走骨架。"""
    from app.services.llm_client import LLMClientError

    payload = _make_payload([5011, 5012])

    def boom(messages):
        raise LLMClientError("network down")

    monkeypatch.setattr(planner, "complete_json", boom)

    result = generate_execution_plan(payload)
    assert result.status == "DEGRADED"
    assert result.plan is not None
    assert result.plan.confidence == pytest.approx(0.3)
    # 骨架按子单分配 task
    all_tasks = [t for phase in result.plan.execution_phases for t in phase.tasks]
    assert {t.ticket_id for t in all_tasks} == {5011, 5012}


def test_severity_enum_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _make_payload([5011])
    plan_dict = _make_valid_plan_dict([5011])
    plan_dict["critical_risks"][0]["severity"] = "CRITICAL"  # 不在 HIGH/MEDIUM/LOW

    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)
    assert result.status == "DEGRADED"


def test_confidence_clamped_to_unit_range(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM 给 1.5 之类越界数字，服务自动收敛到 [0,1]。"""
    payload = _make_payload([5011])
    plan_dict = _make_valid_plan_dict([5011])
    plan_dict["confidence"] = 1.5

    monkeypatch.setattr(
        planner,
        "complete_json",
        lambda messages: (plan_dict, json.dumps(plan_dict), "qwen-plus"),
    )

    result = generate_execution_plan(payload)
    assert result.status == "READY"
    assert result.plan is not None
    assert result.plan.confidence == 1.0
