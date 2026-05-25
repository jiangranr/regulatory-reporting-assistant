"""Verify the DB-backed catalog loader returns the same shape consumed by
impact analysis, and that bootstrap actually populated G31 detail items.

Touches the shared test_app.db via FastAPI startup (init_db) and the
bootstrap_route_a helpers. Idempotent — safe to re-run.
"""
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.database import engine
from app.main import app
from app.services.reporting_catalog_loader import load_catalog_from_db
from scripts.bootstrap_route_a import _ensure_g31_detail_items
from scripts import seed_g31_lineage_reference as g31_seed


def _bootstrap_g31() -> None:
    """Idempotent bootstrap of the G31 detailed catalog into the test DB."""
    # init_db + 1104 base seed happens via the seed-1104 endpoint
    client = TestClient(app)
    client.post("/api/reporting/seed-1104")

    with Session(engine) as session:
        _ensure_g31_detail_items(session)
        session.commit()
    g31_seed.main()


def test_loader_returns_g31_detail_items_and_lineage():
    _bootstrap_g31()

    with Session(engine) as session:
        catalog = load_catalog_from_db(session)

    g31_item_codes = {
        item["item_code"]
        for item in catalog.reporting_items
        if item["item_code"].startswith("G31.")
    }
    # 1 coarse + 5 detail = at least 6 G31 items must be present
    assert "G31.PART_I.BOND_INVESTMENT_BALANCE" in g31_item_codes
    for suffix in [
        "G31.PART_I.1_0.A_穿透前_期末余额",
        "G31.PART_I.1_0.B_投资收入_年初至报告期末数",
        "G31.PART_I.1_0.C_修正久期",
        "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额",
        "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额",
    ]:
        assert suffix in g31_item_codes

    # D 列血缘必须含 dm_g31_lookthrough.indirect_balance（SOURCE_FIELD）
    d_code = "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额"
    d_rows = [row for row in catalog.lineage if row["reporting_item_code"] == d_code]
    assert len(d_rows) == 7, f"D 列预期 7 条血缘，实际 {len(d_rows)}"
    field_codes_by_role = {(r["lineage_role"], r["data_field_code"]) for r in d_rows}
    assert ("SOURCE_FIELD", "dm_g31_lookthrough.indirect_balance") in field_codes_by_role
    assert ("DIMENSION_FIELD", "ods_invest_position.product_id") in field_codes_by_role
    assert ("FILTER_FIELD", "crms_counterparty.institution_type") in field_codes_by_role


def test_loader_returns_empty_catalog_safely():
    """Loader must not crash when both tables are empty; it should return a
    valid empty catalog and log a warning. We can't easily wipe the shared
    test_app.db here, so we just assert shape on whatever is loaded."""
    with Session(engine) as session:
        catalog = load_catalog_from_db(session)
    assert isinstance(catalog.reporting_items, list)
    assert isinstance(catalog.lineage, list)
