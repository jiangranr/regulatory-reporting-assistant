"""zip 目录扫描：解压 zip 包并识别每张报表的 Excel + Doc 文件对。"""
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

_SKIP_DIRS = {"__MACOSX", "__pycache__", ".DS_Store"}


@dataclass
class ReportFileSet:
    object_code: str       # "G31"
    change_type: str       # "NEW" | "MODIFIED" | "INSTRUCTION_ONLY"
    table_category: str    # 顶层目录名
    excel_path: Path | None
    doc_path: Path | None
    version_label: str     # "251"


def detect_change_type(folder_name: str) -> str:
    """从顶层目录名关键词推断 change_type，不做全匹配。"""
    if "新增" in folder_name:
        return "NEW"
    if "修订" in folder_name:
        return "MODIFIED"
    if "填报说明" in folder_name:
        return "INSTRUCTION_ONLY"
    # 兜底：不含以上关键词的目录（如"分支机构报表"）归为 NEW
    return "NEW"


def extract_version_label(filename: str) -> str:
    """从文件名括号内提取版本号。'G31(251).xls' → '251'，'G31填报说明（251）.doc' → '251'"""
    match = re.search(r'[（(](\d+)[）)]', filename)
    return match.group(1) if match else ""


def extract_object_code(folder_name: str) -> str:
    """从报表子文件夹名提取报表代码。'G31'、'S73养老…' → 'G31'、'S73'"""
    match = re.match(r'^([A-Z]\d+(?:_[A-Z0-9]+)?)', folder_name.strip())
    return match.group(1) if match else folder_name.strip()


def scan_zip(zip_path: Path, extract_to: Path) -> tuple[str, list[ReportFileSet]]:
    """
    解压 zip 并扫描目录结构，返回 (version_label, 报表文件集列表)。

    期望目录结构：
      <category_folder>/         ← 顶层：含"新增"/"修订"等关键词
        <report_folder>/         ← 报表代码目录，如 G31/
          G31(251).xls
          G31填报说明（251）.doc
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    # metadata_encoding='utf-8'：处理 macOS zip 命令创建的 zip 包（不带 UTF-8 flag bit，
    # Python 默认按 CP437 解码导致中文乱码）。Python 3.11 支持此参数。
    with zipfile.ZipFile(zip_path, "r", metadata_encoding="utf-8") as zf:
        for member in zf.infolist():
            # 防止 zip slip：确保解压路径不逃逸出 extract_to
            member_path = (extract_to / member.filename).resolve()
            if not str(member_path).startswith(str(extract_to.resolve())):
                raise ValueError(f"不安全的 zip 条目: {member.filename}")
        zf.extractall(extract_to)

    file_sets: list[ReportFileSet] = []
    version_label = ""

    for category_dir in sorted(extract_to.iterdir()):
        if not category_dir.is_dir():
            continue
        if category_dir.name in _SKIP_DIRS:
            continue

        change_type = detect_change_type(category_dir.name)

        for report_dir in sorted(category_dir.iterdir()):
            if not report_dir.is_dir():
                continue

            object_code = extract_object_code(report_dir.name)
            excel_path: Path | None = None
            doc_path: Path | None = None

            for f in report_dir.iterdir():
                if not f.is_file():
                    continue
                suffix = f.suffix.lower()
                if suffix in (".xls", ".xlsx") and excel_path is None:
                    excel_path = f
                    if not version_label:
                        version_label = extract_version_label(f.name)
                elif suffix in (".doc", ".docx") and doc_path is None:
                    doc_path = f
                    if not version_label:
                        version_label = extract_version_label(f.name)

            if excel_path or doc_path:
                file_sets.append(ReportFileSet(
                    object_code=object_code,
                    change_type=change_type,
                    table_category=category_dir.name,
                    excel_path=excel_path,
                    doc_path=doc_path,
                    version_label=version_label,
                ))

    return version_label, file_sets
