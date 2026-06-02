import asyncio
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from sqlalchemy import func
from sqlmodel import SQLModel, Session, create_engine, select

from app.models.db_models import RegCatalogBatch, RegReportingInstruction
from app.services import catalog_ingestor
from app.models.db_models import (
    RegReportingItem,
    RegReportingItemDimension,
    RegReportingObject,
    RegReportingTemplate,
    RegReportingTemplateCell,
)
from app.services.catalog_ingestor import _write_excel_results, create_batch
from app.services.excel_parser import parse_excel


G01_IV_XLSX = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G01_IV/G01_IV（251）.xlsx")


@pytest.mark.skipif(not G01_IV_XLSX.exists(), reason="G01_IV file not available")
def test_write_excel_results_is_idempotent_for_same_template():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    parse_result = parse_excel(G01_IV_XLSX, object_code="G01_IV", section_code="PART_IV")

    with Session(engine) as session:
        reporting_object = RegReportingObject(
            reporting_system_id=1,
            reporting_version_id=1,
            object_code="G01_IV",
            object_name="G01_IV",
        )
        session.add(reporting_object)
        session.commit()
        session.refresh(reporting_object)

        first_count = _write_excel_results(
            session,
            parse_result=parse_result,
            object_id=reporting_object.id,
            batch_item_id=1,
            object_code="G01_IV",
            version_label="251",
            change_type="MODIFIED",
            section_code="PART_IV",
        )
        second_count = _write_excel_results(
            session,
            parse_result=parse_result,
            object_id=reporting_object.id,
            batch_item_id=2,
            object_code="G01_IV",
            version_label="251",
            change_type="MODIFIED",
            section_code="PART_IV",
        )

        template = session.exec(
            select(RegReportingTemplate).where(RegReportingTemplate.template_code == "G01_IV.PART_IV.251")
        ).one()
        cells_count = session.exec(
            select(func.count()).select_from(RegReportingTemplateCell).where(
                RegReportingTemplateCell.template_id == template.id
            )
        ).one()
        items_count = session.exec(
            select(func.count()).select_from(RegReportingItem).where(
                RegReportingItem.reporting_object_id == reporting_object.id
            )
        ).one()
        dimensions_count = session.exec(
            select(func.count()).select_from(RegReportingItemDimension)
        ).one()

    assert first_count == 34
    assert second_count == 0
    assert cells_count == 125
    assert items_count == 34
    assert dimensions_count == 68


@pytest.mark.skipif(not G01_IV_XLSX.exists(), reason="G01_IV file not available")
def test_process_catalog_zip_without_doc_does_not_write_instruction(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(catalog_ingestor, "engine", engine)

    zip_path = tmp_path / "G01_IV_excel_only.zip"
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.write(
            G01_IV_XLSX,
            arcname="2.修订报表（基础类、业务类、支持发展类）/G01_IV/G01_IV（251）.xlsx",
        )

    with Session(engine) as session:
        batch = create_batch(session, zip_filename=zip_path.name, source_doc_ref=str(G01_IV_XLSX))
        batch_id = batch.id

    asyncio.run(
        catalog_ingestor.process_catalog_zip(
            batch_id=batch_id,
            zip_path=zip_path,
            extract_to=tmp_path / "extracted",
            object_codes=["G01_IV"],
        )
    )

    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        instructions_count = session.exec(
            select(func.count()).select_from(RegReportingInstruction)
        ).one()

    assert batch.status == "DONE"
    assert instructions_count == 0
