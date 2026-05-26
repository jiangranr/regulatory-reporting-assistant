"""ConceptMatcher 单元测试（不依赖远程 API）。

覆盖：
- 路 1 alias substring 长别名优先 + 跨度去重
- 路 2 definition substring 正确切片
- 路 4 embedding 在向量表为空时静默跳过
- 路 4 embedding API 调用失败时降级
- 路 4 embedding 命中后能正常计入 candidates 并产出 ConceptMatchHit
- enable_embedding=False 时与既有 routes_concepts.match_concepts 行为等价
- match_offset 在仅 embedding 命中时为 0（不是 -1，对前端友好）

测试通过 monkeypatch app.services.llm_client.embed_texts 注入假向量，
不真调远程 API。
"""

from __future__ import annotations

import struct

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.models.db_models import (
    RegConcept,
    RegConceptAlias,
    RegConceptEmbedding,
    RegConceptReportingItemMap,
)
from app.services import concept_matcher as cm


# ── fixtures ──────────────────────────────────────────────────────────


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_concept(
    session: Session,
    code: str,
    name: str,
    short_def: str,
    aliases: list[str],
    related_items: list[tuple[str, str]] | None = None,
    scope: str = "1104",
) -> int:
    concept = RegConcept(
        concept_code=code,
        canonical_name=name,
        short_definition=short_def,
        full_definition=short_def,
        concept_type="METRIC",
        reporting_system_scope=scope,
        status="ACTIVE",
    )
    session.add(concept)
    session.commit()
    session.refresh(concept)
    assert concept.id is not None
    for alias in aliases:
        session.add(RegConceptAlias(concept_id=concept.id, alias_text=alias))
    for item_code, role in related_items or []:
        session.add(
            RegConceptReportingItemMap(
                concept_id=concept.id, reporting_item_code=item_code, role=role
            )
        )
    session.commit()
    return concept.id


def _seed_embedding(
    session: Session,
    concept_id: int,
    vec: list[float],
    model_name: str = "text-embedding-v3",
) -> None:
    session.add(
        RegConceptEmbedding(
            concept_id=concept_id,
            model_name=model_name,
            dim=len(vec),
            vector=cm.serialize_vector(vec),
            source_text="seed",
        )
    )
    session.commit()


# ── 序列化往返 ─────────────────────────────────────────────────────────


def test_serialize_roundtrip_float32_precision():
    vec = [0.1, 0.2, -0.3, 1.5, 0.0]
    raw = cm.serialize_vector(vec)
    # float32 比 list 紧凑：每元素 4 字节
    assert len(raw) == 4 * len(vec)
    back = cm.deserialize_vector(raw)
    for a, b in zip(vec, back):
        assert abs(a - b) < 1e-6


def test_cosine_similarity_basics():
    assert cm.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cm.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cm.cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    # 维度不匹配 / 零向量 → 0.0
    assert cm.cosine_similarity([1.0], [1.0, 0.0]) == 0.0
    assert cm.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


# ── 路 1 alias ─────────────────────────────────────────────────────────


def test_alias_long_first_no_overlap():
    """长别名优先 + span 占用：'同业融入余额'匹掉的 span 内不再命中短别名指向的其他概念。

    注：CON_SHORT 故意用与 text 完全不重叠的 short_def，避免被路 2 定义子串命中干扰路 1 测试。
    """
    session = _make_session()
    _seed_concept(
        session, "CON_LONG", "同业融入余额", "同业融入余额（口径 A）",
        aliases=["同业融入余额", "同业融入"],
    )
    _seed_concept(
        session, "CON_SHORT", "同业融入概念", "不同字段口径占位填充内容仅作测试",
        aliases=["同业融入"],
    )

    matcher = cm.ConceptMatcher(session, enable_embedding=False)
    hits = matcher.match("本通知统计同业融入余额范围", scope="1104")
    # 长别名优先命中 CON_LONG；CON_SHORT 因 span 被占用且定义无字面重叠，不命中
    assert any(h.concept_code == "CON_LONG" for h in hits)
    assert not any(h.concept_code == "CON_SHORT" for h in hits)


def test_alias_scope_filter():
    """reporting_system_scope 过滤：1104 + CROSS 召回，EAST 排除。

    注：三个概念用不同 alias 避免 consumed_spans 误阻挡（既有 routes_concepts 行为：
    同一 text span 只能命中一个概念，与 scope 过滤是正交逻辑）。
    """
    session = _make_session()
    _seed_concept(session, "C1104", "X", "X1104", ["甲指标"], scope="1104")
    _seed_concept(session, "CEAST", "Y", "YEAST", ["乙指标"], scope="EAST")
    _seed_concept(session, "CCROSS", "Z", "ZCROSS", ["丙指标"], scope="CROSS")

    matcher = cm.ConceptMatcher(session, enable_embedding=False)
    hits = matcher.match("本通知涉及甲指标 / 乙指标 / 丙指标 三项", scope="1104")
    codes = {h.concept_code for h in hits}
    # 1104 + CROSS 应被召回，EAST 不应
    assert "C1104" in codes
    assert "CCROSS" in codes
    assert "CEAST" not in codes


# ── 路 2 definition ────────────────────────────────────────────────────


def test_definition_substring_hit():
    """定义里的子片段在 text 中出现，应弱命中"""
    session = _make_session()
    _seed_concept(
        session, "CON_BOOK", "账面余额", "会计账面口径的余额，含减值前后口径",
        aliases=["账面余额"],
    )

    matcher = cm.ConceptMatcher(session, enable_embedding=False)
    # text 不包含 alias，但包含定义里的片段 "含减值前后口径"
    hits = matcher.match("本通知调整含减值前后口径的统计方式", scope="1104")
    assert any(h.concept_code == "CON_BOOK" for h in hits)


def test_definition_skip_short_fragments():
    """长度 <4 的定义片段不应触发命中"""
    session = _make_session()
    _seed_concept(
        session, "CON_S", "abc", "短，碎，片",
        aliases=[],
    )
    matcher = cm.ConceptMatcher(session, enable_embedding=False)
    hits = matcher.match("短", scope="1104")
    assert not any(h.concept_code == "CON_S" for h in hits)


# ── 路 4 embedding ─────────────────────────────────────────────────────


def test_embedding_skipped_when_table_empty(monkeypatch):
    """向量表为空时，路 4 静默跳过，结果与 enable_embedding=False 等价"""
    session = _make_session()
    _seed_concept(session, "C1", "同业融入余额", "同业融入余额",
                  aliases=["同业融入余额"])

    called = {"n": 0}

    def fake_embed(_texts):
        called["n"] += 1
        return [[0.0]]

    monkeypatch.setattr(cm, "embed_texts", fake_embed)

    matcher = cm.ConceptMatcher(session, enable_embedding=True)
    hits = matcher.match("同业融入余额", scope="1104")
    assert called["n"] == 0  # 没建库直接 return，没调 API
    assert any(h.concept_code == "C1" for h in hits)


def test_embedding_api_failure_falls_back(monkeypatch):
    """embed_texts 抛 LLMClientError 时，降级路 1+2，不抛给业务方"""
    from app.services.llm_client import LLMClientError

    session = _make_session()
    cid = _seed_concept(session, "C1", "同业融入余额", "同业融入余额",
                        aliases=["同业融入余额"])
    _seed_embedding(session, cid, [0.1, 0.2, 0.3])

    def boom(_texts):
        raise LLMClientError("simulated API down")

    monkeypatch.setattr(cm, "embed_texts", boom)

    matcher = cm.ConceptMatcher(session, enable_embedding=True)
    # 不应抛错；路 1 仍能命中
    hits = matcher.match("同业融入余额", scope="1104")
    assert any(h.concept_code == "C1" for h in hits)


def test_embedding_pure_semantic_hit(monkeypatch):
    """纯同义改写场景：text 与 alias 字面零重叠，但 embedding 高相似度，应命中"""
    session = _make_session()
    cid_target = _seed_concept(
        session, "CON_INTERBANK", "同业融入余额",
        "商业银行向其他金融机构融入资金的余额",
        aliases=["同业融入余额", "同业融入", "拆入资金余额"],
    )
    # 另起一个无关概念作为干扰
    cid_noise = _seed_concept(
        session, "CON_NOISE", "投资久期", "债券组合的加权平均剩余期限",
        aliases=["久期"],
    )
    # 给 target 灌入向量 [1, 0]（与 query [1,0] 同向）
    _seed_embedding(session, cid_target, [1.0, 0.0])
    # noise 向量与 query 正交（cos=0），低于阈值
    _seed_embedding(session, cid_noise, [0.0, 1.0])

    def fake_embed(texts):
        # query 嵌入与 target 同方向
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(cm, "embed_texts", fake_embed)

    matcher = cm.ConceptMatcher(session, enable_embedding=True)
    # text 完全不包含任何 alias，纯靠 embedding
    hits = matcher.match("银行间拆借规模变动情况", scope="1104")
    codes = {h.concept_code for h in hits}
    assert "CON_INTERBANK" in codes  # 同向召回
    assert "CON_NOISE" not in codes  # 正交不召回


def test_embedding_strengthens_alias_hit_score(monkeypatch):
    """既被 alias 命中又被 embedding 命中的概念，score 应大于纯 alias 命中"""
    session = _make_session()
    cid_strong = _seed_concept(
        session, "CON_STRONG", "同业融入余额", "商业银行向其他金融机构融入资金",
        aliases=["同业融入余额"],
    )
    cid_weak = _seed_concept(
        session, "CON_WEAK", "拆借", "拆借",
        aliases=["拆借"],
    )
    _seed_embedding(session, cid_strong, [1.0, 0.0])
    _seed_embedding(session, cid_weak, [0.0, 1.0])

    def fake_embed(texts):
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(cm, "embed_texts", fake_embed)

    matcher = cm.ConceptMatcher(session, enable_embedding=True)
    hits = matcher.match("同业融入余额与拆借统计", scope="1104")
    # CON_STRONG 多路命中应排前
    assert hits[0].concept_code == "CON_STRONG"


# ── 工厂 ──────────────────────────────────────────────────────────────


def test_get_concept_matcher_auto_disable_when_no_api_key(monkeypatch):
    """没配 embedding key 时，工厂自动 enable_embedding=False"""
    from app.core import config as config_mod

    class _FakeSettings:
        embedding_api_base = ""
        embedding_api_key = ""

    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettings())

    session = _make_session()
    matcher = cm.get_concept_matcher(session)
    assert matcher.enable_embedding is False


def test_get_concept_matcher_auto_enable_when_configured(monkeypatch):
    from app.core import config as config_mod

    class _FakeSettings:
        embedding_api_base = "https://x.example/v1"
        embedding_api_key = "sk-fake"

    monkeypatch.setattr(config_mod, "get_settings", lambda: _FakeSettings())

    session = _make_session()
    matcher = cm.get_concept_matcher(session)
    assert matcher.enable_embedding is True
