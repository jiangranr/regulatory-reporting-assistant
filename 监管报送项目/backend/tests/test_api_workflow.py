from fastapi.testclient import TestClient
import json

from app.main import app


def test_document_to_ticket_workflow():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    upload_response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "g24_notice.txt",
                "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径，需复核交易对手金融机构识别和余额来源，并追溯重算历史数据，同步调整内部数据加工逻辑与跨表一致性校验。".encode(
                    "utf-8"
                ),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 201
    document_id = upload_response.json()["id"]

    task_response = client.post(f"/api/tasks/from-document/{document_id}")
    assert task_response.status_code == 201
    task_id = task_response.json()["id"]

    impact_response = client.post(f"/api/tasks/{task_id}/analyze-impact")
    assert impact_response.status_code == 200
    impact = impact_response.json()["impacts"][0]
    assert impact["reporting_item_code"] == "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100"
    assert impact["impacted_reporting_field"] == "rpt_g24.interbank_borrowing_bal_top100"
    assert "interbank_deal.balance" in impact["impacted_source_fields"]

    ticket_response = client.post(f"/api/tasks/{task_id}/generate-ticket")
    assert ticket_response.status_code == 200
    ticket_payload = ticket_response.json()
    parent_content = ticket_payload["parent"]["content"]
    assert "母单类型" in parent_content
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in parent_content
    child = ticket_payload["children"][0]
    assert child["content"]
    assert child["summary"]
    assert child["responsible_system"]
    assert child["must_do"] != "[]"
    assert child["acceptance_criteria_structured"] != "[]"
    assert child["quality_score"] > 0

    workflow_response = client.get(f"/api/tasks/{task_id}/workflow")
    assert workflow_response.status_code == 200
    workflow = workflow_response.json()
    assert [step["name"] for step in workflow["steps"]] == [
        "上传发文",
        "条款证据",
        "影响识别",
        "规则卡片",
        "工单草稿",
    ]
    assert workflow["impact_items"]
    assert workflow["reporting_candidates"][0]["reporting_object_code"] == "G24"
    assert any(item["field_code"] == "interbank_deal.balance" for item in workflow["lineage_candidates"])
    assert workflow["ticket_drafts"]


def test_ticket_generation_returns_historical_cases_from_existing_tickets():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    def create_task() -> int:
        upload_response = client.post(
            "/api/documents/upload",
            files={
                    "file": (
                        "g24_notice_history.txt",
                        "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径，并同步调整内部数据加工逻辑与跨表一致性校验。".encode(
                            "utf-8"
                        ),
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
        return task_id

    first_task_id = create_task()
    first_ticket_response = client.post(f"/api/tasks/{first_task_id}/generate-ticket")
    assert first_ticket_response.status_code == 200

    second_task_id = create_task()
    second_ticket_response = client.post(f"/api/tasks/{second_task_id}/generate-ticket")
    assert second_ticket_response.status_code == 200

    children = second_ticket_response.json()["children"]
    histories = [
        case
        for child in children
        for case in json.loads(child["historical_cases"] or "[]")
    ]
    assert histories
    assert histories[0]["title"]
    assert histories[0]["reuse_score"] > 0
    assert histories[0]["matched_item_codes"] == ["G24.MAIN.INTERBANK_BORROWING_BAL_TOP100"]
