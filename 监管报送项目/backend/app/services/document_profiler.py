import json
import re

from pydantic import BaseModel, Field

from app.models.db_models import RegDocument
from app.services.hallucination_guard import apply_grounding
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
    business_signal_id: str = ""
    item_codes: list[str] = Field(default_factory=list)
    table_code: str
    section_hint: str = ""
    indicator_hint: str = ""
    change_type: str  # ADD / MODIFY / DELETE / SCOPE_ADJUST / INSTRUCTION_ADJUST / UNCLEAR
    evidence_text: str = ""
    change_summary: str = ""
    business_summary: str = ""
    changed_dimension: str = ""
    changed_from: str = ""
    changed_to: str = ""
    summary_confidence: float = 0.0
    revision_actions: list[dict] = Field(default_factory=list)
    revision_spans: list[dict] = Field(default_factory=list)
    candidate_sources: list[dict] = Field(default_factory=list)
    confidence: float = 0.7
    evidence_verified: bool = True  # False = 原文中未找到该证据片段（疑似幻觉）
    source_type: str = "LLM"  # LLM / REVISION_TABLE / EXCEL_DIFF
    grounding_status: str = ""  # VERIFIED / PARTIAL / UNVERIFIED / RULE_BASED
    grounding_coverage: float = 0.0
    matched_excerpt: str = ""
    human_review_status: str = "PENDING"  # PENDING / ACCEPTED / REJECTED / CORRECTED
    matched_item_code: str = ""
    match_status: str = ""
    composite_match: dict = Field(default_factory=dict)
    llm_summary: dict = Field(default_factory=dict)
    # ROW = 行级指标新增/删除（产品类别变化）
    # COLUMN = 列级度量新增/删除/修改（计算口径变化）
    # CELL = 单个 cell 口径调整
    # UNCLEAR = LLM 无法判断
    change_axis: str = "UNCLEAR"


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
    change_signals = _enrich_current_revision_action_evidence(
        change_signals,
        document.parsed_text or "",
    )
    change_signals = _ensure_current_revision_scope_signals(
        change_signals,
        document.parsed_text or "",
        found_codes,
    )
    change_signals = _ensure_current_revision_item_definition_signals(
        change_signals,
        document.parsed_text or "",
        found_codes,
    )
    # 原文核验：检查 evidence_text 是否真实存在于文档中，防止幻觉
    doc_text_normalized = re.sub(r"\s+", "", document.parsed_text or "")
    change_signals = [_ground_signal(s, doc_text_normalized) for s in change_signals]
    # 补落格：LLM 抽 signal 通常不填 matched_item_code，用 item_resolver 字面匹配补上
    # 详见 docs/concept-and-ticket-reuse-design.md 补丁 / item_resolver.py
    if session is not None:
        change_signals = _resolve_missing_item_codes(change_signals, session)
    change_signals = _merge_business_signals(change_signals)
    change_signals = _enrich_business_change_summaries(
        change_signals,
        document.parsed_text or "",
    )
    signal_codes = sorted({s.table_code for s in change_signals if s.table_code})
    affected_codes = sorted(set(regex_codes).union(signal_codes))
    in_scope = sorted(c for c in set(in_scope).union(signal_codes) if c in catalog_codes)
    out_of_scope = sorted(c for c in set(out_of_scope).union(signal_codes) if c not in catalog_codes)
    suggested_route = _derive_route(in_scope, out_of_scope, change_signals)

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
      "change_axis": "COLUMN",
      "evidence_text": "原文直接引用片段",
      "confidence": 0.85
    }}
  ],
  "reason": "综合判断说明"
}}

change_axis 填写规则（必填，不能省略）：
- ROW：本次变更是新增或删除了报表的某几行（即新增/删除某个产品类别、业务类别）。例如：G01_IV 新增"11.a.1通过第三方互联网平台吸收的个人活期存款"行。
- COLUMN：本次变更是新增、删除或修改了报表的某个列（即度量维度变化，如新增"修正久期"列、修改"余额"口径）。例如：G31 新增"C 修正久期"列。
- CELL：本次变更只涉及某个具体 cell 的填报口径或说明调整，行和列本身不变。
- UNCLEAR：无法从原文判断变更发生在哪个轴。

系统已知指标：
{items_text}

文件文本（前10000字）：
{_profile_prompt_document_text(document.parsed_text or "")[:10000]}""".strip()


def _profile_prompt_document_text(document_text: str) -> str:
    """Remove machine-only structured blocks before sending text to the LLM."""
    return re.sub(
        r"(?ms)^## 当前版本原位修订片段[^\n]*\n.*?(?=^## |\Z)",
        "",
        document_text or "",
    ).strip()


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
        raw_axis = str(item.get("change_axis", "")).strip().upper()
        change_axis = raw_axis if raw_axis in {"ROW", "COLUMN", "CELL", "UNCLEAR"} else "UNCLEAR"
        signals.append(
            TableChangeSignal(
                table_code=str(item.get("table_code", "")).strip().upper(),
                section_hint=str(item.get("section_hint", "")).strip(),
                indicator_hint=indicator_hint,
                change_type=change_type,
                change_axis=change_axis,
                evidence_text=evidence_text,
                change_summary=str(item.get("change_summary", "")).strip(),
                business_summary=str(item.get("business_summary", "")).strip(),
                business_signal_id=str(item.get("business_signal_id", "")).strip(),
                item_codes=item.get("item_codes") if isinstance(item.get("item_codes"), list) else [],
                changed_dimension=str(item.get("changed_dimension", "")).strip(),
                changed_from=str(item.get("changed_from", "")).strip(),
                changed_to=str(item.get("changed_to", "")).strip(),
                revision_actions=item.get("revision_actions") if isinstance(item.get("revision_actions"), list) else [],
                revision_spans=item.get("revision_spans") if isinstance(item.get("revision_spans"), list) else [],
                candidate_sources=item.get("candidate_sources") if isinstance(item.get("candidate_sources"), list) else [],
                confidence=confidence,
                matched_item_code=str(item.get("matched_item_code", "")).strip(),
                match_status=str(item.get("match_status", "")).strip(),
                composite_match=item.get("composite_match") if isinstance(item.get("composite_match"), dict) else {},
                llm_summary=item.get("llm_summary") if isinstance(item.get("llm_summary"), dict) else {},
            )
        )
    return _merge_instruction_signal_fragments(signals)


def _merge_instruction_signal_fragments(signals: list[TableChangeSignal]) -> list[TableChangeSignal]:
    """Merge adjacent Word revision fragments that describe the same indicator.

    Word tracked changes often split one business change into several runs:
    field label, definition text, formula text, and variable explanations. Keep
    the original action/date evidence, but expose one business signal downstream.
    """
    groups: dict[tuple[str, str, str], list[TableChangeSignal]] = {}
    order: list[tuple[str, str, str]] = []
    for signal in signals:
        key = (
            signal.table_code,
            _normalise_section_hint(signal.section_hint),
            _normalise_indicator_hint(signal.indicator_hint),
        )
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(signal)

    merged: list[TableChangeSignal] = []
    for key in order:
        group = groups[key]
        if len(group) == 1 or not any(_has_revision_action_marker(s.evidence_text) for s in group):
            merged.extend(group)
            continue
        merged.append(_merge_signal_group(group))
    return merged


def _normalise_section_hint(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _normalise_indicator_hint(text: str) -> str:
    normalised = re.sub(r"\s+", "", text or "").replace("·", ".")
    normalised = re.sub(r"(?:填报)?(?:定义|说明|计算公式|公式|口径).*$", "", normalised)
    return normalised or re.sub(r"\s+", "", text or "")


def _has_revision_action_marker(text: str) -> bool:
    return bool(re.search(r"\[\s*(?:新增|删除)\s*\|", text or ""))


def _merge_signal_group(group: list[TableChangeSignal]) -> TableChangeSignal:
    representative = min(
        enumerate(group),
        key=lambda item: (len(item[1].indicator_hint or ""), item[0]),
    )[1]
    evidence_parts: list[str] = []
    for signal in group:
        if signal.evidence_text and signal.evidence_text not in evidence_parts:
            evidence_parts.append(signal.evidence_text)
    return TableChangeSignal(
        table_code=representative.table_code,
        section_hint=representative.section_hint,
        indicator_hint=representative.indicator_hint,
        change_type=_dominant_change_type([s.change_type for s in group]),
        evidence_text="；".join(evidence_parts),
        change_summary=next((s.change_summary for s in group if s.change_summary), ""),
        business_summary=next((s.business_summary for s in group if s.business_summary), ""),
        confidence=max(s.confidence for s in group),
        evidence_verified=all(s.evidence_verified for s in group),
        matched_item_code=next((s.matched_item_code for s in group if s.matched_item_code), ""),
        match_status=next((s.match_status for s in group if s.match_status), ""),
        composite_match=next((s.composite_match for s in group if s.composite_match), {}),
        llm_summary=next((s.llm_summary for s in group if s.llm_summary), {}),
    )


def _dominant_change_type(change_types: list[str]) -> str:
    priority = {
        "ADD": 6,
        "DELETE": 5,
        "MODIFY": 4,
        "SCOPE_ADJUST": 3,
        "INSTRUCTION_ADJUST": 2,
        "UNCLEAR": 1,
    }
    return max(change_types, key=lambda t: priority.get(t, 0)) if change_types else "UNCLEAR"


def _enrich_current_revision_action_evidence(
    signals: list[TableChangeSignal],
    document_text: str,
) -> list[TableChangeSignal]:
    actions = _extract_current_revision_actions(document_text)
    if not actions:
        return signals

    enriched: list[TableChangeSignal] = []
    for signal in signals:
        additions = [
            action["raw"]
            for action in actions
            if _revision_action_applies_to_signal(action["text"], signal.evidence_text)
            and action["raw"] not in signal.evidence_text
        ]
        if additions:
            enriched.append(_copy_signal_with_evidence(signal, "；".join([*additions, signal.evidence_text])))
        else:
            enriched.append(signal)
    return enriched


def _extract_current_revision_actions(document_text: str) -> list[dict[str, str]]:
    current_actions: list[dict[str, str]] = []
    legacy_actions: list[dict[str, str]] = []
    block: str | None = None
    for line in document_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if "当前版本修订动作" in stripped:
                block = "current"
            elif "修订追踪" in stripped:
                block = "legacy"
            else:
                block = None
            continue
        if block is None:
            continue
        parsed = _parse_revision_action_line(stripped)
        if not parsed:
            continue
        if block == "current":
            current_actions.append(parsed)
        else:
            legacy_actions.append(parsed)
    return _latest_year_revision_actions(current_actions or legacy_actions)


def _parse_revision_action_line(line: str) -> dict[str, str] | None:
    match = re.match(r"^-?\s*\[\s*(新增|删除)\s*\|\s*([^|]+?)\s*\|\s*([^\]]+?)\s*\]\s*(.+)$", line)
    if not match:
        return None
    action, author, date, text = match.groups()
    date = date.strip()
    text = text.strip()
    return {
        "raw": f"[{action} | {author.strip()} | {date}] {text}",
        "action": action.strip(),
        "author": author.strip(),
        "text": text,
        "date": date,
    }


def _latest_year_revision_actions(actions: list[dict[str, str]]) -> list[dict[str, str]]:
    years = [
        int(match.group(1))
        for action in actions
        if (match := re.match(r"^\s*(\d{4})", action.get("date", "")))
    ]
    if not years:
        return actions
    latest_year = max(years)
    return [
        action
        for action in actions
        if (match := re.match(r"^\s*(\d{4})", action.get("date", "")))
        and int(match.group(1)) == latest_year
    ]


def _revision_action_applies_to_signal(action_text: str, evidence_text: str) -> bool:
    token = re.sub(r"[，,。、；;：:\[\]\s]+", "", action_text or "")
    if len(token) < 2:
        return False
    evidence_normalized = re.sub(r"\s+", "", evidence_text or "")
    return token in evidence_normalized


def _copy_signal_with_evidence(signal: TableChangeSignal, evidence_text: str) -> TableChangeSignal:
    return signal.model_copy(update={"evidence_text": evidence_text})


def _ensure_current_revision_scope_signals(
    signals: list[TableChangeSignal],
    document_text: str,
    found_codes: list[str],
) -> list[TableChangeSignal]:
    """Add deterministic scope signals for instruction paragraphs the LLM missed."""
    if any("填报机构" in signal.indicator_hint for signal in signals):
        return signals

    paragraph = _extract_instruction_paragraph(document_text, "填报机构")
    if not paragraph:
        return signals

    actions = _extract_current_revision_actions(document_text)
    additions = [
        action["raw"]
        for action in actions
        if _revision_action_applies_to_signal(action["text"], paragraph)
    ]
    if not additions:
        return signals

    table_code = next((code for code in found_codes if code), "")
    if not table_code:
        return signals

    return [
        *signals,
        TableChangeSignal(
            table_code=table_code,
            section_hint="第二部分：一般说明",
            indicator_hint="填报机构范围",
            change_type="SCOPE_ADJUST",
            evidence_text="；".join([*additions, paragraph]),
            confidence=0.86,
        ),
    ]


def _ensure_current_revision_item_definition_signals(
    signals: list[TableChangeSignal],
    document_text: str,
    found_codes: list[str],
) -> list[TableChangeSignal]:
    """Add or enrich item-definition signals when current revision inserts a qualifier."""
    actions = _extract_current_revision_actions(document_text)
    if not actions or not found_codes:
        return signals

    definitions = _extract_revision_item_definition_paragraphs(document_text, actions)
    if not definitions:
        return signals
    span_paragraphs = _extract_current_revision_span_paragraphs(document_text)

    out = list(signals)
    existing_by_hint = {
        _normalise_signal_lookup_key(signal.indicator_hint): index
        for index, signal in enumerate(out)
        if signal.indicator_hint
    }
    table_code = next((code for code in found_codes if code), "")
    if not table_code:
        return signals

    for definition in definitions:
        hint = str(definition["hint"])
        key = _normalise_signal_lookup_key(hint)
        evidence_text = "；".join([*definition["actions"], str(definition["paragraph"])])
        revision_spans = _matching_revision_spans(
            hint,
            str(definition["paragraph"]),
            span_paragraphs,
        )
        revision_spans = _enrich_revision_spans_with_actions(
            revision_spans,
            definition.get("action_details") if isinstance(definition.get("action_details"), list) else [],
            str(definition["paragraph"]),
        )
        if key in existing_by_hint:
            index = existing_by_hint[key]
            current = out[index]
            out[index] = current.model_copy(
                update={
                    "section_hint": current.section_hint or "填报说明定义",
                    "indicator_hint": hint,
                    "change_type": _normalize_revision_marker_change_type(
                        current.change_type,
                        evidence_text,
                        hint,
                    ),
                    "evidence_text": evidence_text,
                    "revision_spans": revision_spans or current.revision_spans,
                    "confidence": max(current.confidence, 0.86),
                    "source_type": "RULE_BASED",
                }
            )
            continue

        out.append(
            TableChangeSignal(
                table_code=table_code,
                section_hint="填报说明定义",
                indicator_hint=hint,
                change_type=_normalize_revision_marker_change_type(
                    "SCOPE_ADJUST",
                    evidence_text,
                    hint,
                ),
                evidence_text=evidence_text,
                revision_spans=revision_spans,
                confidence=0.86,
                source_type="RULE_BASED",
            )
        )
        existing_by_hint[key] = len(out) - 1

    return out


def _extract_revision_item_definition_paragraphs(
    document_text: str,
    actions: list[dict[str, str]],
) -> list[dict[str, object]]:
    definitions: list[dict[str, object]] = []
    lines = document_text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        hint = _extract_item_definition_hint(stripped)
        if not hint:
            continue

        paragraph_parts = [stripped]
        for next_line in lines[index + 1 : index + 5]:
            next_stripped = next_line.strip()
            if not next_stripped:
                break
            if next_stripped.startswith("## ") or _extract_item_definition_hint(next_stripped):
                break
            paragraph_parts.append(next_stripped)
        paragraph = "\n".join(paragraph_parts)
        action_matches = [
            action["raw"]
            for action in actions
            if _revision_action_applies_to_signal(action["text"], paragraph)
        ]
        action_details = [
            action
            for action in actions
            if _revision_action_applies_to_signal(action["text"], paragraph)
        ]
        if action_matches:
            definitions.append(
                {
                    "hint": hint,
                    "paragraph": paragraph,
                    "actions": action_matches,
                    "action_details": action_details,
                }
            )
    return definitions


def _extract_current_revision_span_paragraphs(document_text: str) -> list[list[dict]]:
    paragraphs: list[list[dict]] = []
    current: list[dict] = []
    in_block = False
    for line in document_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_block and current:
                paragraphs.append(current)
                current = []
            in_block = "当前版本原位修订片段" in stripped
            continue
        if not in_block or not stripped or stripped.startswith("- "):
            continue
        try:
            raw = json.loads(stripped)
        except Exception:
            continue
        if not isinstance(raw, dict):
            continue
        span = _normalize_revision_span(raw)
        if not span["text"]:
            continue
        if span["type"] == "TEXT" and span["text"] == "\n":
            if current:
                paragraphs.append(current)
                current = []
            continue
        current.append(span)
    if in_block and current:
        paragraphs.append(current)
    return paragraphs


def _normalize_revision_span(raw: dict) -> dict:
    span_type = str(raw.get("type") or "TEXT").strip().upper()
    if span_type not in {"TEXT", "INSERT", "DELETE"}:
        span_type = "TEXT"
    return {
        "type": span_type,
        "text": str(raw.get("text") or ""),
        "author": str(raw.get("author") or ""),
        "date": str(raw.get("date") or ""),
        "action": str(raw.get("action") or ("新增" if span_type == "INSERT" else "删除" if span_type == "DELETE" else "")),
    }


def _matching_revision_spans(
    hint: str,
    paragraph: str,
    span_paragraphs: list[list[dict]],
) -> list[dict]:
    if not span_paragraphs:
        return []
    hint_key = _normalise_signal_lookup_key(hint)
    paragraph_key = _normalise_signal_lookup_key(paragraph)
    for spans in span_paragraphs:
        span_key = _normalise_signal_lookup_key("".join(str(span.get("text", "")) for span in spans))
        if hint_key and hint_key in span_key:
            return _trim_revision_spans_for_hint(spans, hint, paragraph)
        if paragraph_key and (paragraph_key in span_key or span_key in paragraph_key):
            return _trim_revision_spans_for_hint(spans, hint, paragraph)
    return []


def _trim_revision_spans_for_hint(spans: list[dict], hint: str, paragraph: str) -> list[dict]:
    text = "".join(str(span.get("text", "")) for span in spans)
    if not text:
        return []

    item_code = ""
    if match := re.match(r"^(\d+(?:\.[0-9A-Za-z]+)+)", hint or ""):
        item_code = match.group(1)

    start = -1
    if item_code:
        for needle in (f"[{item_code}", item_code):
            start = text.find(needle)
            if start >= 0:
                break
    if start < 0 and paragraph:
        paragraph_head = re.sub(r"\s+", "", paragraph[:30])
        normalized_text = re.sub(r"\s+", "", text)
        normalized_start = normalized_text.find(paragraph_head)
        if normalized_start >= 0:
            start = min(normalized_start, len(text) - 1)
    if start < 0:
        start = 0

    end_candidates = [
        match.start()
        for match in re.finditer(r"\n\s*\[\d+(?:\.[0-9A-Za-z]+)+", text[start + 1 :])
    ]
    end = start + 1 + end_candidates[0] if end_candidates else min(len(text), start + 900)
    for marker in ("\n核对关系", "\n表内核对关系"):
        marker_index = text.find(marker, start)
        if marker_index >= 0:
            end = min(end, marker_index)
    end = min(end, len(text))
    return _slice_revision_spans(spans, start, end)


def _slice_revision_spans(spans: list[dict], start: int, end: int) -> list[dict]:
    out: list[dict] = []
    cursor = 0
    for span in spans:
        span = _normalize_revision_span(span)
        text = span["text"]
        next_cursor = cursor + len(text)
        if next_cursor <= start:
            cursor = next_cursor
            continue
        if cursor >= end:
            break
        local_start = max(0, start - cursor)
        local_end = min(len(text), end - cursor)
        clipped = text[local_start:local_end]
        if clipped:
            out.append({**span, "text": clipped})
        cursor = next_cursor
    return out


def _enrich_revision_spans_with_actions(
    spans: list[dict],
    actions: list[dict],
    paragraph: str,
) -> list[dict]:
    normalized_actions = [
        action
        for action in actions
        if len(_clean_revision_action_text(str(action.get("text", "")))) >= 2
    ]
    if not normalized_actions:
        return spans

    span_text = "".join(str(span.get("text", "")) for span in spans)
    if any(
        (term := _clean_revision_action_text(str(action.get("text", "")))) not in span_text
        and term in paragraph
        for action in normalized_actions
    ):
        spans = [{"type": "TEXT", "text": paragraph, "author": "", "date": "", "action": ""}]

    out = [_normalize_revision_span(span) for span in spans]
    for action in normalized_actions:
        out = _mark_revision_action_occurrences(out, action)
    return out


def _mark_revision_action_occurrences(spans: list[dict], action: dict) -> list[dict]:
    term = _clean_revision_action_text(str(action.get("text", "")))
    if not term:
        return spans
    marker_type = "INSERT" if action.get("action") == "新增" else "DELETE" if action.get("action") == "删除" else "TEXT"
    if marker_type == "TEXT":
        return spans
    if any(
        _normalize_revision_span(span)["type"] == marker_type
        and _normalize_revision_span(span)["text"] == term
        for span in spans
    ):
        return spans

    marked: list[dict] = []
    for span in spans:
        span = _normalize_revision_span(span)
        text = span["text"]
        if span["type"] != "TEXT" or term not in text:
            marked.append(span)
            continue
        parts = text.split(term)
        for index, part in enumerate(parts):
            if part:
                marked.append({**span, "text": part})
            if index < len(parts) - 1:
                marked.append(
                    {
                        "type": marker_type,
                        "text": term,
                        "author": str(action.get("author", "")),
                        "date": str(action.get("date", "")),
                        "action": str(action.get("action", "")),
                    }
                )
    return marked


def _clean_revision_action_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip("，,。；;、 ")


def _extract_item_definition_hint(line: str) -> str:
    match = re.match(r"^\s*\[\s*([0-9]+(?:\.[0-9A-Za-z]+)+)\s+([^\]]{2,120})\]\s*指", line)
    if not match:
        return ""
    item_code, item_name = match.groups()
    return f"{item_code}{item_name.strip()}"


def _normalise_signal_lookup_key(text: str) -> str:
    return re.sub(r"[\s\[\]【】（）()_.．、，,；;:：-]+", "", text or "").lower()


def _extract_instruction_paragraph(document_text: str, keyword: str) -> str:
    lines = document_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if keyword in stripped and re.match(r"^\s*\d+\s*[．.]\s*", stripped):
            # Collect this line plus subsequent content lines until the next
            # numbered section, so bank-list content on the following line
            # (e.g. "第Ⅳ部分：...直销银行...") is included in the match window.
            result_parts = [stripped]
            for j in range(i + 1, min(i + 8, len(lines))):
                next_stripped = lines[j].strip()
                if re.match(r"^\s*\d+\s*[．.]\s*", next_stripped):
                    break
                if next_stripped:
                    result_parts.append(next_stripped)
            return "\n".join(result_parts)
    return ""


def _normalize_revision_marker_change_type(change_type: str, evidence_text: str, indicator_hint: str = "") -> str:
    """Word 修订追踪标记比 LLM 类型判断更可靠。

    parsed_document_from_pair 会把插入/删除修订格式化成：
    - [新增 | 作者 | 日期] 文本
    - [删除 | 作者 | 日期] 文本
    这里的"新增/删除"只是 Word 修订动作，不等于业务上的指标新增/删除。
    因此要看修订正文是否明确出现新增列/字段/指标等业务新增词。
    """
    if not _has_revision_action_marker(evidence_text):
        return change_type
    body = re.sub(r"-?\s*\[\s*(?:新增|删除)\s*\|[^\]]+\]\s*", "", evidence_text).strip()
    business_text = f"{indicator_hint} {body}"
    if re.search(r"\[\s*新增\s*\|", evidence_text):
        # 整条指标新增判断：INSERT 动作的文本中包含该指标的括号标签 "[11.a.2"，
        # 说明指标定义括号本身被插入，即整条指标是新增而非口径微调。
        # 注：body 已剥掉 [新增|...] 标记头，因此不能在 body 里找"新增"；
        # 需在原始 evidence_text 里逐条 INSERT 动作文本中查找指标代码。
        code_match = re.match(r"^(\d+(?:\.[a-zA-Z0-9]+)+)", indicator_hint or "")
        if code_match:
            code = re.escape(code_match.group(1))
            insert_texts = re.findall(r"\[\s*新增\s*\|[^\]]+\]\s*([^；\n]+)", evidence_text)
            if any(re.search(rf"\[?\s*{code}\b", t) for t in insert_texts):
                return "ADD"
        # 显式业务新增词（新增列/字段/指标等）
        if re.search(r"新增\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)", body):
            return "ADD"
    if re.search(r"\[\s*删除\s*\|", evidence_text) and re.search(r"(?:删除|停报)\s*(?:[A-Z]?\s*[列栏行]|字段|指标|项目|报表|附表)", body):
        return "DELETE"
    if re.search(r"(定义|公式|计算|口径|范围|填报|统计|指项目)", business_text):
        return "SCOPE_ADJUST"
    return change_type


def _ground_signal(signal: TableChangeSignal, doc_normalized: str) -> TableChangeSignal:
    """Classify evidence support while preserving the legacy boolean field."""
    return apply_grounding(signal, doc_normalized)


def _merge_business_signals(signals: list[TableChangeSignal]) -> list[TableChangeSignal]:
    """Merge raw LLM/rule candidates into stable business signals.

    Candidate recall can produce several rows for the same business item. This
    function is the boundary where raw candidates stop being front-end rows.
    """
    groups: dict[str, list[TableChangeSignal]] = {}
    order: list[str] = []
    for signal in signals:
        keys = _business_signal_keys(signal)
        for key in keys:
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(signal)

    merged: list[TableChangeSignal] = []
    for key in sorted(order, key=_business_signal_sort_key):
        group = groups[key]
        primary = _choose_business_primary(group)
        item_codes = _extract_business_item_codes(
            " ".join(
                [
                    primary.matched_item_code,
                    primary.indicator_hint,
                    primary.evidence_text,
                    primary.section_hint,
                ]
            )
        )
        evidence_text = _join_unique([s.evidence_text for s in group])
        candidate_sources = [_candidate_source(s) for s in group]
        revision_actions = _dedupe_dicts(
            action
            for signal in group
            for action in _extract_revision_actions_from_evidence(signal.evidence_text)
        )
        revision_spans = _merge_signal_revision_spans(group)
        merged.append(
            primary.model_copy(
                update={
                    "business_signal_id": key,
                    "item_codes": item_codes,
                    "change_type": _dominant_change_type([s.change_type for s in group]),
                    "evidence_text": evidence_text,
                    "confidence": max(s.confidence for s in group),
                    "candidate_sources": candidate_sources,
                    "revision_actions": revision_actions,
                    "revision_spans": revision_spans,
                    "source_type": primary.source_type,
                    "grounding_status": _merged_backend_grounding_status(group),
                    "grounding_coverage": max((s.grounding_coverage for s in group), default=0.0),
                }
            )
        )
    return merged


def _business_signal_keys(signal: TableChangeSignal) -> list[str]:
    """Return grouping key(s) for a signal.

    Keys are derived only from indicator_hint and matched_item_code, NOT from
    evidence_text.  evidence_text may contain many [X.YZ] cell references that
    are illustrative examples (e.g. "举例：…[1.1C]…[5.2A]…"), which would
    otherwise cause a single signal to spawn N identical output entries.

    A signal whose indicator_hint explicitly covers multiple items (e.g.
    "11.a.1/11.a.2 附注解释") still produces one key per mentioned item so
    that cross-item merging continues to work.
    """
    table_code = signal.table_code or "UNKNOWN"
    item_codes = signal.item_codes or _extract_business_item_codes(
        " ".join(
            [
                signal.matched_item_code,
                signal.indicator_hint,
            ]
        )
    )
    if item_codes:
        return [f"{table_code}::{code}" for code in item_codes]
    return [f"{table_code}::{_normalise_signal_lookup_key(signal.indicator_hint or signal.section_hint)}"]


def _extract_business_item_codes(value: str) -> list[str]:
    codes: list[str] = []
    for match in re.finditer(r"(^|[^A-Za-z0-9.])([1-9]\d?(?:\.[0-9A-Za-z]+)+)(?=$|[^A-Za-z0-9.])", value or ""):
        code = match.group(2).replace("．", ".")
        if code and code not in codes:
            codes.append(code)
    return [
        code
        for code in codes
        if not any(other != code and other.startswith(f"{code}.") for other in codes)
    ]


def _business_signal_sort_key(key: str) -> tuple[str, list[tuple[int, int | str]]]:
    table_code, _, item_key = key.partition("::")
    return (table_code, _natural_item_key(item_key))


def _natural_item_key(value: str) -> list[tuple[int, int | str]]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"([0-9]+)", value):
        if not part:
            continue
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return parts


def _looks_like_item_code(value: str) -> bool:
    return bool(re.fullmatch(r"[1-9]\d?(?:\.[0-9A-Za-z]+)+", value or ""))


def _choose_business_primary(signals: list[TableChangeSignal]) -> TableChangeSignal:
    return sorted(signals, key=_backend_signal_priority, reverse=True)[0]


def _backend_signal_priority(signal: TableChangeSignal) -> tuple[int, int, float]:
    source_score = 2 if signal.source_type in {"RULE_BASED", "REVISION_TABLE", "EXCEL_DIFF"} else 0
    grounding_score = {
        "RULE_BASED": 3,
        "VERIFIED": 2,
        "PARTIAL": 1,
        "UNVERIFIED": 0,
    }.get(signal.grounding_status, 1 if signal.evidence_verified else 0)
    return (source_score, grounding_score, signal.confidence)


def _candidate_source(signal: TableChangeSignal) -> dict:
    return {
        "source_type": signal.source_type,
        "table_code": signal.table_code,
        "section_hint": signal.section_hint,
        "indicator_hint": signal.indicator_hint,
        "change_type": signal.change_type,
        "evidence_text": signal.evidence_text,
        "confidence": signal.confidence,
        "grounding_status": signal.grounding_status,
        "grounding_coverage": signal.grounding_coverage,
        "matched_item_code": signal.matched_item_code,
        "match_status": signal.match_status,
    }


def _merge_signal_revision_spans(signals: list[TableChangeSignal]) -> list[dict]:
    for signal in sorted(signals, key=_backend_signal_priority, reverse=True):
        if signal.revision_spans:
            return [_normalize_revision_span(span) for span in signal.revision_spans if isinstance(span, dict)]
    return []


def _extract_revision_actions_from_evidence(evidence_text: str) -> list[dict]:
    actions: list[dict] = []
    pattern = re.compile(r"\[\s*(新增|删除)\s*\|\s*([^|]+?)\s*\|\s*([^\]]+?)\]\s*([^；\n]+)")
    for match in pattern.finditer(evidence_text or ""):
        action, author, date, text = match.groups()
        actions.append(
            {
                "action": action.strip(),
                "author": author.strip(),
                "date": date.strip(),
                "text": re.sub(r"\s+", "", text or "").strip("，,。；;、 "),
            }
        )
    return actions


def _dedupe_dicts(items) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple] = set()
    for item in items:
        key = tuple(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _join_unique(values: list[str]) -> str:
    out: list[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return "；".join(out)


def _merged_backend_grounding_status(signals: list[TableChangeSignal]) -> str:
    statuses = [s.grounding_status for s in signals if s.grounding_status]
    if "RULE_BASED" in statuses:
        return "RULE_BASED"
    if "VERIFIED" in statuses:
        return "VERIFIED"
    if "PARTIAL" in statuses:
        return "PARTIAL"
    if "UNVERIFIED" in statuses:
        return "UNVERIFIED"
    return "VERIFIED" if any(s.evidence_verified for s in signals) else "UNVERIFIED"


def _enrich_business_change_summaries(
    signals: list[TableChangeSignal],
    document_text: str,
) -> list[TableChangeSignal]:
    if not signals:
        return signals

    fallback_signals = [
        signal.model_copy(
            update={
                "change_summary": signal.change_summary or _fallback_change_summary(signal),
            }
        )
        for signal in signals
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "你是银行监管报表变更分析助手，负责生成业务变更摘要。"
                "你只输出JSON，不输出Markdown。"
                "不要复述原文，不要写来源、规则命中或证据编号。"
                "每条摘要用一句业务话说明这个指标/分区到底变了什么，优先说明适用主体、统计范围、口径、公式或填报要求变化。"
                "不得补充输入中没有的信息。"
            ),
        },
        {
            "role": "user",
            "content": _build_summary_prompt(fallback_signals, document_text),
        },
    ]

    try:
        result, _raw_response, _model = complete_json(messages)
    except Exception:
        return fallback_signals

    summaries = _parse_business_signal_summaries(result)
    if not summaries:
        return fallback_signals

    enriched: list[TableChangeSignal] = []
    for signal in fallback_signals:
        summary = summaries.get(signal.business_signal_id, {})
        change_summary = _clean_summary(summary.get("change_summary", ""))
        business_summary = _clean_summary(summary.get("business_summary", ""))
        llm_summary = summary if summary else signal.llm_summary
        summary_confidence = _safe_float(summary.get("confidence", 0.0))
        enriched.append(
            signal.model_copy(
                update={
                    "change_type": summary.get("change_type") or signal.change_type,
                    "change_summary": change_summary or signal.change_summary,
                    "business_summary": business_summary or signal.business_summary,
                    "changed_dimension": summary.get("changed_dimension") or signal.changed_dimension,
                    "changed_from": summary.get("changed_from") or signal.changed_from,
                    "changed_to": summary.get("changed_to") or signal.changed_to,
                    "summary_confidence": summary_confidence or signal.summary_confidence,
                    "llm_summary": llm_summary,
                }
            )
        )
    return enriched


def _build_summary_prompt(signals: list[TableChangeSignal], document_text: str) -> str:
    signal_lines = []
    for index, signal in enumerate(signals[:30]):
        signal_lines.append(
            "\n".join(
                [
                    f"- business_signal_id: {signal.business_signal_id or f's{index}'}",
                    f"  table_code: {signal.table_code}",
                    f"  item_codes: {', '.join(signal.item_codes)}",
                    f"  section_hint: {signal.section_hint}",
                    f"  indicator_hint: {signal.indicator_hint}",
                    f"  change_type: {signal.change_type}",
                    f"  revision_actions: {signal.revision_actions}",
                    f"  candidate_sources: {signal.candidate_sources}",
                    f"  evidence_text: {_clip_text(signal.evidence_text, 500)}",
                ]
            )
        )
    return f"""请为每条已归并业务信号生成结构化业务变更摘要。
输出JSON格式：
{{
  "business_signal_summaries": [
    {{
      "business_signal_id": "G01::11.a.2",
      "change_type": "SCOPE_ADJUST",
      "changed_dimension": "统计主体 | 填报机构范围 | 指标定义 | 计算公式 | 列位说明 | 报送频率 | 其他",
      "changed_from": "",
      "changed_to": "",
      "change_summary": "一句话说明业务变化",
      "business_summary": "可选，若与change_summary相同可留空",
      "confidence": 0.0
    }}
  ]
}}

摘要要求：
1. 只说明业务变化，不要复述大段原文。
2. 有"新增/删除"修订标记时，先判断它是否只是Word修订动作；只有明确新增指标/字段/报表时才写"新增指标"。
3. 不要使用"限定""规则命中""LLM草稿""证据显示"等过程性表达。
4. 必须基于 revision_actions、candidate_sources 和 evidence_text 判断 changed_dimension、changed_from、changed_to。
5. 如果无法判断具体业务变化，change_type 输出 UNCLEAR，change_summary 写明需要人工确认的缺口。
6. 每条摘要不超过70个中文字符。

信号列表：
{chr(10).join(signal_lines)}

原文上下文（截取）：
{_clip_text(document_text, 3000)}""".strip()


def _parse_business_signal_summaries(result: dict) -> dict[str, dict]:
    raw = result.get("business_signal_summaries", []) if isinstance(result, dict) else []
    if not raw and isinstance(result, dict):
        raw = result.get("signal_summaries", [])
    if not isinstance(raw, list):
        return {}
    summaries: dict[str, dict] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        signal_id = str(item.get("business_signal_id") or item.get("signal_id") or "").strip()
        if not signal_id:
            continue
        summaries[signal_id] = {
            "change_summary": _clean_summary(item.get("change_summary", "")),
            "business_summary": _clean_summary(item.get("business_summary", "")),
            "change_type": str(item.get("change_type", "")).strip().upper(),
            "changed_dimension": _clean_summary(item.get("changed_dimension", "")),
            "changed_from": _clean_summary(item.get("changed_from", "")),
            "changed_to": _clean_summary(item.get("changed_to", "")),
            "confidence": item.get("confidence", 0.0),
        }
    return summaries


def _fallback_change_summary(signal: TableChangeSignal) -> str:
    indicator = _summary_indicator_name(signal)
    inserted_terms = _extract_revision_terms(signal.evidence_text, "新增")
    deleted_terms = _extract_revision_terms(signal.evidence_text, "删除")

    if inserted_terms:
        return f"口径调整：{indicator}修订记录新增{_format_summary_terms(inserted_terms)}，需人工确认具体业务含义。"
    if deleted_terms:
        terms = _format_summary_terms(deleted_terms)
        return f"口径调整：{indicator}修订记录删除{terms}，需人工确认具体业务含义。"
    if signal.change_type == "ADD":
        return f"新增指标：{indicator}。"
    if signal.change_type == "DELETE":
        return f"删除指标：{indicator}。"
    if signal.change_type == "SCOPE_ADJUST":
        return f"口径调整：{indicator}统计口径发生调整。"
    if signal.change_type == "INSTRUCTION_ADJUST":
        return f"说明调整：{indicator}填报说明发生调整。"
    return _clip_text(re.sub(r"\s+", " ", signal.evidence_text).strip(), 80)


def _extract_revision_terms(evidence_text: str, operation: str) -> list[str]:
    terms: list[str] = []
    pattern = re.compile(rf"\[\s*{operation}\s*\|[^\]]+\]\s*([^；\n]+)")
    for match in pattern.finditer(evidence_text or ""):
        term = _clean_revision_term(match.group(1) or "")
        if term and len(term) <= 24 and term not in terms:
            terms.append(term)
    return terms


def _clean_revision_term(value: str) -> str:
    term = re.sub(r"\s+", "", value or "")
    term = term.strip("，,。；;、 ")
    if re.fullmatch(r"[A-Z][.．]?", term):
        return f"{term[0]}列"
    return term.strip("，,。；;、 ")


def _format_summary_terms(terms: list[str]) -> str:
    return "、".join(f'"{term}"' for term in terms)


def _summary_indicator_name(signal: TableChangeSignal) -> str:
    text = signal.indicator_hint or signal.section_hint or "该指标"
    text = re.sub(r"^\[\s*", "", text)
    text = re.sub(r"\s*\]$", "", text)
    text = re.sub(r"\s+", "", text)
    return text or "该指标"


def _clean_summary(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return _clip_text(text, 120)


def _clip_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _safe_float(value: object) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


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
