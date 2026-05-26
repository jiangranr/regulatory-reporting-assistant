import re

from pydantic import BaseModel, Field

from app.models.db_models import RegDocument
from app.services.llm_client import complete_json

FULL_ANALYSIS = "FULL_ANALYSIS"
LIGHTWEIGHT_ARCHIVE = "LIGHTWEIGHT_ARCHIVE"
MANUAL_REVIEW = "MANUAL_REVIEW"
SKIP = "SKIP"

# 匹配1104表号：G + 1-2位数字 + 可选大写字母，如 G21、G4B、G11
_TABLE_CODE_RE = re.compile(r"\bG\d{1,2}[A-Z]?\b")

_VALID_CHANGE_TYPES = frozenset(
    {"ADD", "MODIFY", "DELETE", "SCOPE_ADJUST", "INSTRUCTION_ADJUST", "UNCLEAR"}
)


class TableChangeSignal(BaseModel):
    table_code: str
    section_hint: str = ""
    indicator_hint: str = ""
    change_type: str  # ADD / MODIFY / DELETE / SCOPE_ADJUST / INSTRUCTION_ADJUST / UNCLEAR
    evidence_text: str = ""
    confidence: float = 0.7
    evidence_verified: bool = True  # False = 原文中未找到该证据片段（疑似幻觉）
    matched_item_code: str = ""
    match_status: str = ""
    composite_match: dict = Field(default_factory=dict)


class Document1104ProfileDraft(BaseModel):
    has_1104_reference: bool
    affected_table_codes: list[str] = Field(default_factory=list)
    in_scope_tables: list[str] = Field(default_factory=list)
    out_of_scope_tables: list[str] = Field(default_factory=list)
    change_signals: list[TableChangeSignal] = Field(default_factory=list)
    suggested_route: str = MANUAL_REVIEW
    should_create_task: bool = False
    reason: str = ""
    confidence_score: float = 0.0
    llm_model: str = ""
    raw_response: str = ""


def generate_document_profile(
    document: RegDocument,
    context: dict,
    session=None,
) -> Document1104ProfileDraft:
    """
    阶段一：基于数据库维护的报表本体做轻量预扫（无LLM）。
    未命中 Gxx 表号或报表名称 → 直接返回 SKIP，不调用LLM。
    命中数据库报表范围       → 阶段二：把报表本体、分区和文章交给LLM提取变更信号。
    路线推导由规则层完成，不依赖LLM猜测。
    """
    text = (document.parsed_text or "") + " " + (document.title or "")
    regex_codes = sorted(set(_TABLE_CODE_RE.findall(text)))
    catalog_codes = _catalog_object_codes(context)
    found_codes = _detect_catalog_references(text, regex_codes, context)

    if not regex_codes and not found_codes:
        return Document1104ProfileDraft(
            has_1104_reference=False,
            suggested_route=SKIP,
            reason="文档中未发现数据库已维护的监管报表代码或报表名称，不进入报送影响分析流程。",
            confidence_score=0.95,
        )

    in_scope = sorted(c for c in found_codes if c in catalog_codes)
    out_of_scope = sorted(c for c in regex_codes if c not in catalog_codes)

    messages = [
        {
            "role": "system",
            "content": (
                "你是银行1104监管报表数据治理助手。你只输出JSON，不输出Markdown。"
                "任务：基于系统提供的监管报表本体和报表分区，从监管发文中找出报表、分区或指标"
                "被新增、修改、删除或调整口径/填报说明的证据。"
                "只能围绕系统维护的报表范围生成 change_signals；无法确认具体报表时输出空数组。"
                "change_type 只能是以下之一："
                "ADD（新增指标）/ MODIFY（修改指标内容）/ DELETE（删除指标）"
                "/ SCOPE_ADJUST（调整统计口径）/ INSTRUCTION_ADJUST（调整填报说明）"
                "/ UNCLEAR（表号被提及但变更内容不明确）。"
                "evidence_text 必须直接引用原文片段，不得改写或编造。"
            ),
        },
        {
            "role": "user",
            "content": _build_prompt(document, found_codes, context),
        },
    ]

    result, raw_response, model = complete_json(messages)
    change_signals = _parse_change_signals(result)
    # 原文核验：检查 evidence_text 是否真实存在于文档中，防止幻觉
    doc_text_normalized = re.sub(r"\s+", "", document.parsed_text or "")
    change_signals = [_ground_signal(s, doc_text_normalized) for s in change_signals]
    # 补落格：LLM 抽 signal 通常不填 matched_item_code，用 item_resolver 字面匹配补上
    # 详见 docs/concept-and-ticket-reuse-design.md 补丁 / item_resolver.py
    if session is not None:
        change_signals = _resolve_missing_item_codes(change_signals, session)
    signal_codes = sorted({s.table_code for s in change_signals if s.table_code})
    affected_codes = sorted(set(regex_codes).union(signal_codes))
    in_scope = sorted(c for c in set(in_scope).union(signal_codes) if c in catalog_codes)
    out_of_scope = sorted(c for c in set(out_of_scope).union(signal_codes) if c not in catalog_codes)
    suggested_route = _derive_route(in_scope, out_of_scope, change_signals)

    # 汇总所有变更信号的证据文本作为 evidence_text
    evidence_parts = [s.evidence_text for s in change_signals if s.evidence_text]
    evidence_text = "；".join(evidence_parts[:3])

    return Document1104ProfileDraft(
        has_1104_reference=True,
        affected_table_codes=affected_codes,
        in_scope_tables=in_scope,
        out_of_scope_tables=out_of_scope,
        change_signals=change_signals,
        suggested_route=suggested_route,
        should_create_task=(suggested_route == FULL_ANALYSIS),
        reason=str(result.get("reason", "")),
        confidence_score=_compute_confidence(change_signals, in_scope),
        llm_model=model,
        raw_response=raw_response,
    )


def _build_prompt(document: RegDocument, found_codes: list[str], context: dict) -> str:
    objects_text = _format_reporting_objects(context)
    sections_text = _format_reporting_sections(context)
    in_scope_items = [
        item
        for item in context.get("reporting_items", [])
        if any(item["item_code"].startswith(code) for code in found_codes)
    ]
    if in_scope_items:
        items_text = "\n".join(
            f"- {item['item_code']}: {item['item_name']}（{item['row_label']} × {item['column_label']}）"
            for item in in_scope_items
        )
    else:
        items_text = "（当前系统目录暂无该表指标，请直接从原文提取指标描述）"

    return f"""监管文件标题：{document.title}
发现的1104报表表号：{", ".join(found_codes)}

系统维护的监管报表本体：
{objects_text}

系统维护的报表分区：
{sections_text}

对每个表号，找出文档中描述的指标变更，输出以下JSON：
{{
  "change_signals": [
    {{
      "table_code": "G24",
      "section_hint": "主表",
      "indicator_hint": "同业融入余额",
      "change_type": "SCOPE_ADJUST",
      "evidence_text": "原文直接引用片段",
      "confidence": 0.85
    }}
  ],
  "reason": "综合判断说明"
}}

系统已知指标：
{items_text}

文件文本（前10000字）：
{(document.parsed_text or "")[:10000]}""".strip()


def _catalog_object_codes(context: dict) -> set[str]:
    return {
        str(item.get("object_code", "")).strip().upper()
        for item in context.get("reporting_objects", [])
        if str(item.get("object_code", "")).strip()
    }


def _detect_catalog_references(text: str, regex_codes: list[str], context: dict) -> list[str]:
    found = {code for code in regex_codes if code in _catalog_object_codes(context)}
    for item in context.get("reporting_objects", []):
        code = str(item.get("object_code", "")).strip().upper()
        name = str(item.get("object_name", "")).strip()
        if code and name and name in text:
            found.add(code)
    return sorted(found)


def _format_reporting_objects(context: dict) -> str:
    objects = context.get("reporting_objects", [])
    if not objects:
        return "（当前数据库未维护监管报表本体）"
    lines = []
    for item in objects:
        code = str(item.get("object_code", "")).strip()
        name = str(item.get("object_name", "")).strip()
        category = str(item.get("object_category", "")).strip()
        frequency = str(item.get("report_frequency", "")).strip()
        parts = [part for part in [category, frequency] if part]
        suffix = f"（{'，'.join(parts)}）" if parts else ""
        lines.append(f"- {code}: {name}{suffix}")
    return "\n".join(lines)


def _format_reporting_sections(context: dict) -> str:
    sections = sorted(
        context.get("reporting_sections", []),
        key=lambda item: (
            str(item.get("object_code", "")),
            int(item.get("display_order", 0) or 0),
            str(item.get("section_code", "")),
        ),
    )
    if not sections:
        return "（当前数据库未维护报表分区）"
    return "\n".join(
        f"- {item.get('object_code', '')}.{item.get('section_code', '')}: "
        f"{item.get('section_name', '')}"
        for item in sections
    )


def _parse_change_signals(result: dict) -> list[TableChangeSignal]:
    raw = result.get("change_signals", [])
    if not isinstance(raw, list):
        return []
    signals = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        change_type = str(item.get("change_type", "UNCLEAR")).strip().upper()
        if change_type not in _VALID_CHANGE_TYPES:
            change_type = "UNCLEAR"
        evidence_text = str(item.get("evidence_text", "")).strip()
        indicator_hint = str(item.get("indicator_hint", "")).strip()
        change_type = _normalize_revision_marker_change_type(change_type, evidence_text, indicator_hint)
        try:
            confidence = min(max(float(item.get("confidence", 0.7)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.7
        signals.append(
            TableChangeSignal(
                table_code=str(item.get("table_code", "")).strip().upper(),
                section_hint=str(item.get("section_hint", "")).strip(),
                indicator_hint=indicator_hint,
                change_type=change_type,
                evidence_text=evidence_text,
                confidence=confidence,
                matched_item_code=str(item.get("matched_item_code", "")).strip(),
                match_status=str(item.get("match_status", "")).strip(),
                composite_match=item.get("composite_match") if isinstance(item.get("composite_match"), dict) else {},
            )
        )
    return signals


def _normalize_revision_marker_change_type(change_type: str, evidence_text: str, indicator_hint: str = "") -> str:
    """Word 修订追踪标记比 LLM 类型判断更可靠。

    parsed_document_from_pair 会把插入/删除修订格式化成：
    - [新增 | 作者 | 日期] 文本
    - [删除 | 作者 | 日期] 文本
    这里的“新增/删除”只是 Word 修订动作，不等于业务上的指标新增/删除。
    因此要看修订正文是否明确出现新增列/字段/指标等业务新增词。
    """
    if change_type not in {"INSTRUCTION_ADJUST", "UNCLEAR"}:
        return change_type
    body = re.sub(r"-?\s*\[\s*(?:新增|删除)\s*\|[^\]]+\]\s*", "", evidence_text).strip()
    business_text = f"{indicator_hint} {body}"
    if re.search(r"\[\s*新增\s*\|", evidence_text) and re.search(r"新增\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)", body):
        return "ADD"
    if re.search(r"\[\s*删除\s*\|", evidence_text) and re.search(r"(?:删除|停报)\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)", body):
        return "DELETE"
    if re.search(r"(定义|公式|计算|口径|范围|填报|统计)", business_text):
        return "SCOPE_ADJUST"
    return change_type


def _ground_signal(signal: TableChangeSignal, doc_normalized: str) -> TableChangeSignal:
    """
    检查 evidence_text 是否真实存在于原文（去除空白后的滑动窗口匹配）。
    找不到 → evidence_verified=False，置信度上限压至 0.3，防止幻觉被高置信度误导。
    """
    ev = signal.evidence_text.strip()
    if not ev or len(ev) < 8:
        return signal

    ev_norm = re.sub(r"\s+", "", ev)
    chunk = min(10, len(ev_norm))

    found = any(
        ev_norm[i : i + chunk] in doc_normalized
        for i in range(0, max(1, len(ev_norm) - chunk + 1), 4)
    )

    if found:
        return signal
    return TableChangeSignal(
        table_code=signal.table_code,
        section_hint=signal.section_hint,
        indicator_hint=signal.indicator_hint,
        change_type=signal.change_type,
        evidence_text=signal.evidence_text,
        confidence=min(signal.confidence, 0.3),
        evidence_verified=False,
        matched_item_code=signal.matched_item_code,
        match_status=signal.match_status,
        composite_match=signal.composite_match,
    )


def _resolve_missing_item_codes(
    signals: list[TableChangeSignal], session
) -> list[TableChangeSignal]:
    """补落格：对 matched_item_code 为空的 signal，用 item_resolver 字面匹配补一次。

    设计原则：
    - 只填空，不覆盖：上游 Excel diff / scanner 已经填好的不动
    - 失败静默：resolver 任何异常都退回原 signal，不阻塞主流程
    - 命中后写两路：
        FUZZY_PRECISE → signal.matched_item_code + match_status
        FUZZY_LANE    → signal.composite_match.reporting_item_codes + match_status
    """
    from app.services.item_resolver import ReportingItemResolver

    try:
        resolver = ReportingItemResolver(session)
    except Exception:
        return signals

    out: list[TableChangeSignal] = []
    for signal in signals:
        if signal.matched_item_code or (
            signal.composite_match
            and signal.composite_match.get("reporting_item_codes")
        ):
            out.append(signal)
            continue
        if not signal.table_code or not signal.indicator_hint:
            out.append(signal)
            continue
        try:
            r = resolver.resolve(signal.table_code, signal.indicator_hint)
        except Exception:
            out.append(signal)
            continue
        if r.match_status == "UNRESOLVED":
            out.append(signal)
            continue
        new_signal = signal.model_copy()
        if r.match_status == "FUZZY_PRECISE" and r.matched_item_code:
            new_signal.matched_item_code = r.matched_item_code
            new_signal.match_status = "FUZZY_PRECISE"
        elif r.match_status == "FUZZY_LANE" and r.item_codes:
            cm = dict(new_signal.composite_match or {})
            cm["reporting_item_codes"] = r.item_codes
            cm["resolver_paths"] = r.paths
            cm["resolver_confidence"] = r.confidence
            new_signal.composite_match = cm
            new_signal.match_status = "FUZZY_LANE"
        out.append(new_signal)
    return out


def _derive_route(
    in_scope: list[str],
    out_of_scope: list[str],
    signals: list[TableChangeSignal],
) -> str:
    in_scope_set = set(in_scope)
    actionable = {"ADD", "MODIFY", "DELETE", "SCOPE_ADJUST", "INSTRUCTION_ADJUST"}
    in_scope_signals = [s for s in signals if s.table_code in in_scope_set]

    if in_scope_signals and any(s.change_type in actionable for s in in_scope_signals):
        return FULL_ANALYSIS
    if in_scope_signals:
        return MANUAL_REVIEW
    if out_of_scope:
        return LIGHTWEIGHT_ARCHIVE
    return MANUAL_REVIEW


def _compute_confidence(signals: list[TableChangeSignal], in_scope: list[str]) -> float:
    in_scope_set = set(in_scope)
    in_scope_signals = [s for s in signals if s.table_code in in_scope_set]
    if not in_scope_signals:
        return 0.5
    return sum(s.confidence for s in in_scope_signals) / len(in_scope_signals)
