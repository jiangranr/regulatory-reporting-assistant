import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog_ingestor import _section_code_for_object_code


def _make_test_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls", b"fake_xls")
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc", b"fake_doc")
        zf.writestr("1.新增报表（基础类、业务类、支持发展类）/G51境外业务/G51(251).xlsx", b"fake_xlsx")
    return buf.getvalue()


def test_upload_zip_returns_batch_id():
    client = TestClient(app)
    zip_bytes = _make_test_zip()
    response = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("test_catalog.zip", zip_bytes, "application/zip")},
        data={"source_document_ref": "测试文件"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "batch_id" in data
    assert data["version_label"] == "251"
    assert data["total_count"] == 2


def test_get_batch_detail():
    client = TestClient(app)
    zip_bytes = _make_test_zip()
    upload_resp = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("test_catalog.zip", zip_bytes, "application/zip")},
    )
    assert upload_resp.status_code == 201
    batch_id = upload_resp.json()["batch_id"]

    detail_resp = client.get(f"/api/catalog/batches/{batch_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == batch_id
    assert "items" in data


def test_list_batches():
    client = TestClient(app)
    response = client.get("/api/catalog/batches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_upload_non_zip_returns_400():
    client = TestClient(app)
    response = client.post(
        "/api/catalog/upload-zip",
        files={"file": ("readme.txt", b"not a zip", "text/plain")},
    )
    assert response.status_code == 400


def test_section_code_for_suffixed_reporting_object():
    assert _section_code_for_object_code("G01_IV") == "PART_IV"
    assert _section_code_for_object_code("G31") == "PART_I"
