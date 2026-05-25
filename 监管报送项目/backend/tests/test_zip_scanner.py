import io
import zipfile
from pathlib import Path

import pytest

from app.services.zip_scanner import (
    detect_change_type,
    extract_object_code,
    extract_version_label,
    scan_zip,
)


def test_detect_change_type_new():
    assert detect_change_type("1.新增报表（基础类、业务类、支持发展类）") == "NEW"


def test_detect_change_type_modified():
    assert detect_change_type("2.修订报表（基础类、业务类、支持发展类）") == "MODIFIED"


def test_detect_change_type_instruction_only():
    assert detect_change_type("5.填报说明及其他调整") == "INSTRUCTION_ONLY"


def test_detect_change_type_default():
    assert detect_change_type("6.分支机构报表") == "NEW"


def test_extract_version_label():
    assert extract_version_label("G31(251).xls") == "251"
    assert extract_version_label("G31填报说明（251）.doc") == "251"
    assert extract_version_label("G31.xls") == ""


def test_extract_object_code():
    assert extract_object_code("G31") == "G31"
    assert extract_object_code("G01_IV") == "G01_IV"
    assert extract_object_code("G11_I") == "G11_I"
    assert extract_object_code("S73养老领域相关情况统计表") == "S73"


def test_scan_zip(tmp_path: Path):
    # 构造测试 zip
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls", b"fake_xls")
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc", b"fake_doc")
        zf.writestr("1.新增报表（基础类、业务类、支持发展类）/G51境外业务/G51(251).xlsx", b"fake_xlsx")

    extract_to = tmp_path / "extracted"
    version_label, file_sets = scan_zip(zip_path, extract_to)

    assert version_label == "251"
    assert len(file_sets) == 2

    g31 = next(fs for fs in file_sets if fs.object_code == "G31")
    assert g31.change_type == "MODIFIED"
    assert g31.excel_path is not None
    assert g31.doc_path is not None

    g51 = next(fs for fs in file_sets if fs.object_code == "G51")
    assert g51.change_type == "NEW"
    assert g51.excel_path is not None
    assert g51.doc_path is None


def test_scan_zip_skips_macosx(tmp_path: Path):
    """macOS 压缩包常含 __MACOSX 目录，应被跳过。"""
    zip_path = tmp_path / "macos.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("2.修订报表（基础类、业务类、支持发展类）/G31/G31(251).xls", b"fake")
        zf.writestr("__MACOSX/._G31(251).xls", b"macos_meta")

    extract_to = tmp_path / "extracted2"
    version_label, file_sets = scan_zip(zip_path, extract_to)

    object_codes = [fs.object_code for fs in file_sets]
    assert "G31" in object_codes
    assert "__MACOSX" not in object_codes
    assert len(file_sets) == 1


def test_scan_zip_empty(tmp_path: Path):
    """空 zip 应返回空列表和空版本号。"""
    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        pass  # 空 zip

    extract_to = tmp_path / "extracted3"
    version_label, file_sets = scan_zip(zip_path, extract_to)
    assert version_label == ""
    assert file_sets == []
