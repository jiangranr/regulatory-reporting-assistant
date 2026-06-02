import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.database import engine
from app.main import app
from app.models.db_models import AuditLog, DocumentTaskProfile, RegDocument
from app.models.enums import DocumentStatus
from app.services import document_profiler


def _seed_profile() -> tuple[int, int]:
    with Session(engine) as session:
        document = RegDocument(
            filename="hallucination-review.txt",
            storage_path="/tmp/hallucination-review.txt",
            title="防幻觉复核测试",
            parsed_text="本期新增绿色债券投资余额字段。",
            status=DocumentStatus.PARSED,
            parse_status=DocumentStatus.PARSED,
        )
        session.add(document)
        session.commit()
        session.refresh(document)

        profile = DocumentTaskProfile(
            document_id=document.id,
            affected_table_codes='["G31"]',
            in_scope_tables='["G31"]',
            change_signals=json.dumps(
                [
                    {
                        "table_code": "G31",
                        "indicator_hint": "绿色债券投资余额",
                        "change_type": "ADD",
                        "evidence_text": "本期新增绿色债券投资余额字段。",
                        "confidence": 0.9,
                        "source_type": "LLM",
                        "grounding_status": "VERIFIED",
                        "grounding_coverage": 1.0,
                    },
                    {
                        "table_code": "G31",
                        "indicator_hint": "绿色债券投资余额删除",
                        "change_type": "DELETE",
                        "evidence_text": "本期删除绿色债券投资余额字段。",
                        "confidence": 0.3,
                        "source_type": "LLM",
                        "grounding_status": "UNVERIFIED",
                        "grounding_coverage": 0.25,
                    },
                    {
                        "table_code": "G31",
                        "indicator_hint": "新增 C 列",
                        "change_type": "ADD",
                        "evidence_text": "Excel 差异：新增 C 列",
                        "confidence": 0.8,
                        "source_type": "EXCEL_DIFF",
                        "grounding_status": "RULE_BASED",
                        "grounding_coverage": 1.0,
                    },
                ],
                ensure_ascii=False,
            ),
            suggested_route="FULL_ANALYSIS",
            should_create_task=True,
            confidence_score=0.7,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
        return document.id, profile.id


def test_get_document_hallucination_metrics_separates_ai_and_rule_based_signals():
    document_id, _ = _seed_profile()
    client = TestClient(app)

    response = client.get(f"/api/documents/{document_id}/hallucination-metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total_signals"] == 3
    assert body["ai_signals"] == 2
    assert body["rule_based_signals"] == 1
    assert body["verified_signals"] == 1
    assert body["unverified_signals"] == 1
    assert body["grounding_rate"] == 0.5
    assert body["suspected_hallucination_rate"] == 0.5
    assert body["isolation_rate"] == 0.5


def test_review_document_signal_updates_metrics_and_writes_audit_log():
    document_id, profile_id = _seed_profile()
    client = TestClient(app)

    response = client.post(
        f"/api/documents/{document_id}/signals/1/review",
        json={
            "action": "REJECTED",
            "reviewer": "qa_reviewer",
            "comment": "原文没有删除要求，退回 AI 结论。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["signal"]["human_review_status"] == "REJECTED"
    assert body["metrics"]["rejected_signals"] == 1
    assert body["metrics"]["pending_review_signals"] == 0

    with Session(engine) as session:
        profile = session.get(DocumentTaskProfile, profile_id)
        signals = json.loads(profile.change_signals)
        assert signals[1]["human_review_status"] == "REJECTED"

        audit = session.exec(
            select(AuditLog)
            .where(AuditLog.target_type == "DOCUMENT_SIGNAL")
            .where(AuditLog.target_id == profile_id)
            .order_by(AuditLog.created_at.desc())
        ).first()
        assert audit is not None
        assert audit.action == "SIGNAL_REVIEWED"
        assert '"reviewer": "qa_reviewer"' in audit.detail


def test_profile_document_writes_generation_grounding_and_quarantine_audit_logs(monkeypatch):
    def fake_generate_profile(*_args, **_kwargs):
        return document_profiler.Document1104ProfileDraft(
            has_1104_reference=True,
            affected_table_codes=["G31"],
            in_scope_tables=["G31"],
            change_signals=[
                document_profiler.TableChangeSignal(
                    table_code="G31",
                    indicator_hint="绿色债券投资余额删除",
                    change_type="DELETE",
                    evidence_text="本期删除绿色债券投资余额字段。",
                    confidence=0.3,
                    evidence_verified=False,
                    grounding_status="UNVERIFIED",
                    grounding_coverage=0.25,
                )
            ],
            suggested_route="FULL_ANALYSIS",
            should_create_task=True,
            confidence_score=0.3,
        )

    monkeypatch.setattr(document_profiler, "generate_document_profile", fake_generate_profile)
    with Session(engine) as session:
        document = RegDocument(
            filename="hallucination-profile.txt",
            storage_path="/tmp/hallucination-profile.txt",
            title="防幻觉画像审计测试",
            parsed_text="本期新增绿色债券投资余额字段。",
            status=DocumentStatus.PARSED,
            parse_status=DocumentStatus.PARSED,
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        document_id = document.id

    client = TestClient(app)
    response = client.post(f"/api/documents/{document_id}/profile")

    assert response.status_code == 201
    profile_id = response.json()["id"]
    with Session(engine) as session:
        audits = session.exec(
            select(AuditLog)
            .where(AuditLog.target_type == "DOCUMENT_SIGNAL")
            .where(AuditLog.target_id == profile_id)
        ).all()
        actions = {audit.action for audit in audits}
        assert actions == {
            "SIGNAL_GENERATED",
            "SIGNAL_GROUNDING_EVALUATED",
            "SIGNAL_QUARANTINED",
        }
        grounding = next(audit for audit in audits if audit.action == "SIGNAL_GROUNDING_EVALUATED")
        assert '"grounding_status": "UNVERIFIED"' in grounding.detail
        assert '"grounding_coverage": 0.25' in grounding.detail


def test_accepting_quarantined_signal_writes_release_audit_log():
    document_id, profile_id = _seed_profile()
    client = TestClient(app)

    response = client.post(
        f"/api/documents/{document_id}/signals/1/review",
        json={
            "action": "ACCEPTED",
            "reviewer": "qa_reviewer",
            "comment": "经业务确认后人工放行。",
        },
    )

    assert response.status_code == 200
    with Session(engine) as session:
        actions = {
            audit.action
            for audit in session.exec(
                select(AuditLog)
                .where(AuditLog.target_type == "DOCUMENT_SIGNAL")
                .where(AuditLog.target_id == profile_id)
            ).all()
        }
        assert "SIGNAL_REVIEWED" in actions
        assert "SIGNAL_RELEASED" in actions
