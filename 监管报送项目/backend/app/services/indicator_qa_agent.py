"""indicator_qa_agent.py

指标问答 Agent 编排层。

两种模式：
- 解释模式：填报说明 RAG + LLM 通俗解释 + 工具数据组合
- 排查模式：监管变更检查 + 血缘追溯 + 假说清单生成

设计原则：
- 排查模式只给假说清单，不给结论
- 业务事件假说固定标注 AI 无法分析
- 解释模式中监管答疑来自 RAG，不 web search（无外网时可靠）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterator

from sqlmodel import Session

from app.services.indicator_qa_tools import (
    get_item_basic_info,
    get_item_lineage,
    get_regulatory_changes,
    get_related_tickets,
    search_instruction_rag,
)
from app.services.llm_client import LLMClientError, complete_json, stream_text


# ──────────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class QARequest:
    question: str
    item_code: str | None = None        # 已知指标编码时传入
    anomaly_value: str | None = None    # 异常数值描述（如 "从 3.2 变成 5.8"）


@dataclass
class Hypothesis:
    label: str              # 假说标题
    status: str             # checked / uncertain / out_of_scope
    evidence: str           # 证据或说明
    action: str = ""        # 建议操作


@dataclass
class QAResponse:
    mode: str               # explanation / anomaly
    item_code: str
    item_name: str
    # 解释模式
    instruction_excerpts: list[dict] = field(default_factory=list)   # RAG 召回原文
    plain_explanation: str = ""                                       # LLM 通俗解释
    key_points: list[str] = field(default_factory=list)              # 口径要点
    # 排查模式
    hypotheses: list[Hypothesis] = field(default_factory=list)
    # 通用
    related_tickets: list[dict] = field(default_factory=list)
    lineage_fields: list[dict] = field(default_factory=list)
    error: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# 意图识别
# ──────────────────────────────────────────────────────────────────────────────

_ANOMALY_KEYWORDS = frozenset([
    "异常", "差异", "波动", "跌了", "涨了", "变化大", "偏差", "不对", "问题",
    "为什么", "原因", "排查", "分析", "检查",
])
_EXPLAIN_KEYWORDS = frozenset([
    "什么意思", "怎么填", "口径", "定义", "计算", "解释", "说明", "含义",
    "怎么算", "包含", "范围", "区别",
])


def _detect_intent(question: str) -> str:
    """返回 'anomaly' 或 'explanation'（默认）。"""
    q = question.lower()
    has_anomaly = any(kw in q for kw in _ANOMALY_KEYWORDS)
    has_explain = any(kw in q for kw in _EXPLAIN_KEYWORDS)

    if has_anomaly and not has_explain:
        return "anomaly"
    return "explanation"


def _extract_item_code(question: str) -> str | None:
    """尝试从问题文本中提取 item_code（如 G31.PART_I.BOND_INVESTMENT_BALANCE）。"""
    m = re.search(r'G\d+[._][A-Z0-9_.]+', question.upper())
    return m.group() if m else None


def _extract_object_codes(question: str, item_code: str) -> list[str] | None:
    """从 item_code 或问题文本中提取报表代码（如 ['G31']），用于限制 RAG 搜索范围。
    返回 None 表示不限制。"""
    # 优先从 item_code 提取
    if item_code:
        m = re.match(r'(G\d+)', item_code.upper())
        if m:
            return [m.group(1)]
    # 其次从问题里找 G01/G24/G25/G27/G31 等报表代码
    found = re.findall(r'\bG\d{2}\b', question.upper())
    if found:
        return list(dict.fromkeys(found))  # 去重保序
    return None


def _extract_cn_phrase(question: str) -> str:
    """从问题文本中提取最可能是指标名的中文词组，作为 keyword_hint 兜底。

    例："G31 修正久期怎么计算？" → "修正久期"

    策略：去掉报表代码和常见问法动词后，取最长连续中文词组。
    """
    # 先去掉 GXX 报表代码
    text = re.sub(r'\bG\d{2}\b', '', question)
    # 去掉常见问法词（疑问词 + 动词后缀）
    _QUERY_WORDS = (
        "怎么计算", "怎么填", "怎么理解", "是什么", "是什么意思", "怎么样", "如何",
        "怎么", "什么", "取值", "异常", "计算方法", "口径", "含义", "填法",
    )
    for w in sorted(_QUERY_WORDS, key=len, reverse=True):  # 长词先替换
        text = text.replace(w, " ")
    phrases = re.findall(r'[一-鿿]{2,10}', text)
    if not phrases:
        return ""
    return max(phrases, key=len)


# ──────────────────────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────────────────────

def run_indicator_qa(request: QARequest, session: Session) -> QAResponse:
    """运行指标问答 Agent，返回结构化回答。"""

    # 意图识别
    mode = _detect_intent(request.question)

    # 确定 item_code（优先用请求中的，其次从问题中提取）
    item_code = request.item_code or _extract_item_code(request.question) or ""

    # 基本信息
    basic = get_item_basic_info(item_code, session) if item_code else {"found": False}
    item_name = basic.get("item_name", "") or item_code

    resp = QAResponse(mode=mode, item_code=item_code, item_name=item_name)

    if mode == "explanation":
        _run_explanation_mode(request, basic, resp, session)
    else:
        _run_anomaly_mode(request, basic, resp, session)

    return resp


# ──────────────────────────────────────────────────────────────────────────────
# 解释模式
# ──────────────────────────────────────────────────────────────────────────────

def _run_explanation_mode(
    request: QARequest,
    basic: dict,
    resp: QAResponse,
    session: Session,
) -> None:
    # 1. RAG 召回填报说明
    # 优先用 item 所属报表，其次从问题文本里提取报表代码，避免跨报表串扰
    object_codes = (
        [basic["object_code"]] if basic.get("object_code")
        else _extract_object_codes(request.question, resp.item_code)
    )
    chunks = search_instruction_rag(
        query=request.question,
        object_codes=object_codes,
        top_k=5,
        session=session,
        # 指标名：优先已解析的 item_name，否则从问题里提取2字以上中文词组
        keyword_hint=resp.item_name or _extract_cn_phrase(request.question),
    )
    # 过滤低质量 semantic 块
    # - 有精确/关键词命中时，语义块阈值 0.75（严格）
    # - 全部为语义命中时，阈值 0.6（宽松，总比空好）
    has_strong = any(c.get("match_type") in ("exact", "keyword") for c in chunks)
    sem_threshold = 0.75 if has_strong else 0.60
    resp.instruction_excerpts = [
        c for c in chunks
        if c.get("match_type") in ("exact", "keyword") or c.get("score", 0) >= sem_threshold
    ]

    # 2. 相关工单历史
    if resp.item_code:
        resp.related_tickets = get_related_tickets(resp.item_code, session)

    # 3. LLM 生成通俗解释 + 口径要点（无 RAG 也调，降级为通用知识回答）
    excerpts_text = "\n\n".join(
        f"【{c['source_label']}】\n{c['chunk_text']}" for c in chunks[:3]
    ) if chunks else ""
    resp.plain_explanation, resp.key_points = _llm_explain(
        question=request.question,
        item_name=resp.item_name,
        excerpts=excerpts_text,
    )


def _llm_explain(question: str, item_name: str, excerpts: str) -> tuple[str, list[str]]:
    """调 LLM 生成通俗解释和口径要点。"""
    messages = [
        {
            "role": "system",
            "content": (
                "你是一名银行监管报送专家，帮助业务人员理解指标含义和填报要求。"
                "请严格按 JSON 格式输出，不要输出任何其他内容。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"问题：{question}\n"
                f"指标名称：{item_name}\n\n"
                + (f"填报说明相关原文：\n{excerpts}\n\n请优先基于以上原文回答。\n\n" if excerpts else "（暂无填报说明原文，请基于通用金融知识回答）\n\n")
                + f"请输出 JSON：\n"
                f'{{"plain_explanation": "用2-3句话通俗解释该指标（面向非技术业务人员）",'
                f'"key_points": ["口径要点1", "口径要点2", "口径要点3"]}}'
            ),
        },
    ]
    try:
        data, _raw, _model = complete_json(messages)
        explanation = data.get("plain_explanation", "") if isinstance(data, dict) else ""
        key_points = data.get("key_points", []) if isinstance(data, dict) else []
        return explanation, key_points
    except LLMClientError:
        return "（LLM 服务暂不可用，请直接参考上方填报说明原文）", []


# ──────────────────────────────────────────────────────────────────────────────
# 排查模式
# ──────────────────────────────────────────────────────────────────────────────

def _run_anomaly_mode(
    request: QARequest,
    basic: dict,
    resp: QAResponse,
    session: Session,
) -> None:
    hypotheses: list[Hypothesis] = []

    # 假说 1：监管口径近期变化
    hyp1 = _check_regulatory_change(resp.item_code, session)
    hypotheses.append(hyp1)

    # 假说 2：血缘上游数据质量
    hyp2, lineage_fields = _check_lineage_quality(resp.item_code, session)
    hypotheses.append(hyp2)
    resp.lineage_fields = lineage_fields

    # 假说 3：同表指标同向异动（有用户提供数值时展示）
    if request.anomaly_value:
        hypotheses.append(Hypothesis(
            label="同表相关指标同向异动",
            status="uncertain",
            evidence=f"用户描述：{request.anomaly_value}。建议人工比对同表其他指标是否同向变化。",
            action="手动比对同报表内关联指标的同期变化方向。",
        ))

    # 假说 4：业务事件（固定标注 AI 无法分析）
    hypotheses.append(Hypothesis(
        label="业务事件（超出 AI 分析范围）",
        status="out_of_scope",
        evidence=(
            "业务事件（大额交易、新产品上线、客户结构变化等）需结合业务系统数据判断，"
            "本 AI 无法访问业务源系统。"
        ),
        action="与业务条线确认本期是否有异常业务发生。",
    ))

    resp.hypotheses = hypotheses
    resp.related_tickets = get_related_tickets(resp.item_code, session) if resp.item_code else []


def _check_regulatory_change(item_code: str, session: Session) -> Hypothesis:
    if not item_code:
        return Hypothesis(
            label="监管口径近期变化",
            status="uncertain",
            evidence="未能识别指标编码，无法查询变更记录。",
        )

    changes = get_regulatory_changes(item_code, session)
    if changes:
        recent = changes[0]
        summary = recent.get("change_summary") or "有变更记录，请查看关联工单"
        ticket_ref = f"（工单 #{recent['ticket_id']}）" if recent.get("ticket_id") else ""
        return Hypothesis(
            label="监管口径近期变化",
            status="checked",
            evidence=f"发现 {len(changes)} 条变更记录。最近一条：{summary}{ticket_ref}",
            action="查看关联工单，确认口径变化是否导致数值差异。",
        )
    return Hypothesis(
        label="监管口径近期变化",
        status="checked",
        evidence="知识库中无该指标的近期变更记录，可排除此假说。",
    )


def _check_lineage_quality(item_code: str, session: Session) -> tuple[Hypothesis, list[dict]]:
    if not item_code:
        return Hypothesis(
            label="血缘上游数据质量问题",
            status="uncertain",
            evidence="未能识别指标编码，无法查询血缘。",
        ), []

    lineage = get_item_lineage(item_code, session)
    fields = lineage.get("fields", [])

    if not fields:
        return Hypothesis(
            label="血缘上游数据质量问题",
            status="uncertain",
            evidence="知识库中该指标无血缘记录，无法追溯上游数据。建议先补录血缘。",
            action="补录血缘后重新排查。",
        ), []

    field_list = "、".join(f"{f['field_name']}（{f['system_name']}）" for f in fields[:3])
    if len(fields) > 3:
        field_list += f" 等 {len(fields)} 个字段"

    return Hypothesis(
        label="血缘上游数据质量问题",
        status="checked",
        evidence=f"该指标来源字段：{field_list}。建议核查这些字段本期数据是否存在质量问题。",
        action="联系相关系统团队核查源字段数据质量，检查 ETL 是否有异常。",
    ), fields


# ──────────────────────────────────────────────────────────────────────────────
# 流式入口
# ──────────────────────────────────────────────────────────────────────────────

def _sse(payload: dict) -> str:
    """生成一行 SSE data。"""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def run_indicator_qa_stream(request: QARequest, session) -> Iterator[str]:
    """流式问答入口，yield SSE 文本行。

    事件序列：
      meta       → {mode, item_code, item_name, instruction_excerpts, related_tickets}
      token      → {text}  （LLM 流式 token，仅解释模式）
      keypoints  → {data: [...]}
      hypotheses → {data: [...]}  （仅排查模式）
      lineage    → {data: [...]}  （排查模式，有血缘时）
      done       → {}
      error      → {message}
    """
    try:
        mode = _detect_intent(request.question)
        item_code = request.item_code or _extract_item_code(request.question) or ""
        basic = get_item_basic_info(item_code, session) if item_code else {"found": False}
        item_name = basic.get("item_name", "") or item_code

        # ── 解释模式 ──────────────────────────────────────────────────────────
        if mode == "explanation":
            # 1. RAG 召回（快）
            object_codes = (
                [basic["object_code"]] if basic.get("object_code")
                else _extract_object_codes(request.question, item_code)
            )
            chunks = search_instruction_rag(
                query=request.question,
                object_codes=object_codes,
                top_k=5,
                session=session,
                keyword_hint=item_name or _extract_cn_phrase(request.question),
            )
            has_strong = any(c.get("match_type") in ("exact", "keyword") for c in chunks)
            sem_threshold = 0.75 if has_strong else 0.60
            excerpts = [
                c for c in chunks
                if c.get("match_type") in ("exact", "keyword") or c.get("score", 0) >= sem_threshold
            ]

            related_tickets = get_related_tickets(item_code, session) if item_code else []

            # 2. 立即发送 meta（用户马上看到 RAG 原文）
            yield _sse({
                "type": "meta",
                "mode": mode,
                "item_code": item_code,
                "item_name": item_name,
                "instruction_excerpts": [
                    {
                        "text": c.get("chunk_text", ""),
                        "source_label": c.get("source_label", ""),
                        "item_name": c.get("item_name", ""),
                        "field_tag": c.get("field_tag", ""),
                        "match_type": c.get("match_type", "semantic"),
                        "score": c.get("score"),
                    }
                    for c in excerpts
                ],
                "related_tickets": related_tickets,
            })

            # 3. 流式输出 plain_explanation
            excerpts_text = "\n\n".join(
                f"【{c['source_label']}】\n{c['chunk_text']}" for c in excerpts[:3]
            ) if excerpts else ""
            messages = _build_explain_messages(request.question, item_name, excerpts_text)

            try:
                for token in stream_text(messages):
                    yield _sse({"type": "token", "text": token})
            except LLMClientError:
                yield _sse({"type": "token", "text": "（LLM 服务暂不可用，请直接参考上方填报说明原文）"})

            # 4. 发送 key_points（非流式，快速 JSON 调用）
            try:
                kp_messages = _build_keypoints_messages(request.question, item_name, excerpts_text)
                data, _, _ = complete_json(kp_messages)
                key_points = data.get("key_points", []) if isinstance(data, dict) else []
            except LLMClientError:
                key_points = []
            yield _sse({"type": "keypoints", "data": key_points})

        # ── 排查模式 ──────────────────────────────────────────────────────────
        else:
            # 排查模式无需流式，直接计算后一次性发送
            resp = QAResponse(mode=mode, item_code=item_code, item_name=item_name)
            _run_anomaly_mode(request, basic, resp, session)

            yield _sse({
                "type": "meta",
                "mode": mode,
                "item_code": item_code,
                "item_name": item_name,
                "instruction_excerpts": [],
                "related_tickets": [],
            })
            yield _sse({"type": "hypotheses", "data": [
                {"label": h.label, "status": h.status,
                 "evidence": h.evidence, "action": h.action}
                for h in resp.hypotheses
            ]})
            if resp.lineage_fields:
                yield _sse({"type": "lineage", "data": resp.lineage_fields})

        yield _sse({"type": "done"})

    except Exception as exc:  # noqa: BLE001
        yield _sse({"type": "error", "message": str(exc)})


def _build_explain_messages(question: str, item_name: str, excerpts: str) -> list[dict]:
    """构造流式解释模式的 messages（输出纯文本，不要 JSON）。"""
    return [
        {
            "role": "system",
            "content": "你是一名银行监管报送专家，帮助业务人员理解指标含义和填报要求。用简洁的中文直接回答，不要输出 JSON 或 Markdown 标题，2-4 句话。",
        },
        {
            "role": "user",
            "content": (
                f"问题：{question}\n指标名称：{item_name}\n\n"
                + (f"填报说明相关原文：\n{excerpts}\n\n请优先基于以上原文回答。" if excerpts
                   else "（暂无填报说明原文，请基于通用金融知识回答）")
            ),
        },
    ]


def _build_keypoints_messages(question: str, item_name: str, excerpts: str) -> list[dict]:
    """构造口径要点的 messages（JSON 输出）。"""
    return [
        {
            "role": "system",
            "content": "你是银行监管报送专家。请严格按 JSON 格式输出，不要输出任何其他内容。",
        },
        {
            "role": "user",
            "content": (
                f"问题：{question}\n指标名称：{item_name}\n\n"
                + (f"填报说明原文：\n{excerpts}\n\n" if excerpts else "")
                + '请输出 JSON：{"key_points": ["要点1", "要点2", "要点3"]}'
            ),
        },
    ]
