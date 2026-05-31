"""source_recommender.py

新增指标来源推荐引擎。

设计原则（对照 ai-enhancement-design.md §3）：
- 不做"三层级联+置信度阈值"的表面工程
- 实际流程：关键词+语义双路搜索候选字段 → LLM 推理排序 → 输出带 reasoning 的推荐
- 输出 reasoning 是文本说明，不是伪精确的数字置信度
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.db_models import DataFieldCatalog, DataFieldEmbedding, DataSystemCatalog
from app.services.llm_client import LLMClientError, complete_json, embed_texts


# ──────────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SourceCandidate:
    field_code: str
    field_name: str
    table_name: str
    system_code: str
    system_name: str
    business_meaning: str
    reasoning: str          # LLM 生成的推理说明
    match_method: str       # "keyword" | "semantic" | "llm"


@dataclass
class SourceRecommendResult:
    item_code: str
    item_name: str
    definition: str
    candidates: list[SourceCandidate] = field(default_factory=list)
    unresolved: bool = False        # 三路均无候选时为 True
    escalate_to_human: bool = False  # 可能需要接入新数据源


# ──────────────────────────────────────────────────────────────────────────────
# 公开接口
# ──────────────────────────────────────────────────────────────────────────────

def recommend_source(
    item_code: str,
    item_name: str,
    definition: str,
    session: Session,
    top_k: int = 3,
) -> SourceRecommendResult:
    """为新增指标推荐数据来源字段。

    流程：
    1. 关键词匹配 DataFieldCatalog（快，覆盖 business_meaning 和 field_name）
    2. 语义搜索 DataFieldEmbedding（embedding 可用时）
    3. 合并候选去重，调 LLM 对 top 候选生成 reasoning 并排序
    """
    result = SourceRecommendResult(
        item_code=item_code,
        item_name=item_name,
        definition=definition,
    )

    # Step 1：关键词候选
    keyword_candidates = _keyword_search(item_name, definition, session, top_n=10)

    # Step 2：语义候选（embedding 不可用时降级为纯关键词结果）
    semantic_candidates = _semantic_search(item_name + " " + definition, session, top_n=10)

    # Step 3：合并去重
    seen: set[str] = set()
    merged: list[DataFieldCatalog] = []
    for f in keyword_candidates + semantic_candidates:
        if f.field_code not in seen:
            seen.add(f.field_code)
            merged.append(f)

    if not merged:
        result.unresolved = True
        result.escalate_to_human = True
        return result

    # Step 4：LLM 推理排序（截取前 top_k*3 条送给 LLM，避免上下文过长）
    candidates = _llm_rank_and_reason(
        item_name=item_name,
        definition=definition,
        fields=merged[: top_k * 3],
        session=session,
        top_k=top_k,
    )

    result.candidates = candidates
    result.unresolved = len(candidates) == 0
    result.escalate_to_human = result.unresolved
    return result


def build_field_embeddings(session: Session, force_rebuild: bool = False) -> dict:
    """为 DataFieldCatalog 所有字段构建 embedding 索引。

    Returns:
        {total, written, skipped, errors}
    """
    from app.core.config import get_settings
    settings = get_settings()

    stats = {"total": 0, "written": 0, "skipped": 0, "errors": []}
    fields = session.exec(select(DataFieldCatalog)).all()
    stats["total"] = len(fields)

    for f in fields:
        if f.id is None:
            continue

        # 检查是否已有 embedding
        if not force_rebuild:
            existing = session.exec(
                select(DataFieldEmbedding).where(DataFieldEmbedding.field_id == f.id)
            ).first()
            if existing:
                stats["skipped"] += 1
                continue

        text = f"{f.field_name} {f.business_meaning or ''}"
        try:
            vecs = embed_texts([text])
            vec = vecs[0]
        except LLMClientError as e:
            stats["errors"].append(f"{f.field_code}: {e}")
            continue

        emb_bytes = struct.pack(f"<{len(vec)}f", *vec)

        existing = session.exec(
            select(DataFieldEmbedding).where(DataFieldEmbedding.field_id == f.id)
        ).first()
        if existing:
            existing.embedding = emb_bytes
            existing.model_version = settings.embedding_model
            session.add(existing)
        else:
            session.add(DataFieldEmbedding(
                field_id=f.id,
                embedding=emb_bytes,
                model_version=settings.embedding_model,
            ))
        stats["written"] += 1

    session.commit()
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# 内部：关键词搜索
# ──────────────────────────────────────────────────────────────────────────────

def _keyword_search(
    item_name: str,
    definition: str,
    session: Session,
    top_n: int = 10,
) -> list[DataFieldCatalog]:
    import re
    text = item_name + " " + definition
    words = re.findall(r'[一-鿿]{2,6}', text)
    stop = {"余额", "金额", "填报", "机构", "数据", "管理", "情况", "投资", "按照", "期末",
            "是指", "包括", "填报", "报表", "监管", "规定", "合计"}
    keywords = [w for w in set(words) if w not in stop]

    if not keywords:
        return []

    all_fields = session.exec(select(DataFieldCatalog)).all()
    scored: list[tuple[int, DataFieldCatalog]] = []
    for f in all_fields:
        score = sum(
            1 for kw in keywords
            if kw in (f.business_meaning or "") or kw in (f.field_name or "")
        )
        if score > 0:
            scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:top_n]]


# ──────────────────────────────────────────────────────────────────────────────
# 内部：语义搜索
# ──────────────────────────────────────────────────────────────────────────────

def _semantic_search(
    query: str,
    session: Session,
    top_n: int = 10,
) -> list[DataFieldCatalog]:
    try:
        query_vec = embed_texts([query])[0]
    except LLMClientError:
        return []

    embs = session.exec(select(DataFieldEmbedding)).all()
    if not embs:
        return []

    dim = len(query_vec)
    scored: list[tuple[float, int]] = []
    for emb in embs:
        if not emb.embedding:
            continue
        vec = list(struct.unpack(f"<{len(emb.embedding)//4}f", emb.embedding))
        if len(vec) != dim:
            continue
        sim = _cosine(query_vec, vec)
        scored.append((sim, emb.field_id))

    scored.sort(reverse=True)

    fields: list[DataFieldCatalog] = []
    for _, field_id in scored[:top_n]:
        f = session.get(DataFieldCatalog, field_id)
        if f:
            fields.append(f)
    return fields


# ──────────────────────────────────────────────────────────────────────────────
# 内部：LLM 推理排序
# ──────────────────────────────────────────────────────────────────────────────

def _llm_rank_and_reason(
    item_name: str,
    definition: str,
    fields: list[DataFieldCatalog],
    session: Session,
    top_k: int = 3,
) -> list[SourceCandidate]:
    """让 LLM 读候选字段列表 + 指标定义，输出排序后的推荐及推理说明。"""

    # 构建系统描述 map
    system_map = _get_system_map(session)

    # 构建候选字段描述
    field_lines = []
    for i, f in enumerate(fields):
        sys_name = system_map.get(f.data_system_id, {}).get("name", "未知系统")
        field_lines.append(
            f"{i+1}. [{f.field_code}] {f.field_name}（{sys_name} / {f.table_name}）"
            f"  业务含义：{f.business_meaning or '无描述'}"
        )
    fields_text = "\n".join(field_lines)

    messages = [
        {
            "role": "system",
            "content": (
                "你是一名银行监管数据专家，熟悉 1104 报表体系和银行数据架构。"
                "请严格按要求输出 JSON，不要输出任何其他内容。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"以下是一个新监管报送指标，请从候选源字段中推荐最合适的 {top_k} 个，并说明理由。\n\n"
                f"## 新指标\n- 名称：{item_name}\n- 定义：{definition}\n\n"
                f"## 候选源字段\n{fields_text}\n\n"
                f"## 输出格式（JSON 数组）\n"
                f'[{{"field_code": "字段编码", "reasoning": "一句话推荐理由（30字以内）"}}]'
            ),
        },
    ]

    try:
        data, _raw, _model = complete_json(messages)
        # complete_json 直接返回 json.loads(content)；LLM 输出数组时 data 就是 list
        items = data if isinstance(data, list) else [data]
    except Exception:
        # LLM 失败时直接用关键词结果，不附推理
        return [
            SourceCandidate(
                field_code=f.field_code,
                field_name=f.field_name,
                table_name=f.table_name,
                system_code=str(f.data_system_id),
                system_name=system_map.get(f.data_system_id, {}).get("name", ""),
                business_meaning=f.business_meaning or "",
                reasoning="关键词匹配（LLM 推理不可用）",
                match_method="keyword",
            )
            for f in fields[:top_k]
        ]

    # 拼装结果
    code_to_field = {f.field_code: f for f in fields}
    candidates: list[SourceCandidate] = []
    for item in items[:top_k]:
        fc = item.get("field_code", "")
        f = code_to_field.get(fc)
        if f is None:
            continue
        sys_info = system_map.get(f.data_system_id, {})
        candidates.append(SourceCandidate(
            field_code=f.field_code,
            field_name=f.field_name,
            table_name=f.table_name,
            system_code=sys_info.get("code", ""),
            system_name=sys_info.get("name", ""),
            business_meaning=f.business_meaning or "",
            reasoning=item.get("reasoning", ""),
            match_method="llm",
        ))
    return candidates


def _get_system_map(session: Session) -> dict[int, dict]:
    systems = session.exec(select(DataSystemCatalog)).all()
    return {s.id: {"code": s.system_code, "name": s.system_name} for s in systems if s.id}


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)
