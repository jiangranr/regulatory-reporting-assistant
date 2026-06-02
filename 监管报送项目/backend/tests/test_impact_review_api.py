import json

from fastapi.testclient import TestClient

from app.main import app


def _create_analyzed_g24_task(client: TestClient) -> int:
    client.post("/api/reporting/seed-1104")
    upload_response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "g24_impact_review_notice.txt",
                (
                    "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径，"
                    "需复核交易对手金融机构识别和余额来源，并追溯重算历史数据，"
                    "同步调整内部数据加工逻辑与跨表一致性校验。"
                ).encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201
    task_response = client.post(f"/api/tasks/from-document/{upload_response.json()['id']}")
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]
    impact_response = client.post(f"/api/tasks/{task_id}/analyze-impact")
    assert impact_response.status_code == 200
    assert impact_response.json()["impacts"]
    return task_id


def test_impact_review_save_confirm_generates_system_tickets():
    """新分桶规则：影响范围按真实 system_code（data_system_catalog）拆。

    G24 lineage 跨 4 个真实系统：
      - RPT             报送集市（rpt_g24.*）
      - DM_TREASURY     资金同业数据集市（dm_interbank_position.*）
      - INTERBANK_CORE  同业业务系统（interbank_deal.*）
      - COUNTERPARTY_MDM 交易对手主数据（counterparty.*）

    每个具体系统单独成桶/单，owner_team 走 data_system_catalog 登记的团队。
    """
    client = TestClient(app)
    task_id = _create_analyzed_g24_task(client)

    review_response = client.get(f"/api/tasks/{task_id}/impact-review")
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["status"] == "EDITING"
    assert payload["stats"]["total_items"] >= 1
    assert {
        "system_code": "INTERBANK_CORE",
        "system_name": "同业业务系统",
        "system_type": "SOURCE",
        "owner_team": "金融市场科技团队",
    } in payload["system_options"]

    review = payload["review"]
    item = review["items"][0]
    item["business_note"] = "修正口径优先排产，历史数据由 ETL 团队补录。"

    # G24 应该按真实 system_code 分桶
    real_systems = {system["responsible_system"] for system in item["systems"]}
    assert {"RPT", "DM_TREASURY", "INTERBANK_CORE", "COUNTERPARTY_MDM"} <= real_systems

    # 报送集市桶里展示名应该是 system_name 而不是抽象团队角色
    rpt_system = next(s for s in item["systems"] if s["responsible_system"] == "RPT")
    assert rpt_system["responsible_system_zh"] == "监管报送系统"
    assert rpt_system["system_type"] == "REPORTING"

    # 估值/源系统桶手工追加一个业务字段
    interbank_system = next(s for s in item["systems"] if s["responsible_system"] == "INTERBANK_CORE")
    interbank_system["fields"].append(
        {
            "field_code": "interbank_deal.manual_override",
            "field_name": "业务补充字段",
            "lineage_role": "SOURCE_FIELD",
            "source": "BUSINESS",
            "selected": True,
            "edited": False,
            "removed": False,
            "is_required": False,
        }
    )
    # 把对手方桶里第一条字段反选，验证 selected=False 不进工单
    counterparty_system = next(s for s in item["systems"] if s["responsible_system"] == "COUNTERPARTY_MDM")
    counterparty_system["fields"][0]["selected"] = False

    save_response = client.put(f"/api/tasks/{task_id}/impact-review", json={"review": review})
    assert save_response.status_code == 200
    assert save_response.json()["ok"] is True

    confirm_response = client.post(f"/api/tasks/{task_id}/impact-review/confirm")
    assert confirm_response.status_code == 200
    ticket_payload = confirm_response.json()
    children = ticket_payload["children"]
    systems = {child["responsible_system"] for child in children}
    # 每个真实系统都生成一张子单 + 两张支持单（TEST_ACCEPTANCE/KNOWLEDGE_ARCHIVE）
    assert {"RPT", "DM_TREASURY", "INTERBANK_CORE", "COUNTERPARTY_MDM"} <= systems
    assert {"TEST_ACCEPTANCE", "KNOWLEDGE_ARCHIVE"} <= systems

    # 同业源系统子单要含业务补充字段、业务备注，且 action_type 是 SOURCE_SYSTEM_CHANGE
    interbank_child = next(child for child in children if child["responsible_system"] == "INTERBANK_CORE")
    assert "修正口径优先排产" in interbank_child["business_note"]
    assert "interbank_deal.manual_override" in interbank_child["affected_assets"]
    assert interbank_child["action_ticket_type"] == "SOURCE_SYSTEM_CHANGE"
    assert interbank_child["must_do"] != "[]"
    assert interbank_child["quality_score"] > 0

    # RPT 集市是 REPORTING 类型，应该走 REPORT_PROCESSING
    rpt_child = next(child for child in children if child["responsible_system"] == "RPT")
    assert rpt_child["action_ticket_type"] == "REPORT_PROCESSING"

    workflow_response = client.get(f"/api/tasks/{task_id}/workflow")
    assert workflow_response.status_code == 200
    workflow_ticket_systems = {ticket["responsible_system"] for ticket in workflow_response.json()["ticket_drafts"]}
    assert "RPT" in workflow_ticket_systems
    assert "INTERBANK_CORE" in workflow_ticket_systems
    assert workflow_response.json()["task"]["status"] == "TICKET_GENERATED"
