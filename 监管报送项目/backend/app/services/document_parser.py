from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import re
import xml.etree.ElementTree as ET

from app.models.schemas import ParsedDocument


def parse_text_document(filename: str, content: bytes) -> ParsedDocument:
    suffix = Path(filename).suffix.lower()
    parser = _parser_name(suffix)
    try:
        if suffix == ".docx":
            text = _parse_docx(content)
        elif suffix == ".pdf":
            text = _parse_pdf(content)
        else:
            text = _decode_text(content)
    except Exception as exc:
        return _failed(filename, parser, str(exc))

    text = _normalize_text(text)
    if not text:
        return _failed(filename, parser, "未解析到有效正文")

    paragraphs = _paragraphs(text)
    table_count = text.count("\t")
    quality = "GOOD" if len(text) >= 20 else "LOW"
    return ParsedDocument(
        filename=filename,
        text=text,
        excerpt=text[:160],
        parser=parser,
        char_count=len(text),
        paragraph_count=len(paragraphs),
        table_count=table_count,
        quality=quality,
        error_message="",
    )


def _parser_name(suffix: str) -> str:
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf_text"
    return "text"


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="ignore")


def _parse_docx(content: bytes) -> str:
    try:
        with ZipFile(BytesIO(content)) as archive:
            xml_content = archive.read("word/document.xml")
    except (KeyError, BadZipFile) as exc:
        raise ValueError("无法读取 DOCX 正文") from exc

    root = ET.fromstring(xml_content)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        paragraph_text = "".join(texts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)
    return "\n\n".join(paragraphs)


def _parse_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("当前环境缺少 PDF 文本解析组件 pypdf") from exc

    reader = PdfReader(BytesIO(content))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _paragraphs(text: str) -> list[str]:
    return [paragraph for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]


def _failed(filename: str, parser: str, message: str) -> ParsedDocument:
    return ParsedDocument(
        filename=filename,
        text="",
        excerpt="",
        parser=parser,
        char_count=0,
        paragraph_count=0,
        table_count=0,
        quality="FAILED",
        error_message=message,
    )
