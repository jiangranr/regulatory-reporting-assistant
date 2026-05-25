from types import SimpleNamespace

from app.services.reporting_item_scope import is_analysis_item, filter_analysis_items


def test_analysis_item_includes_fillable_and_derived_business_cells():
    fillable = SimpleNamespace(is_fillable=True, is_derived=False, status="ACTIVE")
    derived = SimpleNamespace(is_fillable=False, is_derived=True, status="ACTIVE")

    assert is_analysis_item(fillable) is True
    assert is_analysis_item(derived) is True


def test_analysis_item_excludes_structural_cells_and_inactive_items():
    structural = SimpleNamespace(is_fillable=False, is_derived=False, status="ACTIVE")
    inactive_fillable = SimpleNamespace(is_fillable=True, is_derived=False, status="INACTIVE")

    assert is_analysis_item(structural) is False
    assert is_analysis_item(inactive_fillable) is False


def test_filter_analysis_items_keeps_only_items_that_can_drive_impact_analysis():
    items = [
        SimpleNamespace(item_code="G31.STRUCT.DATE", is_fillable=False, is_derived=False, status="ACTIVE"),
        SimpleNamespace(item_code="G31.BIZ.FILLABLE", is_fillable=True, is_derived=False, status="ACTIVE"),
        SimpleNamespace(item_code="G31.BIZ.DERIVED", is_fillable=False, is_derived=True, status="ACTIVE"),
    ]

    assert [item.item_code for item in filter_analysis_items(items)] == [
        "G31.BIZ.FILLABLE",
        "G31.BIZ.DERIVED",
    ]
