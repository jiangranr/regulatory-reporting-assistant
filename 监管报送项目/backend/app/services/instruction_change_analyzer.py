"""G31 填报说明版本变更分析器：综合批注、修订、高亮生成 LLM 变更摘要。"""
import asyncio
from dataclasses import dataclass

from app.services.instruction_parser import (
    CommentFragment,
    HighlightFragment,
    InstructionParseResult,
    RevisionFragment,
)
from app.services.llm_client import LLMClientError, complete_json


@dataclass
class ChangeItem:
    category: str
    change: str
    evidence: str = ""


@dataclass
class InstructionChangeAnalysis:
    object_code: str
    summary: str
    key_changes: list[ChangeItem]
    attention_items: list[str]
    uncertain_items: list[str]
    comments_count: int
    revisions_count: int
    highlights_count: int
    llm_model: str
    raw_response: str = ""
    error_message: str = ""


async def analyze_instruction_changes(
    instruction: InstructionParseResult,
    object_code: str,
    reporting_objects: list[dict],
    reporting_sections: list[dict],
    reporting_items: list[dict],
) -> InstructionChangeAnalysis:
    """
    综合 Word 批注、修订追踪、彩色高亮和库里维护的报表范围，
    调用 LLM 输出"此版本填报说明相对上一版本有哪些变更需注意"。
    """
    comments = instruction.comments
    revisions = instruction.revisions
    highlights = instruction.highlights

    messages = [
        {
            "role": "system",
            "content": (
                "你是银行监管报表数据治理专家。你只输出JSON，不输出Markdown。"
                "任务：根据 Word 批注、修订追踪和重点标注，总结本版本填报说明相对上一版本的变更。"
                "变更类型包括：统计口径调整、填报方法变化、指标新增/删除、填报范围变化、其他注意事项。"
                "evidence 必须直接引用原文或批注原话，不得编造。"
            ),
        },
        {
            "role": "user",
            "content": _build_prompt(
                object_code=object_code,
                comments=comments,
                revisions=revisions,
                highlights=highlights,
                instruction_text=instruction.text,
                reporting_objects=reporting_objects,
                reporting_sections=reporting_sections,
                reporting_items=reporting_items,
            ),
        },
    ]

    try:
        result, raw, model = await asyncio.to_thread(complete_json, messages)
    except LLMClientError as exc:
        return InstructionChangeAnalysis(
            object_code=object_code,
            summary="",
            key_changes=[],
            attention_items=[],
            uncertain_items=[],
            comments_count=len(comments),
            revisions_count=len(revisions),
            highlights_count=len(highlights),
            llm_model="",
            error_message=str(exc),
        )

    return InstructionChangeAnalysis(
        object_code=object_code,
        summary=str(result.get("summary", "")),
        key_changes=_parse_change_items(result.get("key_changes", [])),
        attention_items=_parse_str_list(result.get("attention_items", [])),
        uncertain_items=_parse_str_list(result.get("uncertain_items", [])),
        comments_count=len(comments),
        revisions_count=len(revisions),
        highlights_count=len(highlights),
        llm_model=model,
        raw_response=raw,
    )


def _build_prompt(
    object_code: str,
    comments: list[CommentFragment],
    revisions: list[RevisionFragment],
    highlights: list[HighlightFragment],
    instruction_text: str,
    reporting_objects: list[dict],
    reporting_sections: list[dict],
    reporting_items: list[dict],
) -> str:
    scope_lines = _format_scope(object_code, reporting_objects, reporting_sections, reporting_items)

    comment_block = "\n".join(
        f"{i}. [{c.author} | {c.date[:10] if c.date else ''}] {c.text}"
        for i, c in enumerate(comments[:80], 1)
    ) or "（无批注）"

    revision_block = "\n".join(
        f"- [{'新增' if r.change_type == 'INSERT' else '删除'} | {r.author} | {r.date[:10] if r.date else ''}] {r.text}"
        for r in revisions[:80]
    ) or "（无修订追踪）"

    highlight_block = "\n".join(
        f"- [{h.color}] {h.text}" for h in highlights[:60]
    ) or "（无彩色重点）"

    return f"""分析目标报表：{object_code}

=== 系统维护的 {object_code} 报表范围 ===
{scope_lines}

=== 文档批注（共 {len(comments)} 条）===
{comment_block}

=== 修订追踪（共 {len(revisions)} 条）===
{revision_block}

=== 彩色重点片段（共 {len(highlights)} 条）===
{highlight_block}

=== 填报说明正文（前 6000 字）===
{instruction_text[:6000]}

请综合以上信息，总结本版本 {object_code} 填报说明相对上一版本的主要变更，聚焦"填报人员需注意什么"。

输出 JSON 格式（字段说明：summary=整体摘要1-2句, key_changes=变更条目数组, attention_items=注意事项列表, uncertain_items=需人工确认项）：
{{
  "summary": "整体变更摘要",
  "key_changes": [
    {{"category": "统计口径", "change": "变更描述", "evidence": "原文/批注引用"}},
    {{"category": "填报方法", "change": "变更描述", "evidence": "原文/批注引用"}}
  ],
  "attention_items": ["注意事项1", "注意事项2"],
  "uncertain_items": ["需人工确认项1"]
}}""".strip()


def _format_scope(
    object_code: str,
    reporting_objects: list[dict],
    reporting_sections: list[dict],
    reporting_items: list[dict],
) -> str:
    obj = next(
        (o for o in reporting_objects if str(o.get("object_code", "")).strip().upper() == object_code.upper()),
        None,
    )
    if not obj:
        return f"（库中未维护 {object_code} 报表信息）"

    lines = [
        f"报表名称：{obj.get('object_name', '')}",
        f"类别：{obj.get('object_category', '')}",
        f"频度：{obj.get('report_frequency', '')}",
    ]

    obj_sections = [
        s for s in reporting_sections
        if str(s.get("object_code", "")).strip().upper() == object_code.upper()
    ]
    if obj_sections:
        lines.append("分区：")
        lines.extend(
            f"  - {s.get('section_code', '')}: {s.get('section_name', '')}"
            for s in obj_sections
        )

    obj_items = [
        it for it in reporting_items
        if str(it.get("item_code", "")).startswith(object_code)
    ]
    if obj_items:
        lines.append(f"指标数量：{len(obj_items)} 个")
        lines.extend(
            f"  - {it['item_code']}: {it['item_name']}（{it.get('row_label', '')} × {it.get('column_label', '')}）"
            for it in obj_items[:30]
        )

    return "\n".join(lines)


def _parse_change_items(raw: object) -> list[ChangeItem]:
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        result.append(
            ChangeItem(
                category=str(item.get("category", "")),
                change=str(item.get("change", "")),
                evidence=str(item.get("evidence", "")),
            )
        )
    return result


def _parse_str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if x]
