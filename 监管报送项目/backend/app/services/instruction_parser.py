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


def current_version_revisions(revisions: list[RevisionFragment]) -> list[RevisionFragment]:
    """Return revisions from the latest revision year in the Word history.

    Legacy 1104 instructions often carry years of tracked changes. For a
    version review, only the latest dated revision wave should drive the
    "current version" change summary.
    """
    dated_years = [
        int(match.group(1))
        for revision in revisions
        if (match := re.match(r"^(\d{4})", revision.date or ""))
    ]
    if not dated_years:
        return revisions

    latest_year = max(dated_years)
    return [
        revision
        for revision in revisions
        if re.match(rf"^{latest_year}", revision.date or "")
    ]


def _revision_action_label(revision: RevisionFragment) -> str:
    return "新增" if revision.change_type == "INSERT" else "删除"


def _format_revision_action(revision: RevisionFragment) -> str:
    date = revision.date[:10] if revision.date else ""
    return f"[{_revision_action_label(revision)} | {revision.author} | {date}] {revision.text}"


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

    # 当前版本修订动作：保留操作、作者、日期，过滤掉历史版本遗留修订。
    current_revisions = current_version_revisions(instruction.revisions)
    if current_revisions:
        sections.append(
            f"## 当前版本修订动作（共 {len(current_revisions)} 条，"
            f"原始修订共 {len(instruction.revisions)} 条）"
        )
        for rev in current_revisions[:60]:
            sections.append(f"- {_format_revision_action(rev)}")
    else:
        sections.append("## 当前版本修订动作\n- 未识别到修订追踪。")

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


# ---------------------------------------------------------------------------
# 监管元数据抽取
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatoryMetadata:
    """监管文档头部元数据。供 Module D（工单执行规划）使用。"""

    document_no: str = ""
    issuing_authority: str = ""
    published_at: str = ""           # ISO YYYY-MM-DD
    effective_date: str = ""         # ISO YYYY-MM-DD
    first_report_period: str = ""    # 2026Q3 / 2026-09-30
    regulatory_intent: str = ""      # 政策目的段（≤300 字）
    status: str = "PENDING"          # PENDING / OK / PARTIAL / FAILED

    def to_dict(self) -> dict[str, str]:
        return {
            "document_no": self.document_no,
            "issuing_authority": self.issuing_authority,
            "published_at": self.published_at,
            "effective_date": self.effective_date,
            "first_report_period": self.first_report_period,
            "regulatory_intent": self.regulatory_intent,
            "metadata_extraction_status": self.status,
        }


_KNOWN_AUTHORITIES = [
    "国家金融监督管理总局",
    "中国银行保险监督管理委员会",
    "中国银保监会",
    "银保监会",
    "中国人民银行",
    "人民银行",
    "国家外汇管理局",
    "外汇局",
    "财政部",
    "国家税务总局",
    "中国证券监督管理委员会",
    "证监会",
]


_DOC_NO_PATTERNS = [
    # "国金监办〔2026〕14 号" / "银保监办发〔2026〕14 号"
    re.compile(r"[一-龥A-Za-z]{2,12}〔\d{4}〕第?\s*\d+\s*号"),
    # 纯文号 "〔2026〕第 15 号"
    re.compile(r"〔\d{4}〕第?\s*\d+\s*号"),
    # 公告/通知编号 "2026 年第 15 号"
    re.compile(r"\d{4}\s*年第\s*\d+\s*号"),
]


_EFFECTIVE_PATTERN = re.compile(
    r"自\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*起\s*(?:施行|执行|实施|生效)"
)

_PUBLISHED_PATTERN = re.compile(
    r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)

_REPORT_PERIOD_PATTERNS = [
    # "2026 年第三季度报表（数据日期 2026-09-30）按本公告口径首次报送"
    re.compile(
        r"(\d{4})\s*年\s*第\s*([一二三四1234])\s*季度报表[^。\n]{0,80}?首次报送"
    ),
    re.compile(
        r"(\d{4})\s*年\s*第\s*([一二三四1234])\s*季度.{0,40}?按本(?:公告|通知|办法)口径"
    ),
    # 月度："自 2026 年 1 月报送日起"
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(?:报送日|起报送)"),
]

_INTENT_PATTERN = re.compile(
    r"(为(?:了|深化|规范|加强|落实|进一步|更好|确保)[^。]{8,260}?)(?:[，,]\s*现就|[，,]\s*公告如下|[，,]\s*通知如下|[，,]\s*特公告|[，,]\s*特通知|。)",
    re.DOTALL,
)


_CN_QUARTER_MAP = {"一": "Q1", "二": "Q2", "三": "Q3", "四": "Q4",
                   "1": "Q1", "2": "Q2", "3": "Q3", "4": "Q4"}


def extract_regulatory_metadata(parsed_text: str) -> RegulatoryMetadata:
    """从监管发文正文抽取头部元数据。

    设计原则：
    - 纯 regex，零外部依赖，单文档执行 < 10ms
    - 任何字段抽不到给空字符串，不抛异常
    - status: 至少抽到 1 个字段 → PARTIAL；4+ → OK；全空 → FAILED
    """
    if not parsed_text:
        return RegulatoryMetadata(status="FAILED")

    text = parsed_text.replace("　", " ")
    head = text[:1500]   # 头部 1500 字（含发文单位 / 文号 / 标题 / 政策目的）
    tail = text[-600:]   # 落款 600 字（含发布日期）

    fields: dict[str, str] = {
        "document_no": _find_doc_no(head),
        "issuing_authority": _find_issuing_authority(head, tail),
        "published_at": _find_published_at(tail),
        "effective_date": _find_effective_date(text),
        "first_report_period": _find_first_report_period(text),
        "regulatory_intent": _find_regulatory_intent(head),
    }

    filled = sum(1 for value in fields.values() if value)
    if filled == 0:
        status = "FAILED"
    elif filled >= 4:
        status = "OK"
    else:
        status = "PARTIAL"

    return RegulatoryMetadata(**fields, status=status)


def _find_doc_no(text: str) -> str:
    for pattern in _DOC_NO_PATTERNS:
        match = pattern.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def _find_issuing_authority(head: str, tail: str) -> str:
    found: list[str] = []
    for source in (head, tail):
        for authority in _KNOWN_AUTHORITIES:
            if authority in source and authority not in found:
                # 去重：如果已有更长名包含当前短名（如"中国人民银行"已存在时不再加"人民银行"）
                if any(authority in existing and authority != existing for existing in found):
                    continue
                # 去重：如果当前名包含已有短名，替换
                replaced = False
                for i, existing in enumerate(list(found)):
                    if existing in authority and existing != authority:
                        found[i] = authority
                        replaced = True
                        break
                if not replaced:
                    found.append(authority)
    return " / ".join(found)


def _find_published_at(tail: str) -> str:
    matches = list(_PUBLISHED_PATTERN.finditer(tail))
    if not matches:
        return ""
    year, month, day = matches[-1].groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _find_effective_date(text: str) -> str:
    match = _EFFECTIVE_PATTERN.search(text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _find_first_report_period(text: str) -> str:
    # 季度优先
    for pattern in _REPORT_PERIOD_PATTERNS[:2]:
        match = pattern.search(text)
        if match:
            year, quarter = match.group(1), match.group(2)
            return f"{int(year):04d}{_CN_QUARTER_MAP.get(quarter, 'Q?')}"
    # 月度兜底
    match = _REPORT_PERIOD_PATTERNS[2].search(text)
    if match:
        year, month = match.groups()
        return f"{int(year):04d}-{int(month):02d}"
    return ""


def _find_regulatory_intent(head: str) -> str:
    match = _INTENT_PATTERN.search(head)
    if not match:
        return ""
    intent = match.group(1).strip()
    intent = re.sub(r"\s+", "", intent)
    if len(intent) > 300:
        intent = intent[:300] + "…"
    return intent
