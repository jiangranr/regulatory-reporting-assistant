"""Regression test for the 80-duplicate-rows bug.

Before 方案 2: analyze_reporting_impacts consumed build_1104_seed_catalog()
which only had 1 coarse G31 item, so every G31 change signal collapsed onto
G31.PART_I.BOND_INVESTMENT_BALANCE — producing duplicate impact rows.

After 方案 2: the analyzer reads from DB (load_catalog_from_db) which has the
5 detailed PART_I.1_0.* items. A 因持有非底层 signal should now land on the D
item with its real source-field set.
"""
from sqlmodel import Session

from app.core.database import engine
from app.services.reporting_catalog_loader import load_catalog_from_db
from app.services.reporting_change_extractor import signals_to_changes
from app.services.reporting_impact_analyzer import analyze_reporting_impacts

# Re-use the same idempotent bootstrap helper
from tests.test_reporting_catalog_loader import _bootstrap_g31


def test_indirect_holding_signal_routes_to_d_column_and_real_lineage():
    _bootstrap_g31()

    signals = [
        {
            "table_code": "G31",
            "indicator_hint": "因持有非底层资产而间接持有",
            "change_type": "INDICATOR_SCOPE_CHANGE",
            "evidence_text": "调整 G31 因持有非底层资产间接持有期末余额口径。",
            "confidence": 0.9,
        }
    ]

    with Session(engine) as session:
        catalog = load_catalog_from_db(session)

    changes = signals_to_changes(signals, catalog.reporting_items)
    assert len(changes) == 1
    assert changes[0].reporting_item_code == (
        "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额"
    ), "信号必须命中 D 列而不是粗粒度 BOND_INVESTMENT_BALANCE"

    impacts = analyze_reporting_impacts(changes, catalog)
    assert len(impacts) == 1
    impact = impacts[0]
    assert impact.reporting_item_code.endswith("D_因持有非底层资产而间接持有_期末余额")
    assert impact.impacted_reporting_field == "rpt_g31_part_i.indirect_holding_balance"
    # D 列真实源字段
    assert "dm_g31_lookthrough.indirect_balance" in impact.impacted_source_fields
    assert "ods_invest_position.product_id" in impact.impacted_source_fields
    assert "crms_counterparty.institution_type" in impact.impacted_source_fields
    # 各角色都有
    assert {"REPORT_FIELD", "SOURCE_FIELD", "DIMENSION_FIELD", "FILTER_FIELD"}.issubset(
        set(impact.impacted_lineage_roles)
    )


def test_distinct_g31_signals_produce_distinct_impacts_not_duplicates():
    """The original bug: 80 G31 signals collapsed to identical impact rows.
    Here we feed 3 distinct hints and assert they land on 3 different items."""
    _bootstrap_g31()

    signals = [
        {"table_code": "G31", "indicator_hint": "修正久期",
         "change_type": "INDICATOR_SCOPE_CHANGE", "evidence_text": "x", "confidence": 0.9},
        {"table_code": "G31", "indicator_hint": "因持有非底层",
         "change_type": "INDICATOR_SCOPE_CHANGE", "evidence_text": "x", "confidence": 0.9},
        {"table_code": "G31", "indicator_hint": "穿透后",
         "change_type": "INDICATOR_SCOPE_CHANGE", "evidence_text": "x", "confidence": 0.9},
    ]

    with Session(engine) as session:
        catalog = load_catalog_from_db(session)

    changes = signals_to_changes(signals, catalog.reporting_items)
    item_codes = {c.reporting_item_code for c in changes}
    assert len(item_codes) == 3, f"3 个不同信号必须落到 3 个 item，实际 {item_codes}"


def test_composite_semantic_signals_are_kept_as_impact_items():
    _bootstrap_g31()

    signals = [
        {
            "table_code": "G31",
            "indicator_hint": "优先股投资余额",
            "change_type": "DELETE",
            "evidence_text": "从 G31 移出：优先股不再计入债券投资余额。",
            "confidence": 0.82,
            "match_status": "COMPOSITE_SEMANTIC_MATCH",
            "matched_item_code": "",
            "composite_match": {
                "match_type": "COMPOSITE_SEMANTIC_MATCH",
                "pattern_code": "G31_CLASSIFICATION_MEASURE",
                "indicator_hint": "优先股投资余额",
                "measure_phrase": "投资余额",
                "condition_phrase": "优先股",
                "reporting_item_codes": ["G31.PART_I.1_0.A_穿透前_期末余额"],
                "measure_field_codes": [
                    "rpt_g31_part_i.pre_lookthrough_balance",
                    "dm_g31_position.position_balance",
                    "ods_invest_position.book_balance",
                ],
                "condition_field_codes": ["ods_invest_position.asset_type"],
                "measure_fields": [
                    {
                        "field_code": "rpt_g31_part_i.pre_lookthrough_balance",
                        "field_name": "G31 穿透前期末余额",
                        "field_role": "REPORT_MEASURE_FIELD",
                    },
                    {
                        "field_code": "dm_g31_position.position_balance",
                        "field_name": "投资持仓余额",
                        "field_role": "MEASURE_FIELD",
                    },
                    {
                        "field_code": "ods_invest_position.book_balance",
                        "field_name": "投资账面余额",
                        "field_role": "SOURCE_MEASURE_FIELD",
                    },
                ],
                "filter_conditions": [
                    {
                        "field_code": "ods_invest_position.asset_type",
                        "field_name": "投资资产类型",
                        "operator": "=",
                        "value_code": "PREFERRED_STOCK",
                        "value_name": "优先股",
                    }
                ],
                "confidence": 0.82,
                "review_status": "PENDING",
            },
        }
    ]

    with Session(engine) as session:
        catalog = load_catalog_from_db(session)

    changes = signals_to_changes(signals, catalog.reporting_items)
    assert len(changes) == 1
    assert changes[0].reporting_item_code == "G31.COMPOSITE.优先股投资余额"

    impacts = analyze_reporting_impacts(changes, catalog)
    assert len(impacts) == 1
    impact = impacts[0]
    assert impact.reporting_item_code == "G31.COMPOSITE.优先股投资余额"
    assert impact.reporting_item_code != "G31.PART_I.BOND_INVESTMENT_BALANCE"
    assert impact.impacted_reporting_field == "优先股投资余额"
    assert impact.impact_type == "COMPOSITE_SEMANTIC_SCOPE"
    assert "rpt_g31_part_i.pre_lookthrough_balance" in impact.impacted_source_fields
    assert "dm_g31_position.position_balance" in impact.impacted_source_fields
    assert "ods_invest_position.book_balance" in impact.impacted_source_fields
    assert "ods_invest_position.asset_type" in impact.impacted_source_fields
    assert {"REPORT_FIELD", "SOURCE_FIELD", "FILTER_FIELD"}.issubset(
        set(impact.impacted_lineage_roles)
    )
