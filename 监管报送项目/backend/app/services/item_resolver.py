"""把 LLM 抽出的 indicator_hint 反查到 reg_reporting_items 的 item_code。

设计依据：docs/concept-and-ticket-reuse-design.md（后续会追加）+ 用户 2026-05-26 确认。

为什么需要
----------
LLM 文本路径产出的 change_signals 几乎全部 matched_item_code 为空，
导致前端 LineageView 各种 fallback 失效（concept 命中区块为空、field_mapping
fuzzy 全表误匹配）。这是项目里多 UI bug 的共同根因。

策略（与 ConceptMatcher 同构，但目标实体是 reg_reporting_items）
----------------------------------------------------------------
- 路 1 alias substring：indicator_hint 与 item_name / row_label / column_label
                       归一化后字面包含
- 路 2 token overlap：indicator_hint 按业务分隔符切 token，与 item 多字段
                     做 token 交集打分
- 路 4 embedding（W4+）：留接口，本期不实现（先验证字面是否足够）

层级 mismatch 处理（关键设计）
------------------------------
LLM signal 通常是"业务条款级"（例 "1.8 资产支持证券分类调整"），
而 reg_reporting_items 是"cell 级"（例 G31.PART_I.13_0.A_穿透前_期末余额）。
一对多场景：
  - top 1 ≥ 高置信阈值 → 填 matched_item_code，match_status=FUZZY_PRECISE
  - top N 都中等置信  → matched_item_code 留空，命中清单写入
                       composite_match.reporting_item_codes，match_status=FUZZY_LANE
  - 全部低于阈值     → 不动 signal（保持原样，由前端兜底空态展示）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlmodel import Session, select

from app.models.db_models import RegReportingItem, RegReportingObject

# ── 阈值（可调）─────────────────────────────────────────────────────


# 单命中阈值：top-1 分数 ≥ 此值才作为精确命中
_PRECISE_THRESHOLD = 0.55
# 多命中阈值：分数 ≥ 此值进入 composite_match 候选清单
_LANE_THRESHOLD = 0.30
# 候选清单上限：避免几十个 cell 全填
_LANE_TOP_K = 6


# ── 数据结构 ────────────────────────────────────────────────────────


@dataclass
class ResolveResult:
    """匹配结果。

    match_status 取值：
      FUZZY_PRECISE   — 单 item 高置信命中
      FUZZY_LANE      — 多 item 中置信命中（业务条款级 → cell 级一对多）
      UNRESOLVED      — 没有命中达到阈值
    """

    matched_item_code: str = ""
    item_codes: list[str] = field(default_factory=list)
    match_status: str = "UNRESOLVED"
    confidence: float = 0.0
    paths: list[str] = field(default_factory=list)


# ── 文本归一化 / token 化 ───────────────────────────────────────────


# 业务里有意义的分隔符（注意：[] 在字符类内要转义；中文括号字符直接放）
_TOKEN_STRIP = re.compile(
    r"[\s·_\-/×、，,.;:'\"()（）「」『』\[\]【】<>《》]+"
)
# 业务里有意义的最短 token 长度
_MIN_TOKEN_LEN = 2


def _normalise(raw: str) -> str:
    """把字符串归一化为小写 + 去常见分隔。"""
    if not raw:
        return ""
    return _TOKEN_STRIP.sub("", raw).lower()


def _tokenise(raw: str) -> list[str]:
    """按业务分隔符切 token，保留长度 ≥ _MIN_TOKEN_LEN 的片段。"""
    if not raw:
        return []
    parts = _TOKEN_STRIP.split(raw)
    tokens: list[str] = []
    for p in parts:
        p = p.strip()
        # 跳过纯数字编号片段（"1.8.2" 之类），它们做匹配会污染（任意 item_code 都含数字）
        if not p or len(p) < _MIN_TOKEN_LEN:
            continue
        if re.fullmatch(r"[\d.]+", p):
            continue
        tokens.append(p.lower())
    return tokens


# ── 打分 ─────────────────────────────────────────────────────────────


def _score_item(
    hint: str, hint_tokens: list[str], item: RegReportingItem
) -> tuple[float, list[str]]:
    """单个 item 的匹配得分（0.0 ~ 1.0+）。

    返回 (score, paths)。paths 取值 'alias' / 'token'。

    打分依据：
      - 字面 substring 包含 +0.45
      - token 交集 / token 总数 → +0~0.55
      - 行/列双向命中加成 +0.10
    """
    score = 0.0
    paths: set[str] = set()

    hint_norm = _normalise(hint)
    if not hint_norm or not hint_tokens:
        return 0.0, []

    # 字面 substring：hint 的归一化 vs item 各字段
    fields = [item.item_name or "", item.row_label or "", item.column_label or ""]
    item_normed = [_normalise(f) for f in fields]
    if any(f and (hint_norm in f or f in hint_norm) for f in item_normed):
        score += 0.45
        paths.add("alias")

    # token 交集
    item_tokens: set[str] = set()
    for f in fields:
        item_tokens.update(_tokenise(f))
    if item_tokens and hint_tokens:
        hit_set = set(hint_tokens) & item_tokens
        if hit_set:
            overlap = len(hit_set) / max(len(hint_tokens), len(item_tokens))
            score += min(0.55, overlap * 1.2)
            paths.add("token")

    # 双向 row + column 都有 token 命中 → 加成
    row_toks = set(_tokenise(item.row_label or ""))
    col_toks = set(_tokenise(item.column_label or ""))
    if (row_toks & set(hint_tokens)) and (col_toks & set(hint_tokens)):
        score += 0.10

    return score, sorted(paths)


# ── 主类 ────────────────────────────────────────────────────────────


class ReportingItemResolver:
    """把 indicator_hint 反查到具体的 reporting_item_code。

    用法：
        resolver = ReportingItemResolver(session)
        result = resolver.resolve(table_code="G24", indicator_hint="境外法人机构融入款项")
        # result.matched_item_code, result.item_codes, result.match_status
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        # cache: table_code → list[RegReportingItem]
        self._items_cache: dict[str, list[RegReportingItem]] = {}

    # ------------------------------------------------------------------
    def resolve(self, table_code: str, indicator_hint: str) -> ResolveResult:
        if not table_code or not indicator_hint:
            return ResolveResult()
        items = self._load_items(table_code)
        if not items:
            return ResolveResult()

        hint_tokens = _tokenise(indicator_hint)
        if not hint_tokens:
            return ResolveResult()

        # 单 item 表的特例：表里只有一条候选，无论 hint 多模糊都返回该 item。
        # 因为"精确"在单一候选语义上必然成立，与 score 无关。
        # 这覆盖 G24/G27 这类一对一表的常见场景。
        if len(items) == 1 and items[0].item_code:
            sole = items[0]
            s, p = _score_item(indicator_hint, hint_tokens, sole)
            return ResolveResult(
                matched_item_code=sole.item_code,
                item_codes=[sole.item_code],
                match_status="FUZZY_PRECISE",
                confidence=min(max(s, 0.5), 1.0),  # 单表至少 0.5 置信，否则后续过滤会失效
                paths=p or ["table-singleton"],
            )

        scored: list[tuple[float, str, list[str], RegReportingItem]] = []
        for item in items:
            if not item.item_code:
                continue
            s, p = _score_item(indicator_hint, hint_tokens, item)
            if s >= _LANE_THRESHOLD:
                scored.append((s, item.item_code, p, item))

        if not scored:
            return ResolveResult()
        scored.sort(key=lambda x: -x[0])

        top_score, top_code, top_paths, _ = scored[0]
        if top_score >= _PRECISE_THRESHOLD:
            # 高置信单命中：matched_item_code 填 top 1
            return ResolveResult(
                matched_item_code=top_code,
                item_codes=[top_code],
                match_status="FUZZY_PRECISE",
                confidence=min(top_score, 1.0),
                paths=top_paths,
            )

        # 中置信多命中：matched_item_code 留空，list 填到 composite
        lane = [code for _, code, _, _ in scored[:_LANE_TOP_K]]
        merged_paths = sorted({p for _, _, ps, _ in scored[:_LANE_TOP_K] for p in ps})
        return ResolveResult(
            matched_item_code="",
            item_codes=lane,
            match_status="FUZZY_LANE",
            confidence=min(top_score, 1.0),
            paths=merged_paths,
        )

    # ------------------------------------------------------------------
    def _load_items(self, table_code: str) -> list[RegReportingItem]:
        if table_code in self._items_cache:
            return self._items_cache[table_code]
        obj_id_rows = list(
            self.session.exec(
                select(RegReportingObject.id).where(
                    RegReportingObject.object_code == table_code
                )
            ).all()
        )
        if not obj_id_rows:
            self._items_cache[table_code] = []
            return []
        obj_ids = [row for row in obj_id_rows if row is not None]
        items = list(
            self.session.exec(
                select(RegReportingItem).where(
                    RegReportingItem.reporting_object_id.in_(obj_ids)
                )
            ).all()
        )
        self._items_cache[table_code] = items
        return items
