from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.database import engine
from app.main import app
from app.models.db_models import (
    BusinessConceptValueMapping,
    DataFieldCodeValue,
    MeasureFieldMapping,
    RegConcept,
    RegConceptAlias,
)
from app.services.composite_signal_matcher import build_composite_match, build_semantic_field_match


def test_seed_1104_adds_concept_driven_code_and_measure_mappings():
    client = TestClient(app)
    response = client.post("/api/reporting/seed-1104")

    assert response.status_code == 200

    with Session(engine) as session:
        code_value = session.exec(
            select(DataFieldCodeValue).where(
                DataFieldCodeValue.field_code == "ods_invest_position.asset_type",
                DataFieldCodeValue.value_code == "PREFERRED_STOCK",
            )
        ).first()
        concept_mapping = session.exec(
            select(BusinessConceptValueMapping).where(
                BusinessConceptValueMapping.concept_name == "优先股",
                BusinessConceptValueMapping.value_code == "PREFERRED_STOCK",
            )
        ).first()
        measure_mapping = session.exec(
            select(MeasureFieldMapping).where(
                MeasureFieldMapping.measure_concept_code == "MEASURE_INVESTMENT_BALANCE",
                MeasureFieldMapping.field_code == "ods_invest_position.book_balance",
            )
        ).first()
        measure_concept = session.exec(
            select(RegConcept).where(RegConcept.concept_code == "MEASURE_INVESTMENT_BALANCE")
        ).first()

    assert code_value is not None
    assert code_value.value_name == "优先股"
    assert concept_mapping is not None
    assert concept_mapping.field_code == "ods_invest_position.asset_type"
    assert measure_mapping is not None
    assert measure_mapping.reporting_object_code == "G31"
    assert measure_concept is not None
    assert measure_concept.concept_type == "MEASURE"


def test_preferred_stock_balance_builds_concept_plus_measure_composite_match():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        match = build_composite_match(
            session=session,
            table_code="G31",
            indicator_hint="优先股投资余额",
            evidence_text="从 G31 移出：优先股不再计入债券投资余额，迁移至权益类投资明细表。",
        )

    assert match is not None
    assert match.match_type == "COMPOSITE_SEMANTIC_MATCH"
    assert match.pattern_code == "G31_CLASSIFICATION_MEASURE"
    assert match.measure_phrase == "投资余额"
    assert match.condition_phrase == "优先股"
    assert match.needs_review is True
    assert "G31.PART_I.1_0.A_穿透前_期末余额" in match.reporting_item_codes
    assert "dm_g31_position.position_balance" in match.measure_field_codes
    assert "ods_invest_position.book_balance" in match.measure_field_codes
    assert "ods_invest_position.asset_type" in match.condition_field_codes
    assert match.conditions == [
        {
            "field_code": "ods_invest_position.asset_type",
            "field_name": "投资资产类型",
            "operator": "=",
            "value_code": "PREFERRED_STOCK",
            "value_name": "优先股",
            "confidence_level": "HIGH",
        }
    ]


def test_bill_balance_builds_composite_match_from_bottom_code_values():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        match = build_composite_match(
            session=session,
            table_code="G31",
            indicator_hint="票据投资余额",
            evidence_text="新增字段：银行承兑汇票 + 商业承兑汇票，不再计入债券投资余额。",
        )

    assert match is not None
    assert match.condition_phrase == "票据"
    assert match.measure_phrase == "投资余额"
    assert {condition["value_code"] for condition in match.conditions} == {
        "BANK_ACCEPTANCE_BILL",
        "COMMERCIAL_ACCEPTANCE_BILL",
    }
    assert "ods_invest_position.asset_type" in match.condition_field_codes


def test_issuer_type_builds_semantic_field_match_without_measure():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        match = build_semantic_field_match(
            session=session,
            table_code="G31",
            indicator_hint="发行人类型",
            evidence_text="发行人类型枚举值细化。",
        )

    assert match is not None
    assert match.match_type == "SEMANTIC_FIELD_MATCH"
    assert match.condition_phrase == "发行人类型"
    assert match.measure_phrase == ""
    assert match.measure_fields == [
        {
            "field_code": "bond_investment.issuer_type",
            "field_name": "债券发行人类型",
            "table_name": "bond_investment",
            "column_name": "issuer_type",
            "field_role": "DIMENSION_FIELD",
            "confidence_score": 0.8,
        }
    ]


def test_code_value_name_can_be_used_as_concept_alias_for_composite_match():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        preferred_stock = session.exec(
            select(RegConcept).where(RegConcept.concept_code == "CON_PREFERRED_STOCK")
        ).one()
        existing_alias = session.exec(
            select(RegConceptAlias).where(
                RegConceptAlias.concept_id == preferred_stock.id,
                RegConceptAlias.alias_text == "优先股类别",
            )
        ).first()
        if existing_alias is None:
            session.add(
                RegConceptAlias(
                    concept_id=preferred_stock.id,
                    alias_text="优先股类别",
                    alias_source="REGULATION",
                )
            )
            session.commit()

        match = build_composite_match(
            session=session,
            table_code="G31",
            indicator_hint="优先股类别账面余额",
            evidence_text="优先股类别账面余额调整。",
        )

    assert match is not None
    assert match.condition_phrase == "优先股"
    assert match.measure_phrase == "投资余额"
    assert match.matched_concepts[0]["concept_code"] == "CON_PREFERRED_STOCK"
    assert match.matched_concepts[1]["concept_code"] == "MEASURE_INVESTMENT_BALANCE"


def test_composite_match_requires_both_condition_and_measure():
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        assert build_composite_match(session, "G31", "优先股", "") is None
        assert build_composite_match(session, "G31", "投资余额", "") is None
        assert build_composite_match(session, "G24", "优先股投资余额", "") is None
