from sqlmodel import Session, SQLModel, create_engine, select

from app.models.db_models import RegReportingItem, ReportingItemLineage
from scripts import seed_g01_iv_lineage_reference as g01_seed


def _seed_target_items(session: Session) -> None:
    for item_code in [
        "G01_IV.PART_IV.11_1通过互联网吸收的个人定期存款.B_其中_储蓄存款",
        "G01_IV.PART_IV.11_2通过互联网吸收的个人活期存款.B_其中_储蓄存款",
        "G01_IV.PART_IV.11_a_1通过第三方互联网平台吸收的个人定期存款.B_其中_储蓄存款",
        "G01_IV.PART_IV.11_a_2通过第三方互联网平台吸收的个人活期存款.B_其中_储蓄存款",
    ]:
        session.add(
            RegReportingItem(
                reporting_object_id=1,
                item_code=item_code,
                item_name=item_code,
                item_type="MEASURE",
            )
        )
    session.commit()


def test_seed_g01_iv_reference_lineage_is_idempotent_and_covers_four_focus_items():
    memory_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(memory_engine)

    with Session(memory_engine) as session:
        _seed_target_items(session)
        systems = g01_seed.upsert_systems(session)
        fields = g01_seed.upsert_fields(session, systems)

        inserted, existing, missing = g01_seed.upsert_lineage(session, fields)
        session.commit()
        inserted_again, existing_again, missing_again = g01_seed.upsert_lineage(session, fields)
        session.commit()

        rows = session.exec(select(ReportingItemLineage)).all()
        internet_time_deposit = g01_seed.FOCUS_ITEM_CODES["INTERNET_TIME_DEPOSIT"][0]
        item_id = next(
            item.id
            for item in session.exec(select(RegReportingItem)).all()
            if item.item_code == internet_time_deposit
        )
        item_rows = [row for row in rows if row.reporting_item_id == item_id]

        assert missing == 0
        assert missing_again == 0
        assert inserted == len(g01_seed.LINEAGE)
        assert existing == 0
        assert inserted_again == 0
        assert existing_again == len(g01_seed.LINEAGE)
        assert len(rows) == len(g01_seed.LINEAGE)
        assert {row.mapping_status for row in rows} == {"SEED_CONFIRMED"}

    assert {row.lineage_role for row in item_rows} >= {
        "REPORT_FIELD",
        "SOURCE_FIELD",
        "DIMENSION_FIELD",
        "FILTER_FIELD",
    }


def test_seed_g01_iv_reference_lineage_supports_the_current_251_demand_deposit_row_code():
    memory_engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(memory_engine)
    imported_251_code = g01_seed.FOCUS_ITEM_CODES["THIRD_PARTY_INTERNET_DEMAND_DEPOSIT"][1]

    with Session(memory_engine) as session:
        session.add(
            RegReportingItem(
                reporting_object_id=1,
                item_code=imported_251_code,
                item_name=imported_251_code,
                item_type="MEASURE",
            )
        )
        session.commit()
        systems = g01_seed.upsert_systems(session)
        fields = g01_seed.upsert_fields(session, systems)
        g01_seed.upsert_lineage(session, fields)
        session.commit()

        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == imported_251_code)
        ).one()
        rows = session.exec(
            select(ReportingItemLineage).where(ReportingItemLineage.reporting_item_id == item.id)
        ).all()

    assert len(rows) == 8
