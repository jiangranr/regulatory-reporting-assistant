"""多路概念召回 service。

设计依据：docs/concept-and-ticket-reuse-design.md §3 补丁 A。

三路召回 + 加权聚合：
  路 1 alias substring（长别名优先 + 占用区间避重叠）— 沿用既有逻辑，确定性
  路 2 definition substring（短/全定义切片 ≥4 字字面命中）— 轻量加强
  路 4 embedding 余弦相似度 — 真正解决同义改写（"拆放同业" → 同业融入余额）

降级策略：
  - 路 4 没建库 / API 未配 / 调用失败 → 静默跳过，依赖路 1+2，**不阻塞**
  - 三路任意命中均产出 ConceptMatchHit，与既有 routes_concepts.match_concepts 输出结构完全一致

向后兼容：
  - 当 enable_embedding=False（默认 False，由 routes 决定开关）且向量表为空时，
    ConceptMatcher 的输出与既有 routes_concepts.match_concepts **逐字段等价**
  - 这是 W1 平滑切换的基础：先把代码搬过来跑通既有 eval，再 enable embedding 上新路

为什么独立成 service：
  - routes_concepts.py 现在的 match_concepts 把召回 + 报送项辐射 + 排序混在一起
  - 抽到 ConceptMatcher 后：未来加路 5/6/7 只需注册新的 _recall_via_xxx 方法
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass, field
from typing import Iterable

from sqlmodel import Session, select

from app.models.db_models import (
    RegConcept,
    RegConceptAlias,
    RegConceptEmbedding,
    RegConceptReportingItemMap,
)
from app.models.schemas import ConceptMatchHit
from app.services.llm_client import LLMClientError, embed_texts

# ── 序列化 ─────────────────────────────────────────────────────────────


def serialize_vector(vec: list[float]) -> bytes:
    """float32 小端序列化，存进 RegConceptEmbedding.vector。"""
    return struct.pack(f"<{len(vec)}f", *vec)


def deserialize_vector(raw: bytes) -> list[float]:
    """反序列化向量。dim 通过字节长度推断（每个 float32 = 4 字节）。"""
    dim = len(raw) // 4
    if dim == 0:
        return []
    return list(struct.unpack(f"<{dim}f", raw))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """标准余弦相似度。零向量或维度不匹配返回 0.0。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


# ── 候选数据结构 ───────────────────────────────────────────────────────


@dataclass
class _Candidate:
    """召回候选项的内部表示。在多路命中时积累 score 与 paths。"""

    concept_id: int
    concept_code: str
    canonical_name: str
    matched_alias: str = ""
    match_offset: int = -1  # -1 表示该 concept 不是通过字面命中（仅 embedding 召回）
    match_length: int = 0
    paths: set[str] = field(default_factory=set)
    score: float = 0.0


# ── 主类 ──────────────────────────────────────────────────────────────


# 各路在 _Candidate.score 上的权重。alias 命中是确定性最高的信号；
# embedding 按相似度加权，单条最高 ≈ 2 分（cosine=1）；definition 是弱信号
_SCORE_ALIAS = 3.0
_SCORE_EMBEDDING_MAX = 2.0
_SCORE_DEFINITION = 1.0

# embedding 路的最小相似度阈值；低于此值不进候选
_EMBEDDING_MIN_SIM = 0.55
# embedding 路单次召回上限（防止低分大面积召回污染结果）
_EMBEDDING_TOP_K = 10


class ConceptMatcher:
    """多路概念召回器。

    使用方式：
        matcher = ConceptMatcher(session, enable_embedding=True)
        hits = matcher.match(text="...", scope="1104", top_k=20)
    """

    def __init__(self, session: Session, enable_embedding: bool = False):
        self.session = session
        self.enable_embedding = enable_embedding

    # ------------------------------------------------------------------
    def match(
        self,
        text: str,
        scope: str | None = None,
        top_k: int = 20,
    ) -> list[ConceptMatchHit]:
        text = text or ""
        if not text:
            return []

        concept_query = select(RegConcept).where(RegConcept.status == "ACTIVE")
        if scope:
            concept_query = concept_query.where(
                (RegConcept.reporting_system_scope == scope)
                | (RegConcept.reporting_system_scope == "CROSS")
            )
        concepts = list(self.session.exec(concept_query).all())
        concept_by_id: dict[int, RegConcept] = {
            c.id: c for c in concepts if c.id is not None
        }
        if not concept_by_id:
            return []

        candidates: dict[int, _Candidate] = {}

        # 路 1：alias substring
        self._recall_via_alias(text, concept_by_id, candidates)
        # 路 2：definition substring
        self._recall_via_definition(text, concept_by_id, candidates)
        # 路 4：embedding cosine similarity
        if self.enable_embedding:
            self._recall_via_embedding(text, concept_by_id, candidates)

        # 排序：先按 score desc，再按 match_offset asc（字面命中靠前）
        sorted_cands = sorted(
            candidates.values(),
            key=lambda c: (
                -c.score,
                c.match_offset if c.match_offset >= 0 else 10**9,
            ),
        )[:top_k]

        return self._build_hits(sorted_cands)

    # ── 路 1：alias substring（沿用 routes_concepts 旧逻辑） ──────
    def _recall_via_alias(
        self,
        text: str,
        concept_by_id: dict[int, RegConcept],
        candidates: dict[int, _Candidate],
    ) -> None:
        aliases = list(
            self.session.exec(
                select(RegConceptAlias).where(
                    RegConceptAlias.concept_id.in_(concept_by_id.keys())
                )
            ).all()
        )
        # 长别名优先，避免"同业融入"先匹掉而漏了"同业融入余额"
        aliases.sort(key=lambda a: len(a.alias_text), reverse=True)

        consumed_spans: list[tuple[int, int]] = []
        for alias in aliases:
            # 同一概念只算一次 alias 命中
            if alias.concept_id in candidates and "alias" in candidates[alias.concept_id].paths:
                continue
            offset = text.find(alias.alias_text)
            if offset < 0:
                continue
            end = offset + len(alias.alias_text)
            if any(s <= offset < e or s < end <= e for s, e in consumed_spans):
                continue

            cand = candidates.get(alias.concept_id)
            if cand is None:
                concept = concept_by_id[alias.concept_id]
                cand = _Candidate(
                    concept_id=alias.concept_id,
                    concept_code=concept.concept_code,
                    canonical_name=concept.canonical_name,
                )
                candidates[alias.concept_id] = cand
            cand.paths.add("alias")
            cand.matched_alias = alias.alias_text
            cand.match_offset = offset
            cand.match_length = len(alias.alias_text)
            cand.score += _SCORE_ALIAS
            consumed_spans.append((offset, end))

    # ── 路 2：definition substring ─────────────────────────────────
    def _recall_via_definition(
        self,
        text: str,
        concept_by_id: dict[int, RegConcept],
        candidates: dict[int, _Candidate],
    ) -> None:
        """从每个概念的 short_definition / full_definition 中切出长度 ≥4 的片段，
        若 text 包含该片段，则视为弱命中。

        切片策略：按中文常见分隔符切，去空。这样"商业银行向其他金融机构融入资金的余额"
        会被切成 ["商业银行向其他金融机构融入资金的余额"]，整段在 text 里出现概率低；
        实际中更可能匹配的是用户复制粘贴定义片段时（罕见）。这条路主要是兜底，
        真正的同义改写靠路 4。
        """
        splitter = re.compile(r"[，。、；,.;\s（）()\[\]【】「」\"\"《》]+")
        for concept_id, concept in concept_by_id.items():
            for definition in (concept.short_definition, concept.full_definition):
                if not definition or len(definition) < 4:
                    continue
                hit = False
                for frag in splitter.split(definition):
                    frag = frag.strip()
                    if len(frag) < 4:
                        continue
                    if frag in text:
                        cand = candidates.get(concept_id)
                        if cand is None:
                            cand = _Candidate(
                                concept_id=concept_id,
                                concept_code=concept.concept_code,
                                canonical_name=concept.canonical_name,
                            )
                            candidates[concept_id] = cand
                        if "definition" not in cand.paths:
                            cand.paths.add("definition")
                            cand.score += _SCORE_DEFINITION
                            if cand.match_offset < 0:
                                cand.matched_alias = frag
                                cand.match_offset = text.find(frag)
                                cand.match_length = len(frag)
                        hit = True
                        break
                if hit:
                    break

    # ── 路 4：embedding 余弦相似度 ────────────────────────────────
    def _recall_via_embedding(
        self,
        text: str,
        concept_by_id: dict[int, RegConcept],
        candidates: dict[int, _Candidate],
    ) -> None:
        """对 text 嵌入，与所有 ACTIVE 概念的预存向量做余弦相似度排序，
        取 top _EMBEDDING_TOP_K 加入候选。

        降级：
          - 向量表为空（未跑 rebuild_concept_embeddings）→ 静默跳过
          - embed_texts 调用失败（API 挂了 / 限流 / key 错）→ 静默跳过，写日志
        """
        rows = list(
            self.session.exec(
                select(RegConceptEmbedding).where(
                    RegConceptEmbedding.concept_id.in_(concept_by_id.keys())
                )
            ).all()
        )
        if not rows:
            return  # 没建库，路 4 退场

        try:
            query_vec = embed_texts([text])[0]
        except LLMClientError:
            # 不向上抛，让 /match 至少能返回路 1+2 的结果
            return

        # 计算相似度
        scored: list[tuple[int, float]] = []
        for row in rows:
            vec = deserialize_vector(row.vector)
            sim = cosine_similarity(query_vec, vec)
            if sim >= _EMBEDDING_MIN_SIM:
                scored.append((row.concept_id, sim))
        scored.sort(key=lambda x: -x[1])

        for concept_id, sim in scored[:_EMBEDDING_TOP_K]:
            cand = candidates.get(concept_id)
            if cand is None:
                concept = concept_by_id.get(concept_id)
                if concept is None:
                    continue
                cand = _Candidate(
                    concept_id=concept_id,
                    concept_code=concept.concept_code,
                    canonical_name=concept.canonical_name,
                )
                candidates[concept_id] = cand
            cand.paths.add("embedding")
            cand.score += _SCORE_EMBEDDING_MAX * sim

    # ── 构造响应 ──────────────────────────────────────────────────
    def _build_hits(self, candidates: Iterable[_Candidate]) -> list[ConceptMatchHit]:
        cands = list(candidates)
        if not cands:
            return []

        ids = [c.concept_id for c in cands]
        item_maps = list(
            self.session.exec(
                select(RegConceptReportingItemMap).where(
                    RegConceptReportingItemMap.concept_id.in_(ids)
                )
            ).all()
        )
        items_by_concept: dict[int, list[str]] = {}
        for mapping in item_maps:
            items_by_concept.setdefault(mapping.concept_id, []).append(
                mapping.reporting_item_code
            )

        hits: list[ConceptMatchHit] = []
        for cand in cands:
            hits.append(
                ConceptMatchHit(
                    concept_code=cand.concept_code,
                    canonical_name=cand.canonical_name,
                    matched_alias=cand.matched_alias or cand.canonical_name,
                    match_offset=max(cand.match_offset, 0),
                    match_length=cand.match_length,
                    related_reporting_item_codes=items_by_concept.get(
                        cand.concept_id, []
                    ),
                )
            )
        return hits


# ── 便利函数 ─────────────────────────────────────────────────────────


def get_concept_matcher(session: Session, enable_embedding: bool | None = None) -> ConceptMatcher:
    """工厂函数。

    enable_embedding=None 时，根据 settings.embedding_api_key 是否配置自动决定：
      - 已配置 → enable
      - 未配置 → disable（降级为路 1+2，与既有 match_concepts 行为接近）
    """
    if enable_embedding is None:
        from app.core.config import get_settings

        settings = get_settings()
        enable_embedding = bool(settings.embedding_api_key and settings.embedding_api_base)
    return ConceptMatcher(session=session, enable_embedding=enable_embedding)


def build_concept_source_text(concept: RegConcept) -> str:
    """构造用于喂给 embedding 模型的 source_text。

    策略：canonical_name + 短定义。短定义已包含核心语义，加上规范名可锚定。
    full_definition 不进 source_text 以避免噪声主导 embedding。
    """
    name = concept.canonical_name or ""
    short = concept.short_definition or ""
    if not short:
        return name
    return f"{name}：{short}"
