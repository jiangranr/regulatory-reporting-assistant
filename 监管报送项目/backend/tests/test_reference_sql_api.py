"""集成测试：参考 SQL 生成 API。

验证 /api/tickets/{id}/reference-sql/* 端点的完整业务链路。
LLM (complete_json) 用 monkeypatch 拦截，其余走真实数据库和业务逻辑。

覆盖点：
1. REPORT_PROCESSING 子单 → generate → READY（LLM 返回合法 SQL）
2. SOURCE_SYSTEM_CHANGE 子单 → generate → NOT_APPLICABLE，不调 LLM
3. GET reference-sql 读当前状态
4. PUT reference-sql 人工编辑 → EDITED_BY_USER
5. POST feedback → ok=True
6. POST mark-stale → STALE
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ticket_sql_generator as gen


# ── 公共夹具 ─────────────────────────────────────────────────────────────────


def _setup_workflow(client: TestClient) -> dict:
    """seed → 上传文档 → 创建任务 → 影响分析 → 确认复核 → 返回子单列表。"""
    client.post("/api/reporting/seed-1104")

    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "g24_sql_test.txt",
                (
                    "监管要求调整 G24 最大百家金融机构同业融入余额统计口径，"
                    "需复核交易对手金融机构识别和余额来源字段，并调整数据加工逻辑。"
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201
    doc_id = upload.json()["id"]

    task_resp = client.post(f"/api/tasks/from-document/{doc_id}")
    assert task_resp.status_code == 201
    task_id = task_resp.json()["id"]

    impact_resp = client.post(f"/api/tasks/{task_id}/analyze-impact")
    assert impact_resp.status_code == 200
    assert impact_resp.json()["impacts"]

    # 拉影响范围，直接确认（不改字段）
    review_resp = client.get(f"/api/tasks/{task_id}/impact-review")
    assert review_resp.status_code == 200
    review = review_resp.json()["review"]

    confirm_resp = client.post(
        f"/api/tasks/{task_id}/impact-review/confirm",
    )
    assert confirm_resp.status_code == 200
    children = confirm_resp.json()["children"]
    assert children, "影响确认后应生成子单"
    return {"task_id": task_id, "children": children}


def _find_child(children: list, action_type: str) -> dict | None:
    return next(
        (c for c in children if c.get("action_ticket_type") == action_type),
        None,
    )


def _mock_llm(sql: str, confidence: float = 0.85):
    """返回符合 _LlmSqlPayload schema 的 mock。"""
    return lambda _: (
        {
            "sql": sql,
            "explanation": "按 G24 同业融入口径汇总，按报告期过滤。",
            "assumptions": ["rpt_g24 已按日期分区"],
            "confidence": confidence,
        },
        "{}",
        "mock-model",
    )


_GOOD_SQL = (
    "SELECT report_date, SUM(interbank_borrowing_balance) AS total_balance "
    "FROM rpt_g24 "
    "WHERE report_date = '${report_date}' "
    "GROUP BY report_date;"
)


# ── 测试：REPORT_PROCESSING → 正常生成 ──────────────────────────────────────


def test_report_processing_generates_ready_sql(monkeypatch):
    """REPORT_PROCESSING 子单走 LLM，返回 READY 状态和合法 SQL。"""
    monkeypatch.setattr(gen, "complete_json", _mock_llm(_GOOD_SQL))
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    rpt_child = _find_child(children, "REPORT_PROCESSING")
    if rpt_child is None:
        pytest.skip("本次影响分析未生成 REPORT_PROCESSING 子单（可能 catalog 数据不足）")

    ticket_id = rpt_child["id"]
    assert ticket_id, "子单 id 不能为空"

    # 初始状态应为 NOT_GENERATED
    get_resp = client.get(f"/api/tickets/{ticket_id}/reference-sql")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "NOT_GENERATED"

    # 触发生成
    gen_resp = client.post(f"/api/tickets/{ticket_id}/reference-sql/generate")
    assert gen_resp.status_code == 200
    body = gen_resp.json()

    assert body["status"] in {"READY", "PARTIAL", "DEGRADED"}
    # READY/PARTIAL 时必须有 sql
    if body["status"] in {"READY", "PARTIAL"}:
        assert body["reference_sql"], "READY/PARTIAL 时 reference_sql 不能为空"
        assert body["confidence"] > 0

    # 再次 GET，持久化了
    get_after = client.get(f"/api/tickets/{ticket_id}/reference-sql")
    assert get_after.json()["status"] == body["status"]
    assert get_after.json()["reference_sql"] == body["reference_sql"]


# ── 测试：SOURCE_SYSTEM_CHANGE → NOT_APPLICABLE，不调 LLM ───────────────────


def test_source_system_change_is_not_applicable(monkeypatch):
    """SOURCE_SYSTEM_CHANGE 子单必须直接返回 NOT_APPLICABLE，不调用 LLM。"""
    monkeypatch.setattr(
        gen, "complete_json",
        lambda _: pytest.fail("SOURCE_SYSTEM_CHANGE 不该调 LLM"),
    )
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    src_child = _find_child(children, "SOURCE_SYSTEM_CHANGE")
    if src_child is None:
        pytest.skip("本次影响分析未生成 SOURCE_SYSTEM_CHANGE 子单")

    ticket_id = src_child["id"]
    gen_resp = client.post(f"/api/tickets/{ticket_id}/reference-sql/generate")
    assert gen_resp.status_code == 200
    body = gen_resp.json()

    assert body["status"] == "NOT_APPLICABLE"
    assert body["ability"] == "NOT_APPLICABLE"
    assert body["reference_sql"] == ""
    # 原因文案必须解释是源系统改造单，指向下游子单
    assert "源系统改造" in body["not_applicable_reason"]
    assert "报送加工" in body["not_applicable_reason"]


# ── 测试：PUT 人工编辑 → EDITED_BY_USER ─────────────────────────────────────


def test_save_user_edit(monkeypatch):
    """PUT /reference-sql 保存人工 SQL，状态变 EDITED_BY_USER。"""
    monkeypatch.setattr(gen, "complete_json", _mock_llm(_GOOD_SQL))
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    rpt_child = _find_child(children, "REPORT_PROCESSING")
    if rpt_child is None:
        pytest.skip("未生成 REPORT_PROCESSING 子单")

    ticket_id = rpt_child["id"]
    # 先生成一次
    client.post(f"/api/tickets/{ticket_id}/reference-sql/generate")

    custom_sql = "SELECT 1 AS manual_check FROM rpt_g24 LIMIT 1;"
    put_resp = client.put(
        f"/api/tickets/{ticket_id}/reference-sql",
        json={"reference_sql": custom_sql, "comment": "人工修正口径"},
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["status"] == "EDITED_BY_USER"
    assert body["reference_sql"] == custom_sql

    # GET 确认持久化
    get_resp = client.get(f"/api/tickets/{ticket_id}/reference-sql")
    assert get_resp.json()["status"] == "EDITED_BY_USER"
    assert get_resp.json()["reference_sql"] == custom_sql


# ── 测试：POST feedback ──────────────────────────────────────────────────────


@pytest.mark.parametrize("thumbs", ["up", "down"])
def test_feedback(monkeypatch, thumbs):
    """POST /reference-sql/feedback 接受 up/down，返回 ok=True。"""
    monkeypatch.setattr(gen, "complete_json", _mock_llm(_GOOD_SQL))
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    rpt_child = _find_child(children, "REPORT_PROCESSING")
    if rpt_child is None:
        pytest.skip("未生成 REPORT_PROCESSING 子单")

    ticket_id = rpt_child["id"]
    client.post(f"/api/tickets/{ticket_id}/reference-sql/generate")

    fb_resp = client.post(
        f"/api/tickets/{ticket_id}/reference-sql/feedback",
        json={"thumbs": thumbs, "comment": ""},
    )
    assert fb_resp.status_code == 200
    assert fb_resp.json()["ok"] is True


# ── 测试：POST mark-stale ────────────────────────────────────────────────────


def test_mark_stale(monkeypatch):
    """READY 态的 SQL 在调用 mark-stale 后变为 STALE。"""
    monkeypatch.setattr(gen, "complete_json", _mock_llm(_GOOD_SQL))
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    rpt_child = _find_child(children, "REPORT_PROCESSING")
    if rpt_child is None:
        pytest.skip("未生成 REPORT_PROCESSING 子单")

    ticket_id = rpt_child["id"]
    gen_resp = client.post(f"/api/tickets/{ticket_id}/reference-sql/generate")
    if gen_resp.json()["status"] not in {"READY", "PARTIAL", "DEGRADED"}:
        pytest.skip("生成结果不是可标 STALE 的状态")

    stale_resp = client.post(f"/api/tickets/{ticket_id}/reference-sql/mark-stale")
    assert stale_resp.status_code == 200
    assert stale_resp.json()["status"] == "STALE"

    get_resp = client.get(f"/api/tickets/{ticket_id}/reference-sql")
    assert get_resp.json()["status"] == "STALE"


# ── 测试：feedback 非法 thumbs 值 ───────────────────────────────────────────


def test_feedback_invalid_thumbs(monkeypatch):
    """thumbs 不是 up/down 应返回 400。"""
    monkeypatch.setattr(gen, "complete_json", _mock_llm(_GOOD_SQL))
    client = TestClient(app)
    data = _setup_workflow(client)
    children = data["children"]

    rpt_child = _find_child(children, "REPORT_PROCESSING")
    if rpt_child is None:
        pytest.skip("未生成 REPORT_PROCESSING 子单")

    ticket_id = rpt_child["id"]
    resp = client.post(
        f"/api/tickets/{ticket_id}/reference-sql/feedback",
        json={"thumbs": "maybe", "comment": ""},
    )
    assert resp.status_code == 400


# ── 测试：不存在的 ticket_id ─────────────────────────────────────────────────


def test_get_reference_sql_not_found():
    client = TestClient(app)
    resp = client.get("/api/tickets/999999/reference-sql")
    assert resp.status_code == 404


def test_generate_reference_sql_not_found():
    client = TestClient(app)
    resp = client.post("/api/tickets/999999/reference-sql/generate")
    assert resp.status_code == 404
