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
    client = TestClient(app)
    task_id = _create_analyzed_g24_task(client)

    review_response = client.get(f"/api/tasks/{task_id}/impact-review")
    assert review_response.status_code == 200
    payload = review_response.json()
    assert payload["status"] == "EDITING"
    assert payload["stats"]["total_items"] >= 1

    review = payload["review"]
    item = review["items"][0]
    item["business_note"] = "修正口径优先排产，历史数据由 ETL 团队补录。"
    allowed_systems = {system["responsible_system"] for system in item["systems"]}
    assert allowed_systems <= {
        "REG_REPORTING_SYSTEM",
        "DATA_GOVERNANCE_PLATFORM",
        "DATA_MART_ETL",
        "SOURCE_SYSTEM",
        "DATA_QUALITY_PLATFORM",
        "TEST_ACCEPTANCE",
        "KNOWLEDGE_ARCHIVE",
    }

    etl_system = next(system for system in item["systems"] if system["responsible_system"] == "DATA_MART_ETL")
    etl_system["fields"].append(
        {
            "field_code": "manual.etl_override_field",
            "field_name": "业务补充字段",
            "lineage_role": "DERIVED_FIELD",
            "source": "BUSINESS",
            "selected": True,
            "edited": False,
            "removed": False,
            "is_required": False,
        }
    )
    source_system = next(system for system in item["systems"] if system["responsible_system"] == "SOURCE_SYSTEM")
    source_system["fields"][0]["selected"] = False

    save_response = client.put(f"/api/tasks/{task_id}/impact-review", json={"review": review})
    assert save_response.status_code == 200
    assert save_response.json()["ok"] is True

    confirm_response = client.post(f"/api/tasks/{task_id}/impact-review/confirm")
    assert confirm_response.status_code == 200
    ticket_payload = confirm_response.json()
    children = ticket_payload["children"]
    systems = {child["responsible_system"] for child in children}
    assert {"DATA_MART_ETL", "SOURCE_SYSTEM", "TEST_ACCEPTANCE", "KNOWLEDGE_ARCHIVE"} <= systems

    etl_child = next(child for child in children if child["responsible_system"] == "DATA_MART_ETL")
    assert "修正口径优先排产" in etl_child["business_note"]
    assert "manual.etl_override_field" in etl_child["affected_assets"]
    assert etl_child["must_do"] != "[]"
    assert etl_child["quality_score"] > 0

    workflow_response = client.get(f"/api/tasks/{task_id}/workflow")
    assert workflow_response.status_code == 200
    workflow_ticket_systems = {ticket["responsible_system"] for ticket in workflow_response.json()["ticket_drafts"]}
    assert "DATA_MART_ETL" in workflow_ticket_systems
    assert workflow_response.json()["task"]["status"] == "TICKET_GENERATED"
