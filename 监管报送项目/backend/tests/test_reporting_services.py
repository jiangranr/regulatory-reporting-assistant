from app.services.reporting_change_extractor import extract_reporting_changes, signals_to_changes
from app.services.reporting_impact_analyzer import analyze_reporting_impacts
from app.services.reporting_seed import build_1104_seed_catalog


def test_1104_seed_contains_funds_interbank_reporting_items_and_lineage():
    catalog = build_1104_seed_catalog()

    object_codes = {item["object_code"] for item in catalog.reporting_objects}
    item_codes = {item["item_code"] for item in catalog.reporting_items}
    field_codes = {field["field_code"] for field in catalog.data_fields}
    lineage_roles = {
        (lineage["reporting_item_code"], lineage["data_field_code"], lineage["lineage_role"])
        for lineage in catalog.lineage
    }

    assert {"G21", "G24", "G25", "G27", "G31"}.issubset(object_codes)
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in item_codes
    assert "rpt_g24.interbank_borrowing_bal_top100" in field_codes
    assert (
        "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        "interbank_deal.counterparty_fin_org_code",
        "DIMENSION_FIELD",
    ) in lineage_roles
    assert (
        "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        "interbank_deal.balance",
        "SOURCE_FIELD",
    ) in lineage_roles


def test_extract_reporting_changes_identifies_g24_interbank_change():
    text = "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径。"

    changes = extract_reporting_changes(text)

    assert changes
    assert changes[0].reporting_system_code == "1104"
    assert changes[0].reporting_object_code == "G24"
    assert changes[0].reporting_item_code == "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100"
    assert changes[0].change_type == "INDICATOR_SCOPE_CHANGE"


def test_unmatched_revision_signal_does_not_fallback_to_unrelated_g31_item():
    catalog = build_1104_seed_catalog()
    signal = {
        "table_code": "G31",
        "indicator_hint": "优先股投资余额",
        "change_type": "DELETE",
        "evidence_text": "从 G31 移出：优先股不再计入债券投资余额",
        "confidence": 0.55,
        "matched_item_code": "",
        "match_status": "UNMATCHED_DELETED",
    }

    changes = signals_to_changes([signal], catalog.reporting_items)

    assert changes[0].reporting_object_code == "G31"
    assert changes[0].reporting_item_code == ""
    assert changes[0].change_type == "INDICATOR_REMOVE"


def test_composite_revision_signal_does_not_become_pseudo_exact_item_match():
    catalog = build_1104_seed_catalog()
    signal = {
        "table_code": "G31",
        "indicator_hint": "优先股投资余额",
        "change_type": "DELETE",
        "evidence_text": "从 G31 移出：优先股不再计入债券投资余额",
        "confidence": 0.86,
        "matched_item_code": "",
        "match_status": "COMPOSITE_SEMANTIC_MATCH",
        "composite_match": {
            "match_type": "COMPOSITE_SEMANTIC_MATCH",
            "condition_phrase": "优先股",
            "measure_phrase": "投资余额",
        },
    }

    changes = signals_to_changes([signal], catalog.reporting_items)

    assert changes[0].reporting_object_code == "G31"
    assert changes[0].reporting_item_code == "G31.COMPOSITE.优先股投资余额"
    assert changes[0].reporting_item_code != "G31.PART_I.BOND_INVESTMENT_BALANCE"
    assert changes[0].change_type == "INDICATOR_REMOVE"


def test_analyze_reporting_impacts_uses_interbank_lineage_fields():
    catalog = build_1104_seed_catalog()
    changes = extract_reporting_changes("调整G24同业融入余额统计口径。")

    impacts = analyze_reporting_impacts(changes, catalog)

    assert impacts
    impact = impacts[0]
    assert impact.reporting_item_code == "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100"
    assert impact.impact_type == "INDICATOR_SCOPE"
    assert impact.impacted_reporting_field == "rpt_g24.interbank_borrowing_bal_top100"
    assert "interbank_deal.balance" in impact.impacted_source_fields
    assert "interbank_deal.counterparty_fin_org_code" in impact.impacted_source_fields


def test_scope_change_outputs_ticket_scope_and_required_subtickets():
    catalog = build_1104_seed_catalog()
    changes = extract_reporting_changes("调整G24同业融入余额统计口径。")

    impacts = analyze_reporting_impacts(changes, catalog)

    impact = impacts[0]
    assert impact.ticket_parent_type == "SCOPE_RANGE_ADJUSTMENT"
    assert impact.required_sub_ticket_types == [
        "SCOPE_CONFIRMATION",
        "REPORTING_PROCESSING",
        "TEST_ACCEPTANCE",
        "ARCHIVE_REVIEW",
    ]
    assert "DATA_MAPPING" in impact.conditional_sub_ticket_types
    assert impact.sub_ticket_triggers["DATA_MAPPING"] == "NEW_DIMENSION_OR_FILTER_FIELD"
