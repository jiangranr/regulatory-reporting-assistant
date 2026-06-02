from app.models.enums import ActionTicketType, ChangeTicketType, SeverityLevel
from app.services.change_severity_classifier import ChangeClassification, SeverityScore
from app.services.reporting_change_extractor import extract_reporting_changes, signals_to_changes
from app.services.reporting_impact_analyzer import analyze_reporting_impacts
from app.services.reporting_seed import build_1104_seed_catalog
from app.services.reporting_ticket_generator import build_ticket_plan


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


def test_unverified_llm_signal_is_excluded_from_downstream_changes():
    catalog = build_1104_seed_catalog()
    signal = {
        "table_code": "G31",
        "indicator_hint": "绿色债券投资余额",
        "change_type": "ADD",
        "evidence_text": "本期新增绿色债券投资余额字段。",
        "confidence": 0.3,
        "source_type": "LLM",
        "grounding_status": "UNVERIFIED",
        "human_review_status": "PENDING",
    }

    changes = signals_to_changes([signal], catalog.reporting_items)

    assert len(changes) == 1
    assert changes[0].reporting_object_code == ""
    assert changes[0].change_type == "MANUAL_REVIEW"


def test_unresolved_instruction_signal_does_not_fallback_to_structural_catalog_item():
    signal = {
        "table_code": "G31",
        "indicator_hint": "填报机构范围",
        "change_type": "SCOPE_ADJUST",
        "evidence_text": "3. 填报机构：新增直销银行。",
        "confidence": 0.86,
        "matched_item_code": "",
        "match_status": "",
    }
    catalog_items = [
        {
            "item_code": "G31.PART_I.1_0.COL_1",
            "item_name": "1.0-COL_1",
            "row_label": "1.0",
            "column_label": "COL_1",
        },
        {
            "item_code": "G31.PART_I.1_0.C_修正久期",
            "item_name": "1 行·C 列 · 修正久期",
            "row_label": "1.债券投资合计",
            "column_label": "C·修正久期",
        },
    ]

    changes = signals_to_changes([signal], catalog_items)

    assert changes[0].reporting_item_code == ""


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


def test_build_ticket_plan_outputs_structured_ticket_cards():
    catalog = build_1104_seed_catalog()
    changes = extract_reporting_changes(
        "调整G24同业融入余额统计口径，并同步调整内部数据加工逻辑与跨表一致性校验。"
    )
    impacts = analyze_reporting_impacts(changes, catalog)
    classification = ChangeClassification(
        change_ticket_type=ChangeTicketType.SCOPE_ADJUSTMENT,
        severity=SeverityScore(
            level=SeverityLevel.L3_STANDARD,
            score=8,
            triggered_signals=["test"],
        ),
    )

    plan = build_ticket_plan(
        classification,
        impacts,
        "G24 口径调整",
        document_text="同步调整内部数据加工逻辑与跨表一致性校验",
    )

    assert plan.children
    assert any(
        child.card.responsible_system == "DATA_GOVERNANCE_PLATFORM"
        for child in plan.children
        if child.card
    )
    assert all(child.card and child.card.summary for child in plan.children)
    assert all(child.card and child.card.must_do for child in plan.children)
    assert all(
        child.quality and child.quality.score > 0 for child in plan.children
    )


def test_manual_review_without_impacts_uses_matrix_fallback_scope_confirm():
    classification = ChangeClassification(
        change_ticket_type=ChangeTicketType.MANUAL_REVIEW,
        severity=SeverityScore(
            level=SeverityLevel.L2_LIGHT,
            score=3,
            triggered_signals=["low confidence"],
        ),
    )

    plan = build_ticket_plan(
        classification,
        [],
        "人工复核任务",
        document_text="",
    )

    assert [child.action_type for child in plan.children] == [
        ActionTicketType.SCOPE_CONFIRM
    ]
    assert plan.children[0].card is None
    assert plan.children[0].quality is None
    assert "责任分配" in plan.children[0].content_markdown


def test_ticket_cards_include_asset_names_and_readable_evidence_text():
    catalog = build_1104_seed_catalog()
    changes = extract_reporting_changes(
        "监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径。"
    )
    impacts = analyze_reporting_impacts(changes, catalog)
    classification = ChangeClassification(
        change_ticket_type=ChangeTicketType.SCOPE_ADJUSTMENT,
        severity=SeverityScore(
            level=SeverityLevel.L3_STANDARD,
            score=8,
            triggered_signals=["test"],
        ),
    )

    plan = build_ticket_plan(
        classification,
        impacts,
        "G24 口径调整",
        document_text="调整同业融入余额统计口径。",
    )

    cards = [child.card for child in plan.children if child.card]
    assert cards
    first_card = cards[0]
    assert first_card.affected_assets["reporting_items"][0] == {
        "code": "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
        "name": "最大百家金融机构同业融入余额",
    }
    assert first_card.affected_assets["reporting_fields"][0] == {
        "code": "rpt_g24.interbank_borrowing_bal_top100",
        "name": "G24 最大百家金融机构同业融入余额",
    }
    assert {
        "code": "interbank_deal.balance",
        "name": "同业交易余额",
        "role": "SOURCE_FIELD",
    } in first_card.affected_assets["source_fields"]
    assert all(ref.get("src") and ref.get("text") for ref in first_card.evidence_refs)
    assert any("需要复核报送字段" in ref["text"] for ref in first_card.evidence_refs)
    assert not any(ref["text"] == "REPORTING_ITEM_SCOPE_CHANGE" for ref in first_card.evidence_refs)
