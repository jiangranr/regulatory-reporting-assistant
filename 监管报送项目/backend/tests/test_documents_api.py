from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
import openpyxl
import pytest
from sqlalchemy import text
from sqlmodel import Session

from app.core.database import engine
from app.main import app
from app.services import document_profiler
from scripts.bootstrap_route_a import _ensure_g31_detail_items


G31_V2_REVISION_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "G31_修订对照表_v2_2026Q1.xlsx"
)
G31_252_TEMPLATE_FILE = (
    Path(__file__).resolve().parents[2]
    / "一表通"
    / "附件4：报表表样和填报说明汇总"
    / "2.修订报表（基础类、业务类、支持发展类）"
    / "G31"
    / "G31(252).xls"
)


def test_upload_document_returns_parse_metadata_and_unique_storage_paths():
    client = TestClient(app)

    first = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "repo_notice.txt",
                "第一条 监管报送字段应完整。\n\n第二条 资金账户应保持一致。".encode("utf-8"),
                "text/plain",
            )
        },
    )
    second = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "repo_notice.txt",
                "第一条 监管报送字段应完整。\n\n第二条 资金账户应保持一致。".encode("utf-8"),
                "text/plain",
            )
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_body = first.json()
    second_body = second.json()
    assert first_body["status"] == "PARSED"
    assert first_body["parse_status"] == "PARSED"
    assert first_body["parser"] == "text"
    assert first_body["char_count"] > 0
    assert first_body["paragraph_count"] == 2
    assert first_body["parse_quality"] == "GOOD"
    assert first_body["parse_error_message"] == ""
    assert first_body["storage_path"] != second_body["storage_path"]


def test_upload_empty_document_records_failed_parse_status():
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "FAILED"
    assert body["parse_status"] == "FAILED"
    assert body["parse_quality"] == "FAILED"
    assert body["parse_error_message"]


def test_upload_reporting_pair_combines_template_and_instruction():
    client = TestClient(app)

    response = client.post(
        "/api/documents/upload-reporting-pair",
        files={
            "template_file": (
                "G31(251).xls",
                b"fake excel content",
                "application/vnd.ms-excel",
            ),
            "instruction_file": (
                "G31-instruction.txt",
                "新增附表G31-A同业交易对手大额风险暴露明细表。\n\n填写交易对手名称和风险暴露余额。".encode("utf-8"),
                "text/plain",
            ),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PARSED"
    assert body["parser"].startswith("template_plus_")
    assert "G31(251).xls" in body["filename"]
    assert "G31-instruction.txt" in body["filename"]
    assert "非黑色重点片段" in body["parsed_text"]
    assert "新增附表G31-A" in body["parsed_text"]


def test_upload_reporting_triplet_returns_unmatched_revision_candidates():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["报表", "部分", "指标项目", "指标字段", "调整类型", "调整说明"])
    ws.append(["G31", "PART_II", "底层资产合计", "E_穿透层级", "新增", "251版新增穿透层级"])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    response = client.post(
        "/api/documents/upload-reporting-triplet?object_code=G31",
        files={
            "revision_table_file": (
                "G31_revision.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["revision_entry_count"] == 1
    assert body["scan_results"] == []
    assert body["revision_candidates"][0]["match_status"] == "UNMATCHED_NEW"
    assert body["revision_candidates"][0]["row_label"] == "底层资产合计"
    assert "新增候选 1 条" in body["scan_summary"]
    raw_response = client.get(f"/api/documents/{body['document']['id']}/raw-text")

    assert raw_response.status_code == 200
    raw_body = raw_response.json()
    assert raw_body["document_id"] == body["document"]["id"]
    assert raw_body["source"] == "revision_table"
    assert "修订对照表解析明细" in raw_body["text"]
    assert "底层资产合计 × E_穿透层级" in raw_body["text"]
    assert "251版新增穿透层级" in raw_body["text"]

    profile_response = client.post(f"/api/documents/{body['document']['id']}/profile")

    assert profile_response.status_code == 201
    profile = profile_response.json()
    assert len(profile["change_signals"]) == 1
    assert profile["change_signals"][0]["table_code"] == "G31"
    assert profile["change_signals"][0]["indicator_hint"] == "底层资产合计 × E_穿透层级"
    assert profile["change_signals"][0]["change_type"] == "ADD"
    assert profile["change_signals"][0]["match_status"] == "UNMATCHED_NEW"


def test_upload_reporting_triplet_v2_profile_uses_business_field_name_for_indicator_hint():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    response = client.post(
        "/api/documents/upload-reporting-triplet?object_code=G31",
        files={
            "revision_table_file": (
                "G31_修订对照表_v2_2026Q1.xlsx",
                G31_V2_REVISION_FILE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["revision_entry_count"] == 8

    raw_response = client.get(f"/api/documents/{body['document']['id']}/raw-text")

    assert raw_response.status_code == 200
    raw_text = raw_response.json()["text"]
    assert "修正久期" in raw_text
    assert "新增 C 列" in raw_text
    assert " | - | - |" not in raw_text

    profile_response = client.post(f"/api/documents/{body['document']['id']}/profile")

    assert profile_response.status_code == 201
    profile = profile_response.json()
    indicator_hints = [signal["indicator_hint"] for signal in profile["change_signals"]]
    assert "修正久期" in indicator_hints
    assert "×" not in indicator_hints
    assert all(hint.strip() and hint.strip() != "×" for hint in indicator_hints)
    preferred_stock_signal = next(
        signal for signal in profile["change_signals"] if signal["indicator_hint"] == "优先股投资余额"
    )
    issuer_type_signal = next(
        signal for signal in profile["change_signals"] if signal["indicator_hint"] == "发行人类型"
    )
    bill_signal = next(
        signal for signal in profile["change_signals"] if signal["indicator_hint"] == "票据投资余额"
    )
    assert issuer_type_signal["match_status"] == "SEMANTIC_FIELD_MATCH"
    assert issuer_type_signal["composite_match"]["match_type"] == "SEMANTIC_FIELD_MATCH"
    assert issuer_type_signal["composite_match"]["measure_fields"][0]["field_code"] == "bond_investment.issuer_type"
    assert bill_signal["match_status"] == "COMPOSITE_SEMANTIC_MATCH"
    assert {item["value_code"] for item in bill_signal["composite_match"]["filter_conditions"]} == {
        "BANK_ACCEPTANCE_BILL",
        "COMMERCIAL_ACCEPTANCE_BILL",
    }
    assert preferred_stock_signal["match_status"] == "COMPOSITE_SEMANTIC_MATCH"
    assert preferred_stock_signal["composite_match"]["match_type"] == "COMPOSITE_SEMANTIC_MATCH"
    assert preferred_stock_signal["composite_match"]["condition_phrase"] == "优先股"
    assert preferred_stock_signal["composite_match"]["measure_phrase"] == "投资余额"
    assert preferred_stock_signal["composite_match"]["filter_conditions"] == [
        {
            "field_code": "ods_invest_position.asset_type",
            "field_name": "投资资产类型",
            "operator": "=",
            "value_code": "PREFERRED_STOCK",
            "value_name": "优先股",
            "confidence_level": "HIGH",
        }
    ]


@pytest.mark.skipif(not G31_252_TEMPLATE_FILE.exists(), reason="G31 252 template file not available")
def test_profile_excel_only_triplet_uses_template_diff_without_llm(monkeypatch):
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")
    with Session(engine) as session:
        _ensure_g31_detail_items(session)
        session.commit()

    def fail_generate_profile(*_args, **_kwargs):
        raise AssertionError("Excel-only triplet profile must not call LLM profiling")

    monkeypatch.setattr(document_profiler, "generate_document_profile", fail_generate_profile)

    response = client.post(
        "/api/documents/upload-reporting-triplet?object_code=G31",
        files={
            "template_file": (
                "G31(252).xls",
                G31_252_TEMPLATE_FILE.read_bytes(),
                "application/vnd.ms-excel",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["revision_table_parsed"] is False
    assert body["excel_diff_count"] > 0

    profile_response = client.post(f"/api/documents/{body['document']['id']}/profile")

    assert profile_response.status_code == 201
    profile = profile_response.json()
    assert profile["llm_model"] == "rule-based-triplet-excel-diff"
    assert profile["should_create_task"] is True
    assert profile["affected_table_codes"] == ["G31"]
    assert profile["change_signals"]
    assert {signal["table_code"] for signal in profile["change_signals"]} == {"G31"}
    assert {signal["change_type"] for signal in profile["change_signals"]} & {"ADD", "DELETE", "MODIFY"}
    assert all(signal["indicator_hint"].strip() for signal in profile["change_signals"])
    assert any("新版 Excel" in signal["evidence_text"] for signal in profile["change_signals"])
    assert '"source": "triplet_excel_diff"' in profile["raw_response"]


def test_list_documents_handles_legacy_null_parse_error_message():
    client = TestClient(app)
    upload = client.post(
        "/api/documents/upload",
        files={"file": ("legacy.txt", b"legacy document text", "text/plain")},
    )
    document_id = upload.json()["id"]
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE reg_documents SET parse_error_message = NULL WHERE id = :document_id"),
            {"document_id": document_id},
        )

    response = client.get("/api/documents")

    assert response.status_code == 200
    document = next(item for item in response.json() if item["id"] == document_id)
    assert document["parse_error_message"] == ""
