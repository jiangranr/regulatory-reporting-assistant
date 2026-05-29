"""Reference SQL Generator · 参考 SQL 生成。

把"监管口径 + 业务勾选字段 schema + 业务备注"喂给 LLM，生成带注释的参考 SQL。

设计要点（见 docs/superpowers/plans/2026-05-29-reference-sql-generator.md）：
- 可生成性闸门 assess_sql_ability：先判 4 档（CAN_GENERATE / PARTIAL /
  VALIDATION_ONLY / NOT_APPLICABLE），NOT_APPLICABLE 直接返回不调 LLM
- 提示词模板：app/prompts/system_ticket_sql_v1.md（取数 / 对账两分支）
- 5 层校验：JSON / schema / sqlglot 语法 / 表在清单 / 列在清单
- 失败兜底：3 次重试后返回骨架 SQL（confidence ≤ 0.2）

调用方：app/api/routes_tasks.py 的参考 SQL 端点。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import sqlglot
from jinja2 import Template
from pydantic import BaseModel, Field, ValidationError
from sqlglot import expressions as exp

from app.models.enums import ActionTicketType
from app.services.llm_client import LLMClientError, complete_json

logger = logging.getLogger(__name__)

PROMPT_VERSION = "sql_v1"
_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_ticket_sql_v1.md"

MAX_RETRIES = 2  # 初次 + 2 次重试 = 3 次机会

# 约定俗成的技术列（时间分区 / 占位符），不算业务字段，不参与"编造字段"校验
_CONVENTIONAL_COLUMNS = {"data_dt", "report_date", "etl_dt", "biz_date", "dt", "pt", "ds"}

# ── 可生成性闸门 ────────────────────────────────────────────────────────────

# 非数据加工类动作：这些子单不碰数据，不该生成 SQL
NON_DATA_ACTIONS = {
    ActionTicketType.SCOPE_CONFIRM,
    ActionTicketType.TASK_INIT,
    ActionTicketType.TEST_ACCEPTANCE,
    ActionTicketType.ARCHIVE_REVIEW,
    ActionTicketType.CATALOG_INIT,
}

# 取数类动作：生成 SELECT
QUERY_ACTIONS = {
    ActionTicketType.DATA_MAPPING,
    ActionTicketType.REPORT_PROCESSING,
    ActionTicketType.LINEAGE_BUILD,
    ActionTicketType.HISTORICAL_DATA,
    ActionTicketType.MERGED_LIGHTWEIGHT,
}

ABILITY_CAN_GENERATE = "CAN_GENERATE"
ABILITY_PARTIAL = "PARTIAL"
ABILITY_VALIDATION_ONLY = "VALIDATION_ONLY"
ABILITY_NOT_APPLICABLE = "NOT_APPLICABLE"

_NOT_APPLICABLE_REASONS = {
    "NON_DATA_ACTION": "这是{action}类任务，属于业务口径判断或流程动作，不涉及数据加工。"
                       "请业务方先确认口径后，由数据加工类子单生成取数 SQL。",
    "SOURCE_GAP": "监管要求的字段在源系统中尚无对应来源。请先完成本工单（源系统改造），"
                  "字段就绪后再由下游加工单生成 SQL。",
    "NO_FIELDS": "本工单未关联到任何可用源字段，无法生成 SQL。请先在影响范围里勾选相关字段。",
}


def assess_sql_ability(
    action_type: ActionTicketType | str,
    has_source_fields: bool,
    has_transform_expression: bool,
) -> tuple[str, str]:
    """判定 SQL 可生成性。返回 (ability, not_applicable_reason)。

    not_applicable_reason 仅在 NOT_APPLICABLE 时非空。
    """
    try:
        action = ActionTicketType(action_type) if isinstance(action_type, str) else action_type
    except ValueError:
        action = None

    if action in NON_DATA_ACTIONS:
        label = _action_label(action)
        return ABILITY_NOT_APPLICABLE, _NOT_APPLICABLE_REASONS["NON_DATA_ACTION"].format(action=label)

    if action == ActionTicketType.SOURCE_SYSTEM_CHANGE and not has_source_fields:
        return ABILITY_NOT_APPLICABLE, _NOT_APPLICABLE_REASONS["SOURCE_GAP"]

    if action == ActionTicketType.VALIDATION_RULE:
        return ABILITY_VALIDATION_ONLY, ""

    if not has_source_fields:
        return ABILITY_NOT_APPLICABLE, _NOT_APPLICABLE_REASONS["NO_FIELDS"]

    if has_transform_expression:
        return ABILITY_CAN_GENERATE, ""
    return ABILITY_PARTIAL, ""


def _action_label(action: ActionTicketType | None) -> str:
    labels = {
        ActionTicketType.SCOPE_CONFIRM: "「影响范围确认」",
        ActionTicketType.TASK_INIT: "「报送任务配置」",
        ActionTicketType.TEST_ACCEPTANCE: "「测试验收」",
        ActionTicketType.ARCHIVE_REVIEW: "「知识沉淀」",
        ActionTicketType.CATALOG_INIT: "「目录初始化」",
    }
    return labels.get(action, "该")


# ── 输入数据类 ──────────────────────────────────────────────────────────────


@dataclass
class FieldContext:
    code: str
    table_name: str = ""
    column_name: str = ""
    data_type: str = ""
    business_meaning: str = ""
    lineage_role: str = ""
    transform_expression: str = ""


@dataclass
class ReportingItemContext:
    code: str
    name: str = ""
    definition: str = ""
    evidence_text: str = ""


@dataclass
class RegDocumentContext:
    document_no: str = ""
    effective_date: str = ""
    first_report_period: str = ""
    regulatory_intent: str = ""


@dataclass
class SqlGenerationInput:
    ticket_title: str
    action_type: str
    reporting_items: list[ReportingItemContext]
    available_fields: list[FieldContext]
    reg_document: RegDocumentContext
    business_note: str = ""


# ── 输出 ────────────────────────────────────────────────────────────────────


@dataclass
class SqlWarning:
    type: str        # FIELD_NOT_IN_SCOPE / TABLE_NOT_IN_CATALOG / SYNTAX_ERROR
    message: str
    field_code: str = ""
    severity: str = "WARNING"   # ERROR / WARNING / INFO

    def to_dict(self) -> dict[str, str]:
        return {
            "type": self.type,
            "message": self.message,
            "field_code": self.field_code,
            "severity": self.severity,
        }


class _LlmSqlPayload(BaseModel):
    """LLM 返回 JSON 的 schema。"""

    sql: str
    explanation: str = ""
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = 0.0


@dataclass
class SqlGenerationResult:
    status: str          # READY / DEGRADED / NOT_APPLICABLE
    ability: str
    sql: str = ""
    dialect: str = "ANSI"
    explanation: str = ""
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    warnings: list[SqlWarning] = field(default_factory=list)
    not_applicable_reason: str = ""
    generated_by: str = ""


# ── 主入口 ──────────────────────────────────────────────────────────────────


def generate_reference_sql(payload: SqlGenerationInput) -> SqlGenerationResult:
    """生成参考 SQL。先过可生成性闸门，再调 LLM + 5 层校验 + 兜底。"""

    has_source_fields = bool(payload.available_fields)
    has_transform = any(f.transform_expression for f in payload.available_fields)
    ability, na_reason = assess_sql_ability(
        payload.action_type, has_source_fields, has_transform
    )

    if ability == ABILITY_NOT_APPLICABLE:
        return SqlGenerationResult(
            status="NOT_APPLICABLE",
            ability=ability,
            not_applicable_reason=na_reason,
        )

    mode = "VALIDATION" if ability == ABILITY_VALIDATION_ONLY else "QUERY"
    system_prompt, user_prompt = _render_prompt(payload, mode)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    valid_tables = {f.table_name for f in payload.available_fields if f.table_name}
    valid_columns = {f.column_name for f in payload.available_fields if f.column_name}

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            data, _raw, model_used = complete_json(messages)
            parsed = _LlmSqlPayload(**data)
        except (LLMClientError, ValidationError, ValueError) as exc:
            last_error = f"attempt {attempt}: {exc}"
            logger.warning("SqlGenerator attempt %d failed: %s", attempt, exc)
            continue

        warnings, syntax_ok = _validate_sql(parsed.sql, valid_tables, valid_columns)
        confidence = max(0.0, min(1.0, parsed.confidence))
        if ability == ABILITY_PARTIAL:
            confidence = min(confidence, 0.5)  # PARTIAL 档置信度上限

        status = "READY"
        if not syntax_ok:
            status = "DEGRADED"

        return SqlGenerationResult(
            status=status,
            ability=ability,
            sql=parsed.sql,
            explanation=parsed.explanation,
            assumptions=parsed.assumptions,
            confidence=confidence,
            warnings=warnings,
            generated_by=f"{PROMPT_VERSION}@{model_used}",
        )

    # 全部失败 → 骨架兜底
    logger.error("SqlGenerator all retries failed: %s", last_error)
    return SqlGenerationResult(
        status="DEGRADED",
        ability=ability,
        sql=_build_skeleton_sql(payload, mode),
        explanation="LLM 调用失败，返回骨架 SQL，请人工补全。",
        confidence=0.2,
        warnings=[SqlWarning(
            type="LLM_FAILED",
            message=f"LLM 调用 {MAX_RETRIES + 1} 次失败，已返回骨架 SQL",
            severity="ERROR",
        )],
        generated_by=f"{PROMPT_VERSION}@skeleton",
    )


# ── 内部辅助 ────────────────────────────────────────────────────────────────


def _render_prompt(payload: SqlGenerationInput, mode: str) -> tuple[str, str]:
    raw = _PROMPT_PATH.read_text(encoding="utf-8")
    rendered = Template(raw).render(
        mode=mode,
        ticket_title=payload.ticket_title,
        reporting_items=payload.reporting_items,
        available_fields=payload.available_fields,
        reg_document=payload.reg_document,
        business_note=payload.business_note,
    )
    parts = rendered.split("===SYSTEM===", 1)
    if len(parts) != 2:
        raise RuntimeError("prompt template 缺少 ===SYSTEM=== 分隔符")
    sub = parts[1].split("===USER===", 1)
    if len(sub) != 2:
        raise RuntimeError("prompt template 缺少 ===USER=== 分隔符")
    return sub[0].strip(), sub[1].strip()


def _validate_sql(
    sql: str,
    valid_tables: set[str],
    valid_columns: set[str],
) -> tuple[list[SqlWarning], bool]:
    """L3-L5 校验：语法 / 表在清单 / 列在清单。返回 (warnings, syntax_ok)。"""
    warnings: list[SqlWarning] = []

    # L3: sqlglot 语法
    try:
        tree = sqlglot.parse_one(sql)
    except Exception as exc:  # sqlglot.errors.ParseError 等
        warnings.append(SqlWarning(
            type="SYNTAX_ERROR",
            message=f"SQL 语法解析失败：{str(exc)[:120]}",
            severity="ERROR",
        ))
        return warnings, False

    # L4: 表名在清单（仅当我们确实有清单时才校验，避免误报）
    if valid_tables:
        used_tables = {t.name for t in tree.find_all(exp.Table) if t.name}
        for tbl in sorted(used_tables - valid_tables):
            warnings.append(SqlWarning(
                type="TABLE_NOT_IN_CATALOG",
                message=f"表 {tbl} 未在业务勾选字段的来源表内（可能 AI 推断）",
                field_code=tbl,
                severity="INFO",
            ))

    # L5: 列名在清单（排除约定俗成的技术列）
    if valid_columns:
        used_columns = {c.name for c in tree.find_all(exp.Column) if c.name}
        used_columns -= _CONVENTIONAL_COLUMNS
        for col in sorted(used_columns - valid_columns):
            warnings.append(SqlWarning(
                type="FIELD_NOT_IN_SCOPE",
                message=f"字段 {col} 未在业务勾选清单内，请确认是否需要补充勾选或核对 AI 是否写错",
                field_code=col,
                severity="WARNING",
            ))

    return warnings, True


def _build_skeleton_sql(payload: SqlGenerationInput, mode: str) -> str:
    """LLM 全失败时的兜底骨架。"""
    table = next((f.table_name for f in payload.available_fields if f.table_name), "源表")
    cols = [f.column_name for f in payload.available_fields if f.column_name][:5]
    item_names = "、".join(i.name or i.code for i in payload.reporting_items[:3])
    select_cols = ",\n  ".join(cols) if cols else "/* TODO 选择字段 */"
    header = (
        f"-- 工单：{payload.ticket_title}\n"
        f"-- 业务备注：{payload.business_note or '（无）'}\n"
        f"-- 监管：{payload.reg_document.document_no or '（未抽到）'} "
        f"自 {payload.reg_document.effective_date or '?'} 起执行\n"
        f"-- ⚠️ LLM 调用失败，这是骨架，请人工补全加工逻辑（涉及指标：{item_names}）\n"
    )
    return (
        f"{header}"
        f"SELECT\n  {select_cols}\nFROM {table}\n"
        f"WHERE data_dt = '${{report_date}}'\n;"
    )
