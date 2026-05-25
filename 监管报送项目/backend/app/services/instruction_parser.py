import io
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
import re
import shutil
import subprocess
import tempfile

from app.models.schemas import ParsedDocument
from app.services.document_parser import parse_text_document

_WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = f"{{{_WNS}}}"


@dataclass(frozen=True)
class HighlightFragment:
    text: str
    color: str


@dataclass(frozen=True)
class CommentFragment:
    """Word 文档批注（旁注）"""
    author: str
    date: str
    text: str


@dataclass(frozen=True)
class RevisionFragment:
    """Word 文档修订追踪（插入/删除）"""
    change_type: str  # "INSERT" | "DELETE"
    author: str
    date: str
    text: str


@dataclass(frozen=True)
class InstructionParseResult:
    text: str
    html: str
    highlights: list[HighlightFragment]
    comments: list[CommentFragment]
    revisions: list[RevisionFragment]
    parser: str
    error_message: str = ""


def parse_instruction_file(filename: str, content: bytes) -> InstructionParseResult:
    suffix = Path(filename).suffix.lower()
    if suffix in {".doc", ".docx"}:
        # 对 .doc 文件先转换为 .docx 再提取批注；.docx 直接提取
        docx_content = content if suffix == ".docx" else _convert_doc_to_docx(filename, content)
        comments = _extract_docx_comments(docx_content) if docx_content else []
        revisions = _extract_docx_revisions(docx_content) if docx_content else []

        html = _convert_word_to_html(filename, content)
        if html:
            parsed_html = _parse_html(html)
            return InstructionParseResult(
                text=parsed_html.text,
                html=html,
                highlights=parsed_html.highlights,
                comments=comments,
                revisions=revisions,
                parser=f"{suffix[1:]}_html",
            )

    parsed = parse_text_document(filename, content)
    return InstructionParseResult(
        text=parsed.text,
        html="",
        highlights=[],
        comments=[],
        revisions=[],
        parser=parsed.parser,
        error_message=parsed.error_message,
    )


def build_pair_document_text(
    template_filename: str,
    instruction_filename: str,
    instruction: InstructionParseResult,
) -> str:
    sections = [
        "# 报表表样与填报说明联合导入",
        "",
        f"报表文件：{template_filename}",
        f"填报说明：{instruction_filename}",
        "",
    ]

    # 批注（人工批注最能体现版本变更讨论）
    if instruction.comments:
        sections.append(f"## 文档批注（共 {len(instruction.comments)} 条）")
        for i, c in enumerate(instruction.comments[:60], 1):
            sections.append(f"{i}. [{c.author} | {c.date[:10] if c.date else ''}] {c.text}")
    else:
        sections.append("## 文档批注\n- 未识别到批注。")

    sections.append("")

    # 修订追踪
    if instruction.revisions:
        sections.append(f"## 修订追踪（共 {len(instruction.revisions)} 条）")
        for rev in instruction.revisions[:60]:
            label = "新增" if rev.change_type == "INSERT" else "删除"
            sections.append(f"- [{label} | {rev.author} | {rev.date[:10] if rev.date else ''}] {rev.text}")
    else:
        sections.append("## 修订追踪\n- 未识别到修订追踪。")

    sections.append("")

    # 彩色高亮重点
    sections.append("## 非黑色重点片段")
    if instruction.highlights:
        sections.extend(
            f"- [{fragment.color}] {fragment.text}" for fragment in instruction.highlights[:80]
        )
    else:
        sections.append("- 未识别到非黑色重点片段。")

    sections.extend(["", "## 填报说明正文", instruction.text])

    if instruction.html:
        sections.extend(["", "## 填报说明 HTML", instruction.html[:20000]])

    return "\n".join(sections).strip()


def parsed_document_from_pair(
    template_filename: str,
    instruction_filename: str,
    instruction: InstructionParseResult,
) -> ParsedDocument:
    text = build_pair_document_text(template_filename, instruction_filename, instruction)
    paragraphs = [item for item in re.split(r"\n\s*\n", text) if item.strip()]
    table_count = text.count("<table") + text.count("\t")
    quality = "GOOD" if instruction.text else "FAILED"
    error = instruction.error_message if not instruction.text else ""
    return ParsedDocument(
        filename=f"{Path(template_filename).stem}+{Path(instruction_filename).stem}",
        text=text if instruction.text else "",
        excerpt=text[:160] if instruction.text else "",
        parser=f"template_plus_{instruction.parser}",
        char_count=len(text) if instruction.text else 0,
        paragraph_count=len(paragraphs) if instruction.text else 0,
        table_count=table_count,
        quality=quality,
        error_message=error or ("未解析到填报说明正文" if not instruction.text else ""),
    )


def _convert_doc_to_docx(filename: str, content: bytes) -> bytes:
    """将 .doc 文件转换为 .docx 字节，用于批注提取。失败返回空 bytes。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return b""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "source.doc"
        tmp_path.write_bytes(content)
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "docx", "--outdir", tmp_dir, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return b""
        out = Path(tmp_dir) / "source.docx"
        return out.read_bytes() if out.exists() else b""


def _extract_docx_comments(docx_content: bytes) -> list[CommentFragment]:
    """从 .docx 字节流中提取所有批注（word/comments.xml）。"""
    if not docx_content:
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(docx_content)) as zf:
            if "word/comments.xml" not in zf.namelist():
                return []
            root = ET.fromstring(zf.read("word/comments.xml"))
    except Exception:
        return []

    comments: list[CommentFragment] = []
    for el in root.findall(f".//{_W}comment"):
        author = el.get(f"{_W}author", "")
        date = el.get(f"{_W}date", "")
        parts = [t.text for t in el.iter(f"{_W}t") if t.text]
        text = "".join(parts).strip()
        if text:
            comments.append(CommentFragment(author=author, date=date, text=text))
    return comments


def _extract_docx_revisions(docx_content: bytes) -> list[RevisionFragment]:
    """从 .docx 字节流中提取插入/删除修订追踪（word/document.xml）。"""
    if not docx_content:
        return []
    try:
        with zipfile.ZipFile(io.BytesIO(docx_content)) as zf:
            if "word/document.xml" not in zf.namelist():
                return []
            root = ET.fromstring(zf.read("word/document.xml"))
    except Exception:
        return []

    revisions: list[RevisionFragment] = []
    for ins_el in root.findall(f".//{_W}ins"):
        author = ins_el.get(f"{_W}author", "")
        date = ins_el.get(f"{_W}date", "")
        parts = [t.text for t in ins_el.iter(f"{_W}t") if t.text]
        text = "".join(parts).strip()
        if text:
            revisions.append(RevisionFragment("INSERT", author, date, text))
    for del_el in root.findall(f".//{_W}del"):
        author = del_el.get(f"{_W}author", "")
        date = del_el.get(f"{_W}date", "")
        parts = [t.text for t in del_el.iter(f"{_W}delText") if t.text]
        text = "".join(parts).strip()
        if text:
            revisions.append(RevisionFragment("DELETE", author, date, text))
    return revisions


def _convert_word_to_html(filename: str, content: bytes) -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return ""

    suffix = Path(filename).suffix.lower() or ".doc"
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"source{suffix}"
        tmp_path.write_bytes(content)
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "html",
                    "--outdir",
                    tmp_dir,
                    str(tmp_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError):
            return ""

        html_files = sorted(Path(tmp_dir).glob("*.html")) + sorted(Path(tmp_dir).glob("*.htm"))
        if not html_files:
            return ""
        return html_files[0].read_text(encoding="utf-8", errors="ignore")


@dataclass(frozen=True)
class _ParsedHtml:
    text: str
    highlights: list[HighlightFragment]


class _InstructionHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.highlights: list[HighlightFragment] = []
        self._color_stack: list[str | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name.lower(): value or "" for name, value in attrs}
        color = _extract_color(tag.lower(), attr)
        current = color if color is not None else (self._color_stack[-1] if self._color_stack else None)
        self._color_stack.append(current)
        if tag.lower() in {"p", "div", "tr", "br", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")
        if tag.lower() in {"td", "th"}:
            self.text_parts.append("\t")

    def handle_endtag(self, tag: str) -> None:
        if self._color_stack:
            self._color_stack.pop()
        if tag.lower() in {"p", "div", "tr", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        clean = re.sub(r"\s+", " ", data).strip()
        if not clean:
            return
        self.text_parts.append(clean)
        self.text_parts.append(" ")
        color = self._color_stack[-1] if self._color_stack else None
        if color and _is_attention_color(color):
            self.highlights.append(HighlightFragment(text=clean, color=color))


def _parse_html(html: str) -> _ParsedHtml:
    parser = _InstructionHtmlParser()
    parser.feed(html)
    text = "".join(parser.text_parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return _ParsedHtml(text=text, highlights=_dedupe_highlights(parser.highlights))


def _extract_color(tag: str, attrs: dict[str, str]) -> str | None:
    if tag == "font" and attrs.get("color"):
        return attrs["color"].strip()
    style = attrs.get("style", "")
    match = re.search(r"(?:^|;)\s*color\s*:\s*([^;]+)", style, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _is_attention_color(color: str) -> bool:
    normalized = color.strip().lower().replace(" ", "")
    if normalized in {"", "black", "#000", "#000000", "rgb(0,0,0)", "windowtext", "auto"}:
        return False
    if normalized in {"#fff", "#ffffff", "white", "transparent"}:
        return False
    return True


def _dedupe_highlights(highlights: list[HighlightFragment]) -> list[HighlightFragment]:
    seen: set[tuple[str, str]] = set()
    result: list[HighlightFragment] = []
    for item in highlights:
        key = (item.text, item.color)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
