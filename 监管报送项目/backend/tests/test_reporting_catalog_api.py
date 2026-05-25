from fastapi.testclient import TestClient

from app.main import app


def test_seed_and_query_1104_funds_interbank_reporting_catalog():
    client = TestClient(app)

    seed_response = client.post("/api/reporting/seed-1104")
    assert seed_response.status_code == 200
    assert seed_response.json()["reporting_objects"] >= 5
    assert seed_response.json()["reporting_items"] >= 6

    items_response = client.get("/api/reporting/items?reporting_system_code=1104")
    assert items_response.status_code == 200
    item_codes = {item["item_code"] for item in items_response.json()}
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in item_codes
    assert "G31.PART_I.BOND_INVESTMENT_BALANCE" in item_codes

    lineage_response = client.get(
        "/api/reporting/items/G24.MAIN.INTERBANK_BORROWING_BAL_TOP100/lineage"
    )
    assert lineage_response.status_code == 200
    field_codes = {item["field_code"] for item in lineage_response.json()["fields"]}
    assert "interbank_deal.balance" in field_codes
    assert "interbank_deal.counterparty_fin_org_code" in field_codes
