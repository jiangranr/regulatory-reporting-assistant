from fastapi.testclient import TestClient

from app.main import app
from app.services import document_profiler


def test_profile_document_uses_reporting_context_and_persists_profile(monkeypatch):
    captured: dict[str, object] = {}

    def fake_generate_profile(document, context):
        captured["document_title"] = document.title
        captured["object_names"] = [item["object_name"] for item in context["reporting_objects"]]
        captured["section_names"] = [item["section_name"] for item in context["reporting_sections"]]
        captured["item_codes"] = [item["item_code"] for item in context["reporting_items"]]
        captured["field_codes"] = [item["field_code"] for item in context["data_fields"]]
        captured["lineage_roles"] = [item["lineage_role"] for item in context["reporting_lineage"]]
        return document_profiler.Document1104ProfileDraft(
            has_1104_reference=True,
            affected_table_codes=["G24"],
            in_scope_tables=["G24"],
            out_of_scope_tables=[],
            change_signals=[
                document_profiler.TableChangeSignal(
                    table_code="G24",
                    section_hint="主表",
                    indicator_hint="同业融入余额",
                    change_type="SCOPE_ADJUST",
                    evidence_text="G24最大百家金融机构同业融入情况表中同业融入余额统计口径。",
                    confidence=0.86,
                )
            ],
            suggested_route="FULL_ANALYSIS",
            should_create_task=True,
            confidence_score=0.86,
            reason="文件涉及 1104 报表指标口径调整。",
            llm_model="fake-model",
            raw_response='{"ok": true}',
        )

    monkeypatch.setattr(document_profiler, "generate_document_profile", fake_generate_profile)
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")
    upload = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "profile_notice.txt",
                "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径。".encode(),
                "text/plain",
            )
        },
    )
    document_id = upload.json()["id"]

    response = client.post(f"/api/documents/{document_id}/profile")

    assert response.status_code == 201
    body = response.json()
    assert body["document_id"] == document_id
    assert body["suggested_route"] == "FULL_ANALYSIS"
    assert body["should_create_task"] is True
    assert body["affected_table_codes"] == ["G24"]
    assert body["in_scope_tables"] == ["G24"]
    assert body["change_signals"][0]["indicator_hint"] == "同业融入余额"
    assert body["change_signals"][0]["change_type"] == "SCOPE_ADJUST"
    assert "最大百家金融机构同业融入情况表" in captured["object_names"]
    assert "主表" in captured["section_names"]
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in captured["item_codes"]
    assert "interbank_deal.balance" in captured["field_codes"]
    assert "SOURCE_FIELD" in captured["lineage_roles"]

    get_response = client.get(f"/api/documents/{document_id}/profile")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == body["id"]


def test_profile_missing_document_returns_404():
    client = TestClient(app)

    response = client.post("/api/documents/999999/profile")

    assert response.status_code == 404
