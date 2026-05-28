"""Module D · AI 工单执行规划。

把"母单 + N 个子单 + 监管元数据 + 命中概念 + 历史相似工单"喂给 LLM，
让它输出结构化的"分阶段执行规划 + 风险点 + 团队协作建议"。

设计要点（见 docs/kg-and-agent-enhancement-design.md §4）：
- 提示词模板：app/prompts/execution_planner_v1.md（jinja2，分 SYSTEM/USER）
- 严格 schema：ExecutionPlan Pydantic 模型 + 5 层校验
- 防幻觉：team 枚举 / ticket_id 必须存在 / severity 枚举 / JSON 合法 / 工期是区间
- 失败兜底：2 次重试后降级为"骨架规划"（confidence ≤ 0.4 + needs_human_review）

调用方：app/api/routes_tasks.py 的 3 个 endpoint。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models.enums import ResponsibleSystem
from app.services.llm_client import LLMClientError, complete_json

logger = logging.getLogger(__name__)

# ── 提示词版本与模板路径 ────────────────────────────────────────────────────

PROMPT_VERSION = "planner_v1"
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "execution_planner_v1.md"

# ── 常量 ────────────────────────────────────────────────────────────────────

_VALID_TEAMS = {member.value for member in ResponsibleSystem}
_VALID_SEVERITIES = {"HIGH", "MEDIUM", "LOW"}
_TEAM_ZH_DEFAULT = {
    "REG_REPORTING_SYSTEM": "报送系统",
    "DATA_GOVERNANCE_PLATFORM": "数据治理平台",
    "DATA_MART_ETL": "数据集市 / ETL",
    "SOURCE_SYSTEM": "业务源系统",
    "DATA_QUALITY_PLATFORM": "数据质量平台",
    "TEST_ACCEPTANCE": "测试验收",
    "KNOWLEDGE_ARCHIVE": "知识沉淀",
}

MAX_RETRIES = 2
MIN_CHILD_TICKETS_FOR_LLM = 1
MAX_CHILD_TICKETS_FED_TO_LLM = 10


# ── 输入数据类 ──────────────────────────────────────────────────────────────


@dataclass
class RegulatoryDocumentContext:
    title: str = ""
    document_no: str = ""
    issuing_authority: str = ""
    published_at: str = ""
    effective_date: str = ""
    first_report_period: str = ""
    regulatory_intent: str = ""


@dataclass
class ParentTicketContext:
    title: str = ""
    change_ticket_type: str = ""
    severity_level: str = ""


@dataclass
class ChildTicketContext:
    id: int
    responsible_system: str = ""
    table_code: str = ""
    item_code: str = ""
    item_name: str = ""
    change_type: str = ""
    evidence_text: str = ""
    blockers: str = ""
    quality_issues: str = ""


@dataclass
class ConceptHitContext:
    concept_name: str
    paths: list[str] = field(default_factory=list)


@dataclass
class HistoricalCaseContext:
    title: str
    summary: str
    duration: str = ""


@dataclass
class ExecutionPlannerInput:
    task_id: int
    reg_document: RegulatoryDocumentContext
    parent_ticket: ParentTicketContext
    child_tickets: list[ChildTicketContext]
    concept_hits: list[ConceptHitContext] = field(default_factory=list)
    historical_cases: list[HistoricalCaseContext] = field(default_factory=list)


# ── 输出 Pydantic 模型（与前端 API 契约严格对齐） ───────────────────────────


class ExecutionTask(BaseModel):
    team: str
    team_zh: str
    action: str
    ticket_id: int
    is_blocker: bool = False
    blocker_reason: str = ""

    @field_validator("team")
    @classmethod
    def validate_team(cls, v: str) -> str:
        if v not in _VALID_TEAMS:
            raise ValueError(f"team 必须是 7 个枚举之一，收到 {v!r}")
        return v


class ExecutionPhase(BaseModel):
    phase_name: str
    tasks: list[ExecutionTask] = Field(default_factory=list)


class CriticalRisk(BaseModel):
    severity: str
    description: str
    ticket_id_ref: int | None = None
    mitigation: str = ""

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity 必须是 HIGH/MEDIUM/LOW，收到 {v!r}")
        return v


class ExecutionPlan(BaseModel):
    """与 GET /api/tasks/{task_id}/execution-plan 的 plan 字段同形。"""

    executive_summary: str
    estimated_duration: str
    execution_phases: list[ExecutionPhase] = Field(default_factory=list)
    critical_risks: list[CriticalRisk] = Field(default_factory=list)
    team_coordination: str = ""
    confidence: float = 0.0
    needs_human_review: bool = False
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = ""


@dataclass
class PlannerResult:
    """规划生成结果（服务层返回，路由层包成 HTTP 响应）。"""

    status: str          # "READY" / "DEGRADED" / "EMPTY"
    plan: ExecutionPlan | None
    warning: str = ""
    raw_response: str = ""


# ── 主入口 ──────────────────────────────────────────────────────────────────


def generate_execution_plan(payload: ExecutionPlannerInput) -> PlannerResult:
    """生成执行规划。失败 2 次重试后降级到骨架规划。

    返回的 PlannerResult 不直接落库——由路由层根据 status 决定是否持久化。
    """

    if len(payload.child_tickets) < MIN_CHILD_TICKETS_FOR_LLM:
        return PlannerResult(
            status="EMPTY",
            plan=None,
            warning="无影响子单，无需规划",
        )

    if len(payload.child_tickets) > MAX_CHILD_TICKETS_FED_TO_LLM:
        logger.warning(
            "child_tickets count %d exceeds cap %d, truncating to first %d",
            len(payload.child_tickets),
            MAX_CHILD_TICKETS_FED_TO_LLM,
            MAX_CHILD_TICKETS_FED_TO_LLM,
        )
        payload = _truncate_payload(payload)

    system_prompt, user_prompt = _render_prompt(payload)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    valid_ticket_ids = {child.id for child in payload.child_tickets}
    last_error: str = ""
    last_raw: str = ""

    for attempt in range(1, MAX_RETRIES + 2):  # 初次 + 2 次重试 = 3 次机会
        try:
            data, raw, model_used = complete_json(messages)
            last_raw = raw
            plan = _validate_and_build_plan(data, valid_ticket_ids, model_used)
        except (LLMClientError, ValidationError, ValueError) as exc:
            last_error = f"attempt {attempt}: {exc}"
            logger.warning("ExecutionPlanner attempt %d failed: %s", attempt, exc)
            continue
        return PlannerResult(status="READY", plan=plan, raw_response=raw)

    # 所有重试都失败 → 降级
    logger.error("ExecutionPlanner all retries failed: %s", last_error)
    return PlannerResult(
        status="DEGRADED",
        plan=_build_skeleton_plan(payload, last_error),
        warning=f"LLM 调用 {MAX_RETRIES + 1} 次失败，已返回骨架规划，请人工补充",
        raw_response=last_raw,
    )


# ── 内部辅助 ────────────────────────────────────────────────────────────────


def _truncate_payload(payload: ExecutionPlannerInput) -> ExecutionPlannerInput:
    return ExecutionPlannerInput(
        task_id=payload.task_id,
        reg_document=payload.reg_document,
        parent_ticket=payload.parent_ticket,
        child_tickets=payload.child_tickets[:MAX_CHILD_TICKETS_FED_TO_LLM],
        concept_hits=payload.concept_hits,
        historical_cases=payload.historical_cases,
    )


def _render_prompt(payload: ExecutionPlannerInput) -> tuple[str, str]:
    """读取模板，渲染，按 ===SYSTEM=== / ===USER=== 分隔。"""
    raw = _PROMPT_PATH.read_text(encoding="utf-8")
    rendered = Template(raw).render(
        reg_document=payload.reg_document,
        parent_ticket=payload.parent_ticket,
        child_tickets=payload.child_tickets,
        concept_hits=payload.concept_hits,
        historical_cases=payload.historical_cases,
    )

    parts = rendered.split("===SYSTEM===", 1)
    if len(parts) != 2:
        raise RuntimeError("prompt template 缺少 ===SYSTEM=== 分隔符")
    after_system = parts[1]
    sub = after_system.split("===USER===", 1)
    if len(sub) != 2:
        raise RuntimeError("prompt template 缺少 ===USER=== 分隔符")
    return sub[0].strip(), sub[1].strip()


def _validate_and_build_plan(
    data: dict[str, Any],
    valid_ticket_ids: set[int],
    model_used: str,
) -> ExecutionPlan:
    """5 层校验：

    L1 JSON 合法（complete_json 已保障）
    L2 Pydantic schema
    L3 team 枚举（field_validator 已查）
    L4 ticket_id 在输入清单内
    L5 severity 枚举（field_validator 已查）+ 工期是区间
    """

    # L2 + L3 + L5（部分）
    plan = ExecutionPlan(**data)

    # L4: 所有 task.ticket_id 必须在输入清单
    for phase in plan.execution_phases:
        for task in phase.tasks:
            if task.ticket_id not in valid_ticket_ids:
                raise ValueError(
                    f"ticket_id={task.ticket_id} 不在输入清单 {sorted(valid_ticket_ids)}"
                )
    # risk 的 ticket_id_ref 也要校验（可空）
    for risk in plan.critical_risks:
        if risk.ticket_id_ref is not None and risk.ticket_id_ref not in valid_ticket_ids:
            raise ValueError(
                f"risk.ticket_id_ref={risk.ticket_id_ref} 不在输入清单"
            )

    # L5: 工期必须含区间符号（"-" 或 "—" 或 "至"）
    duration = plan.estimated_duration.strip()
    if not any(sep in duration for sep in ("-", "—", "至", "~", "～")):
        raise ValueError(f"estimated_duration 必须给区间，收到 {duration!r}")

    # confidence 必须在 [0, 1]
    plan.confidence = max(0.0, min(1.0, plan.confidence))

    # 标注模型版本
    plan.generated_by = f"{PROMPT_VERSION}@{model_used}"
    plan.generated_at = datetime.utcnow()

    return plan


def _build_skeleton_plan(payload: ExecutionPlannerInput, error_hint: str) -> ExecutionPlan:
    """LLM 全失败时的兜底：按子单的 responsible_system 简单分组成 1 个阶段。

    给一个看得过去的骨架，confidence=0.3，标记 needs_human_review。
    """
    tasks: list[ExecutionTask] = []
    for child in payload.child_tickets:
        team = child.responsible_system if child.responsible_system in _VALID_TEAMS else "DATA_GOVERNANCE_PLATFORM"
        tasks.append(
            ExecutionTask(
                team=team,
                team_zh=_TEAM_ZH_DEFAULT.get(team, "数据治理平台"),
                action=f"复核 {child.table_code}{('.' + child.item_code) if child.item_code else ''} 变更并落实改造",
                ticket_id=child.id,
                is_blocker=bool(child.blockers and child.blockers != "无"),
                blocker_reason=child.blockers if child.blockers and child.blockers != "无" else "",
            )
        )

    return ExecutionPlan(
        executive_summary="自动生成的骨架规划：LLM 调用失败，已按责任系统归并子单作为兜底，请人工审核并细化阶段与风险点。",
        estimated_duration="2-4 周",
        execution_phases=[
            ExecutionPhase(phase_name="第 1-2 周（待人工细化）", tasks=tasks),
        ],
        critical_risks=[],
        team_coordination="LLM 不可用，建议召集相关责任系统线下对齐工期与依赖关系。",
        confidence=0.3,
        needs_human_review=True,
        generated_by=f"{PROMPT_VERSION}@skeleton",
        generated_at=datetime.utcnow(),
    )
