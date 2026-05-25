"""手动从填报说明抽取规则卡片 + 候选概念(P1 最简形态)。

设计依据: docs/rule-card-and-concept-kb-design.md 第 6 节(P1 抽取流水线的简化版)。

简化点(相对设计):
- 不建 reg_extraction_job 任务表,直接同步执行
- 不实现三级处置策略,所有候选一律 DRAFT + PENDING(由人工 PATCH review)
- 不做候选/库内现状比对的精细分类(仅按 canonical_name+aliases 去重)
- 不实现 L2/L3,仅抽 L1

MOCK_AI=true 时走预置 mock 数据(基于 doc 段落生成 fake 候选),不调真 LLM。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.db_models import (
    RegConcept,
    RegConceptAlias,
    RegDocument,
    RegReportingRuleCard,
    RegReportingRuleCardConceptMap,
)
from app.services.llm_client import LLMClientError, complete_json


REPORTING_OBJECT_PATTERN = re.compile(r"\b(G[0-9]{1,3}[A-Z]*)\b")


@dataclass
class ExtractionResult:
    document_id: int
    inferred_object_code: str
    rule_cards_created: int
    concepts_created: int
    aliases_created: int
    card_concept_links_created: int
    rule_cards_skipped: int
    concepts_skipped: int
    llm_used: bool
    error_message: str = ""


def extract_from_document(document_id: int, session: Session) -> ExtractionResult:
    """同步抽取入口。读 doc 全文 → LLM 抽 → 落 DRAFT 候选。"""
    doc = session.get(RegDocument, document_id)
    if doc is None:
        raise ValueError(f"Document {document_id} not found")

    parsed_text = (doc.parsed_text or "").strip()
    if not parsed_text:
        return ExtractionResult(
            document_id=document_id,
            inferred_object_code="",
            rule_cards_created=0,
            concepts_created=0,
            aliases_created=0,
            card_concept_links_created=0,
            rule_cards_skipped=0,
            concepts_skipped=0,
            llm_used=False,
            error_message="document has no parsed_text",
        )

    object_code = _infer_object_code(doc)
    settings = get_settings()
    llm_used = False
    if settings.mock_ai:
        payload = _mock_extract(parsed_text, object_code, doc)
    else:
        try:
            payload = _llm_extract(parsed_text, object_code)
            llm_used = True
        except LLMClientError as exc:
            # LLM 失败时退回 mock,保证可演示
            payload = _mock_extract(parsed_text, object_code, doc)
            return _persist(
                payload,
                doc,
                object_code,
                session,
                llm_used=False,
                error_message=f"LLM failed, fell back to mock: {exc}",
            )

    return _persist(payload, doc, object_code, session, llm_used=llm_used)


# --------------------------------------------------------------------------- #
# 推断报表对象 code
# --------------------------------------------------------------------------- #


def _infer_object_code(doc: RegDocument) -> str:
    """从 filename / title 里抓 G\\d+ 代码,抓不到返回空。"""
    sources = [doc.filename or "", doc.title or "", (doc.parsed_text or "")[:200]]
    for src in sources:
        m = REPORTING_OBJECT_PATTERN.search(src)
        if m:
            return m.group(1)
    return ""


# --------------------------------------------------------------------------- #
# MOCK 抽取:不调 LLM,从段落生成 fake 候选(demo 兜底)
# --------------------------------------------------------------------------- #


def _mock_extract(text: str, object_code: str, doc: RegDocument) -> dict:
    """从原文切段,挑头 6 段含"应"/"不"/"统计"/"包括"等规则信号词的段落
    作为 mock 卡片;同时从段落里抽出名词候选作为 mock 概念。
    """
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    rule_signals = ("应", "不应", "不含", "不包括", "包括", "统计", "按口径", "穿透", "纳入", "排除", "口径", "范围")
    candidate_paragraphs = [p for p in paragraphs if any(s in p for s in rule_signals)][:6]
    rule_cards: list[dict] = []
    for idx, p in enumerate(candidate_paragraphs, start=1):
        snippet = p[:160]
        title = _derive_title(p)
        rule_cards.append(
            {
                "title": title,
                "text": snippet,
                "evidence": snippet[:80],
                "location": f"{object_code or 'doc'} 第 {idx} 段(自动定位)",
                "confidence": "MEDIUM",
                "subject_concept": "",
                "object_concept": "",
            }
        )

    # 从段落里抽名词候选(粗粒度:含"余额/资产/口径/类型/项目"的 4-8 字词)
    concept_pattern = re.compile(r"[一-鿿]{2,10}(?:余额|资产|口径|类型|项目|业务|融入|存放|权益|风险|权重)")
    concept_names: list[str] = []
    seen: set[str] = set()
    for p in candidate_paragraphs:
        for match in concept_pattern.findall(p):
            if match in seen:
                continue
            seen.add(match)
            concept_names.append(match)
            if len(concept_names) >= 8:
                break
        if len(concept_names) >= 8:
            break

    concepts: list[dict] = [
        {
            "canonical_name": name,
            "short_definition": f"从 {object_code or doc.filename} 自动抽取的候选概念,请人工补充定义",
            "concept_type": "METRIC" if "余额" in name else "SCOPE",
            "aliases": [name],
        }
        for name in concept_names
    ]
    return {"rule_cards": rule_cards, "concepts": concepts}


def _derive_title(paragraph: str) -> str:
    """从段落首句提取一个短标题(不超过 24 字)。"""
    first_sentence = re.split(r"[。；;]", paragraph, maxsplit=1)[0]
    return first_sentence[:24] or paragraph[:24]


# --------------------------------------------------------------------------- #
# 真 LLM 抽取
# --------------------------------------------------------------------------- #


_EXTRACTION_SYSTEM_PROMPT = """你是 1104 监管报送规则提取专家。请从用户给定的填报说明原文中提取:

1. 报送规则卡片(rule_cards):每条对应填报说明里的一句明确规则,正文不超过 200 字。
   - title: 短标题(<= 24 字)
   - text: 规则正文(可对原文略加润色,保留口径)
   - evidence: 严格从原文摘录,**必须能在原文 substring 匹配到**,不允许编造
   - location: "§X.X 章节名"
   - confidence: HIGH/MEDIUM/LOW
   - subject_concept / object_concept: 该规则的主体/客体术语(中文),若不明显留空

2. 监管概念候选(concepts):规则里用到的名词性术语(主体/客体/口径词)。
   - canonical_name: 规范名(中文)
   - short_definition: 一句话定义(<= 80 字)
   - concept_type: METRIC | SCOPE | CLASSIFICATION | CALCULATION | DIMENSION | ENTITY
   - aliases: 同义说法数组(包含 canonical_name 本身)

返回严格 JSON,无任何其他文本。"""


def _llm_extract(text: str, object_code: str) -> dict:
    """调真 LLM。返回 dict { rule_cards, concepts }。"""
    truncated = text[:6000]
    user_prompt = (
        f"报表对象代码:{object_code or '(未识别)'}\n\n"
        f"填报说明原文(已截断到前 6000 字):\n{truncated}"
    )
    payload, _raw, _model = complete_json(
        [
            {"role": "system", "content": _EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )
    # 防御:有些模型可能在外层包一层 result
    if isinstance(payload, dict) and "rule_cards" not in payload and "result" in payload:
        payload = payload["result"]
    if not isinstance(payload, dict) or "rule_cards" not in payload:
        raise LLMClientError(f"LLM payload missing rule_cards: {json.dumps(payload, ensure_ascii=False)[:200]}")
    return payload


# --------------------------------------------------------------------------- #
# 落库 (DRAFT)
# --------------------------------------------------------------------------- #


def _persist(
    payload: dict,
    doc: RegDocument,
    object_code: str,
    session: Session,
    llm_used: bool,
    error_message: str = "",
) -> ExtractionResult:
    rule_cards_payload = payload.get("rule_cards") or []
    concepts_payload = payload.get("concepts") or []

    # 已有 alias → concept_id 映射,用于命中已存在概念
    existing_aliases = list(session.exec(select(RegConceptAlias)).all())
    alias_to_concept: dict[str, int] = {a.alias_text: a.concept_id for a in existing_aliases}
    existing_concepts = {
        c.canonical_name: c.id
        for c in session.exec(select(RegConcept)).all()
        if c.id is not None
    }

    # 1. 概念候选先入库(规则卡片可能引用它们)
    concepts_created = 0
    concepts_skipped = 0
    aliases_created = 0
    concept_name_to_id: dict[str, int] = dict(existing_concepts)
    for c in concepts_payload:
        name = (c.get("canonical_name") or "").strip()
        if not name:
            continue
        # 命中 canonical_name 或 alias 的视为已存在
        if name in concept_name_to_id:
            concepts_skipped += 1
            existing_id = concept_name_to_id[name]
        elif name in alias_to_concept:
            concepts_skipped += 1
            existing_id = alias_to_concept[name]
            concept_name_to_id[name] = existing_id
        else:
            concept = RegConcept(
                concept_code=_make_concept_code(name, doc.id or 0),
                canonical_name=name,
                short_definition=(c.get("short_definition") or "")[:500],
                full_definition=c.get("short_definition") or "",
                concept_type=_normalize_concept_type(c.get("concept_type")),
                reporting_system_scope="1104" if object_code else "",
                current_version_no=1,
                is_locked=False,
                status="DRAFT",
                created_by="EXTRACT" + ("(LLM)" if llm_used else "(MOCK)"),
            )
            session.add(concept)
            session.flush()
            concept_name_to_id[name] = concept.id  # type: ignore[assignment]
            existing_id = concept.id  # type: ignore[assignment]
            concepts_created += 1

        # 别名(包括 canonical_name 自身)
        aliases = c.get("aliases") or []
        if name not in aliases:
            aliases = [name] + list(aliases)
        for alias in aliases:
            alias = (alias or "").strip()
            if not alias:
                continue
            if alias_to_concept.get(alias) == existing_id:
                continue
            row = session.exec(
                select(RegConceptAlias)
                .where(RegConceptAlias.concept_id == existing_id)
                .where(RegConceptAlias.alias_text == alias)
            ).first()
            if row:
                continue
            session.add(
                RegConceptAlias(
                    concept_id=existing_id,
                    alias_text=alias,
                    alias_source="REGULATION" if llm_used else "INTERNAL",
                    source_document_id=doc.id,
                    evidence_text="auto_extracted",
                )
            )
            alias_to_concept[alias] = existing_id
            aliases_created += 1

    # 2. 规则卡片
    rule_cards_created = 0
    rule_cards_skipped = 0
    card_concept_links_created = 0
    for idx, card in enumerate(rule_cards_payload, start=1):
        title = (card.get("title") or "").strip()
        text = (card.get("text") or "").strip()
        if not title or not text:
            continue
        # 幂等:同 document + 同 title 已有 → 跳过
        dup = session.exec(
            select(RegReportingRuleCard)
            .where(RegReportingRuleCard.source_document_id == doc.id)
            .where(RegReportingRuleCard.card_title == title)
        ).first()
        if dup:
            rule_cards_skipped += 1
            continue

        evidence = (card.get("evidence") or "").strip()
        evidence_verified = bool(evidence) and evidence in (doc.parsed_text or "")
        rule_card = RegReportingRuleCard(
            card_code=_make_card_code(object_code, doc.id or 0, idx),
            reporting_object_code=object_code or None,
            reporting_item_code=None,
            card_level="L1",
            card_title=title[:200],
            card_text=text,
            source_document_id=doc.id,
            source_location=(card.get("location") or "")[:200],
            evidence_text=evidence,
            evidence_verified=evidence_verified,
            confidence_level=(card.get("confidence") or "MEDIUM").upper(),
            review_status="PENDING",
            status="DRAFT",
            created_by="EXTRACT" + ("(LLM)" if llm_used else "(MOCK)"),
            updated_by="EXTRACT" + ("(LLM)" if llm_used else "(MOCK)"),
        )
        session.add(rule_card)
        session.flush()
        rule_cards_created += 1

        # 关联概念(SUBJECT/OBJECT)
        for role_key, role_value in (("subject_concept", "SUBJECT"), ("object_concept", "OBJECT")):
            cname = (card.get(role_key) or "").strip()
            if not cname:
                continue
            cid = concept_name_to_id.get(cname) or alias_to_concept.get(cname)
            if cid is None:
                continue
            existing_link = session.exec(
                select(RegReportingRuleCardConceptMap)
                .where(RegReportingRuleCardConceptMap.card_id == rule_card.id)
                .where(RegReportingRuleCardConceptMap.concept_id == cid)
                .where(RegReportingRuleCardConceptMap.role == role_value)
            ).first()
            if existing_link:
                continue
            session.add(
                RegReportingRuleCardConceptMap(
                    card_id=rule_card.id,
                    concept_id=cid,
                    role=role_value,
                )
            )
            card_concept_links_created += 1

    session.commit()
    return ExtractionResult(
        document_id=doc.id or 0,
        inferred_object_code=object_code,
        rule_cards_created=rule_cards_created,
        concepts_created=concepts_created,
        aliases_created=aliases_created,
        card_concept_links_created=card_concept_links_created,
        rule_cards_skipped=rule_cards_skipped,
        concepts_skipped=concepts_skipped,
        llm_used=llm_used,
        error_message=error_message,
    )


_VALID_CONCEPT_TYPES = {
    "METRIC", "SCOPE", "CLASSIFICATION", "CALCULATION", "DIMENSION", "ENTITY"
}


def _normalize_concept_type(value: str | None) -> str:
    if not value:
        return "METRIC"
    v = value.upper().strip()
    return v if v in _VALID_CONCEPT_TYPES else "METRIC"


def _slugify(text: str) -> str:
    """简单 slug:取拼音难,用 hash + 前 8 个 ascii 字符兜底。"""
    ascii_part = "".join(ch for ch in text if ch.isascii() and ch.isalnum())
    if ascii_part:
        return ascii_part[:24].upper()
    return f"H{abs(hash(text)) % 10**8:08d}"


def _make_concept_code(name: str, doc_id: int) -> str:
    return f"CON_EXTRACT_{doc_id}_{_slugify(name)}"


def _make_card_code(object_code: str, doc_id: int, idx: int) -> str:
    prefix = object_code or "AUTO"
    return f"RC_{prefix}_EXTRACT_{doc_id}_{idx:03d}"
