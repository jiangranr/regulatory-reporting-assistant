"""端到端 smoke 测试：用持久 DB 的真实向量库，跑几个核心场景。

为什么不放在 tests/eval/ 里：
  eval framework 用 in-memory DB，每次跑都从 seed 开始，没有 embedding 向量。
  要在 eval 里测真 embedding 效果，需要每次跑 rebuild_concept_embeddings（慢、烧 token）。
  smoke 脚本走持久 DB（data/app.db）+ 已建好的向量库，是"真效果"的快速验证。

跑法：
  uv run python scripts/smoke_concept_match.py

前置条件：
  1. .env 已配 REG_ASSISTANT_EMBEDDING_API_*
  2. 已跑过 uv run python scripts/rebuild_concept_embeddings.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select  # noqa: E402

from app.core.database import engine  # noqa: E402
from app.models.db_models import RegConceptEmbedding  # noqa: E402
from app.services.concept_matcher import ConceptMatcher  # noqa: E402


# (输入文本, scope, 必须命中的至少一个 concept_code)
SCENARIOS: list[tuple[str, str, list[str]]] = [
    # 1. 纯同义改写（路 4 embedding 核心场景）
    (
        "拆放同业纳入统计范围",
        "1104",
        ["CON_INTERBANK_BORROWING_BAL"],  # 字面零重叠
    ),
    # 2. 字面命中（路 1 应稳定召回）
    (
        "本通知统计同业融入余额的填报口径",
        "1104",
        ["CON_INTERBANK_BORROWING_BAL"],
    ),
    # 3. G31 债券口径
    (
        "G31 投资业务情况表新增穿透前后的债券投资账面余额对照填报",
        "1104",
        ["CON_BOND_INVESTMENT_BAL"],
    ),
    # 4. 资产管理产品 / 穿透原则
    (
        "对资产管理产品按穿透原则填报，需识别底层资产",
        "1104",
        ["CON_ASSET_MGMT_PRODUCT", "CON_LOOK_THROUGH", "CON_UNDERLYING_ASSET"],
    ),
    # 5. 纯语义召回（无 alias 命中；只测有概念被语义召回出来即可）
    (
        "银行间拆借规模变动情况",
        "1104",
        # 这条输入语义偏"同业资金往来"，可能命中 BORROWING 或 DEPOSIT 或 FINANCIAL_INSTITUTION
        # 关键是必须召回到至少一个同业相关概念（任一即可）
        ["CON_INTERBANK_BORROWING_BAL", "CON_INTERBANK_DEPOSIT", "CON_FINANCIAL_INSTITUTION"],
    ),
    # 6. 负样本（不应命中任何概念）
    (
        "本通知关于办公场所消防安全检查工作的部署",
        "1104",
        [],
    ),
]


def main() -> int:
    with Session(engine) as session:
        n_vectors = len(list(session.exec(select(RegConceptEmbedding)).all()))
        if n_vectors == 0:
            print("[!] 向量库为空。请先跑：")
            print("    uv run python scripts/rebuild_concept_embeddings.py")
            return 2
        print(f"向量库：{n_vectors} 个概念向量已就绪\n")

        matcher = ConceptMatcher(session, enable_embedding=True)

        all_ok = True
        for text, scope, must_hit_any in SCENARIOS:
            print(f">>> {text}")
            print(f"    scope={scope}, 期望命中至少 1 个: {must_hit_any or '（无）'}")
            hits = matcher.match(text, scope=scope, top_k=5)
            hit_codes = [h.concept_code for h in hits]

            for h in hits:
                items_preview = ", ".join(h.related_reporting_item_codes[:2])
                print(
                    f"    · {h.concept_code:35s} "
                    f"alias='{h.matched_alias}'  items=[{items_preview}]"
                )
            if not hits:
                print("    · （0 命中）")

            # 校验
            if not must_hit_any:
                ok = len(hits) == 0
            else:
                ok = any(c in hit_codes for c in must_hit_any)
            mark = "✅" if ok else "❌"
            print(f"    {mark}\n")
            all_ok = all_ok and ok

        print("=" * 60)
        if all_ok:
            print("✅ 所有场景通过")
            return 0
        else:
            print("❌ 至少 1 个场景未通过预期")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
