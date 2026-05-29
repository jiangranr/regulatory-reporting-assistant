"""单元测试：参考 SQL 生成 + 可生成性闸门。

策略：mock llm_client.complete_json，独立验证闸门 / 5 层校验 / 兜底。
"""

from __future__ import annotations

import json

import pytest

from app.models.enums import ActionTicketType as A
from app.services import ticket_sql_generator as gen
from app.services.ticket_sql_generator import (
    FieldContext,
    RegDocumentContext,
    ReportingItemContext,
    SqlGenerationInput,
    assess_sql_ability,
    generate_reference_sql,
)


# ── 闸门 4 档 ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action,has_fields,has_transform,expected",
    [
        (A.SCOPE_CONFIRM, True, True, "NOT_APPLICABLE"),
        (A.TASK_INIT, True, True, "NOT_APPLICABLE"),
        (A.TEST_ACCEPTANCE, True, True, "NOT_APPLICABLE"),
        (A.ARCHIVE_REVIEW, True, True, "NOT_APPLICABLE"),
        (A.SOURCE_SYSTEM_CHANGE, False, False, "NOT_APPLICABLE"),
        (A.VALIDATION_RULE, True, True, "VALIDATION_ONLY"),
        (A.DATA_MAPPING, True, True, "CAN_GENERATE"),
        (A.DATA_MAPPING, True, False, "PARTIAL"),
        (A.DATA_MAPPING, False, False, "NOT_APPLICABLE"),
        (A.REPORT_PROCESSING, True, True, "CAN_GENERATE"),
    ],
)
def test_assess_sql_ability(action, has_fields, has_transform, expected):
    ability, reason = assess_sql_ability(action, has_fields, has_transform)
    assert ability == expected
    if expected == "NOT_APPLICABLE":
        assert reason  # 必须给人话原因
    else:
        assert reason == ""


# ── 夹具 ────────────────────────────────────────────────────────────────────


def _make_payload(action="DATA_MAPPING", with_transform=True, with_fields=True):
    fields = []
    if with_fields:
        fields = [
            FieldContext(
                code="dm_g31.position_balance",
                table_name="dm_g31",
                column_name="position_balance",
                data_type="DECIMAL",
                business_meaning="期末余额",
                transform_expression="sum(position_balance)" if with_transform else "",
            ),
            FieldContext(
                code="dm_g31.asset_type",
                table_name="dm_g31",
                column_name="asset_type",
                data_type="VARCHAR",
            ),
        ]
    return SqlGenerationInput(
        ticket_title="穿透后期末余额加工",
        action_type=action,
        reporting_items=[ReportingItemContext("G31.1", "穿透后期末余额")],
        available_fields=fields,
        reg_document=RegDocumentContext(document_no="15号", effective_date="2026-07-01"),
        business_note="优先处理",
    )


def _valid_sql_response(sql: str, confidence=0.82):
    return {
        "sql": sql,
        "explanation": "按穿透后口径汇总",
        "assumptions": ["asset_type 覆盖穿透口径"],
        "confidence": confidence,
    }


_GOOD_SQL = (
    "-- 工单：穿透后期末余额\n-- 业务备注：优先处理\n-- 监管：15号 自 2026-07-01\n"
    "SELECT data_dt, SUM(position_balance) AS bal FROM dm_g31 "
    "WHERE asset_type IN ('BOND') AND data_dt = '${report_date}' GROUP BY data_dt;"
)


# ── 主流程 ──────────────────────────────────────────────────────────────────


def test_not_applicable_skips_llm(monkeypatch):
    monkeypatch.setattr(gen, "complete_json", lambda m: pytest.fail("不该调 LLM"))
    result = generate_reference_sql(_make_payload(action="SCOPE_CONFIRM"))
    assert result.status == "NOT_APPLICABLE"
    assert result.ability == "NOT_APPLICABLE"
    assert result.not_applicable_reason
    assert result.sql == ""


def test_happy_path(monkeypatch):
    monkeypatch.setattr(
        gen, "complete_json",
        lambda m: (_valid_sql_response(_GOOD_SQL), "{}", "qwen-plus"),
    )
    result = generate_reference_sql(_make_payload())
    assert result.status == "READY"
    assert result.ability == "CAN_GENERATE"
    assert "SUM(position_balance)" in result.sql
    assert result.confidence == 0.82
    assert "qwen-plus" in result.generated_by
    # 所有字段都在清单内，无 FIELD_NOT_IN_SCOPE
    assert not any(w.type == "FIELD_NOT_IN_SCOPE" for w in result.warnings)


def test_fabricated_field_flagged(monkeypatch):
    bad_sql = "SELECT data_dt, fake_column FROM dm_g31 WHERE data_dt = '${report_date}';"
    monkeypatch.setattr(
        gen, "complete_json",
        lambda m: (_valid_sql_response(bad_sql), "{}", "qwen-plus"),
    )
    result = generate_reference_sql(_make_payload())
    assert result.status == "READY"  # 字段编造不阻塞，只告警
    warns = [w for w in result.warnings if w.type == "FIELD_NOT_IN_SCOPE"]
    assert warns
    assert warns[0].field_code == "fake_column"


def test_fabricated_table_flagged(monkeypatch):
    bad_sql = "SELECT position_balance FROM ghost_table WHERE data_dt = '${report_date}';"
    monkeypatch.setattr(
        gen, "complete_json",
        lambda m: (_valid_sql_response(bad_sql), "{}", "qwen-plus"),
    )
    result = generate_reference_sql(_make_payload())
    assert any(w.type == "TABLE_NOT_IN_CATALOG" and w.field_code == "ghost_table"
               for w in result.warnings)


def test_syntax_error_degrades(monkeypatch):
    monkeypatch.setattr(
        gen, "complete_json",
        lambda m: (_valid_sql_response("SELECT FROM WHERE GROUP"), "{}", "qwen-plus"),
    )
    result = generate_reference_sql(_make_payload())
    assert result.status == "DEGRADED"
    assert any(w.type == "SYNTAX_ERROR" for w in result.warnings)


def test_partial_caps_confidence(monkeypatch):
    monkeypatch.setattr(
        gen, "complete_json",
        lambda m: (_valid_sql_response(_GOOD_SQL, confidence=0.9), "{}", "qwen-plus"),
    )
    result = generate_reference_sql(_make_payload(with_transform=False))
    assert result.ability == "PARTIAL"
    assert result.confidence <= 0.5  # PARTIAL 上限收敛


def test_llm_failure_returns_skeleton(monkeypatch):
    from app.services.llm_client import LLMClientError

    def boom(m):
        raise LLMClientError("network down")

    monkeypatch.setattr(gen, "complete_json", boom)
    result = generate_reference_sql(_make_payload())
    assert result.status == "DEGRADED"
    assert result.confidence == pytest.approx(0.2)
    assert "dm_g31" in result.sql  # 骨架引用了真实表
    assert any(w.type == "LLM_FAILED" for w in result.warnings)


def test_validation_only_uses_validation_branch(monkeypatch):
    captured = {}

    def capture(messages):
        captured["system"] = messages[0]["content"]
        return _valid_sql_response(_GOOD_SQL), "{}", "qwen-plus"

    monkeypatch.setattr(gen, "complete_json", capture)
    result = generate_reference_sql(_make_payload(action="VALIDATION_RULE"))
    assert result.ability == "VALIDATION_ONLY"
    assert "对账校验" in captured["system"]  # 走了对账分支


def test_invalid_json_retries_then_skeleton(monkeypatch):
    calls = {"n": 0}

    def bad_schema(m):
        calls["n"] += 1
        return {"not_sql_field": "x"}, "{}", "qwen-plus"  # 缺 sql 字段

    monkeypatch.setattr(gen, "complete_json", bad_schema)
    result = generate_reference_sql(_make_payload())
    assert result.status == "DEGRADED"
    assert calls["n"] == 3  # 1 + 2 retries
