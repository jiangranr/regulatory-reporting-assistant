"""一次性给所有 ACTIVE 概念建/重建 embedding。

用法：
    # 默认：增量模式（只补缺失或模型版本不匹配的）
    uv run python scripts/rebuild_concept_embeddings.py

    # 全量重建（删除旧向量后重新生成；用于模型升级 / source_text 改动）
    uv run python scripts/rebuild_concept_embeddings.py --full

    # 限定 reporting_system_scope
    uv run python scripts/rebuild_concept_embeddings.py --scope 1104

    # dry-run 看会发生什么
    uv run python scripts/rebuild_concept_embeddings.py --dry-run

依赖：
    .env 必须配置 REG_ASSISTANT_EMBEDDING_API_BASE / _KEY / _MODEL
    （DashScope 用户：base = https://dashscope.aliyuncs.com/compatible-mode/v1）

退出码：
    0  成功
    1  部分失败（详见输出）
    2  配置错误（API key 未配 / 网络挂）
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.models.db_models import RegConcept, RegConceptEmbedding  # noqa: E402
from app.services.concept_matcher import (  # noqa: E402
    build_concept_source_text,
    serialize_vector,
)
from app.services.llm_client import LLMClientError, embed_texts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="重建监管概念的 embedding 向量库")
    parser.add_argument(
        "--full",
        action="store_true",
        help="全量重建（先删除现有向量），用于换模型或 source_text 策略",
    )
    parser.add_argument(
        "--scope",
        default=None,
        help="限制 reporting_system_scope，例如 1104 / EAST / CROSS。默认全量",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不调 API、不写库，只列出将要做什么",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="单批向量化条数，默认走 settings.embedding_batch_size",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not (settings.embedding_api_base and settings.embedding_api_key) and not args.dry_run:
        print(
            "[!] embedding API 未配置。请在 .env 设置 "
            "REG_ASSISTANT_EMBEDDING_API_BASE / _API_KEY / _MODEL",
            file=sys.stderr,
        )
        return 2

    print(f"模型：{settings.embedding_model}（dim 期望 {settings.embedding_dim}）")
    if args.dry_run:
        print("【DRY RUN】不调 API、不写库")

    with Session(engine) as session:
        # 1. 拉所有 ACTIVE 概念
        concept_query = select(RegConcept).where(RegConcept.status == "ACTIVE")
        if args.scope:
            concept_query = concept_query.where(
                RegConcept.reporting_system_scope == args.scope
            )
        concepts = list(session.exec(concept_query).all())
        print(f"待处理 ACTIVE 概念：{len(concepts)}")
        if not concepts:
            return 0

        # 2. 拉现有 embeddings（如果是 full，会全删）
        existing_rows = list(
            session.exec(
                select(RegConceptEmbedding).where(
                    RegConceptEmbedding.model_name == settings.embedding_model
                )
            ).all()
        )
        existing_by_concept = {r.concept_id: r for r in existing_rows}

        if args.full:
            print(f"【FULL】删除 {len(existing_rows)} 条旧向量（model={settings.embedding_model}）")
            if not args.dry_run:
                for row in existing_rows:
                    session.delete(row)
                session.commit()
                existing_by_concept = {}

        # 3. 算出需要新建/重算的清单
        # 增量模式：只处理 source_text 变化或还没向量的
        to_embed: list[tuple[RegConcept, str]] = []
        skipped = 0
        for concept in concepts:
            source_text = build_concept_source_text(concept)
            existing = existing_by_concept.get(concept.id)
            if existing and existing.source_text == source_text:
                skipped += 1
                continue
            to_embed.append((concept, source_text))

        print(f"需向量化：{len(to_embed)}，跳过（已最新）：{skipped}")
        if not to_embed:
            print("✅ 已是最新，无需重建")
            return 0

        if args.dry_run:
            for concept, source_text in to_embed[:10]:
                print(f"  · {concept.concept_code}: {source_text}")
            if len(to_embed) > 10:
                print(f"  ... 及另外 {len(to_embed) - 10} 个")
            return 0

        # 4. 调远程 API 拿向量（分批）
        batch_size = args.batch_size or settings.embedding_batch_size
        ok_count = 0
        err_count = 0
        for offset in range(0, len(to_embed), batch_size):
            batch = to_embed[offset : offset + batch_size]
            texts = [s for _, s in batch]
            print(
                f"批 {offset // batch_size + 1}：发送 {len(batch)} 条 "
                f"({batch[0][0].concept_code} ... {batch[-1][0].concept_code})",
                end=" ",
            )
            try:
                vectors = embed_texts(texts)
            except LLMClientError as exc:
                print(f"❌ 失败 {exc}")
                err_count += len(batch)
                continue

            if len(vectors) != len(batch):
                print(f"❌ 数量不匹配：期望 {len(batch)} 收到 {len(vectors)}")
                err_count += len(batch)
                continue

            # 5. 落库（更新或新建）
            now = datetime.utcnow()
            for (concept, source_text), vec in zip(batch, vectors):
                existing = existing_by_concept.get(concept.id)
                if existing:
                    existing.vector = serialize_vector(vec)
                    existing.source_text = source_text
                    existing.dim = len(vec)
                    existing.updated_at = now
                    session.add(existing)
                else:
                    session.add(
                        RegConceptEmbedding(
                            concept_id=concept.id,
                            model_name=settings.embedding_model,
                            dim=len(vec),
                            vector=serialize_vector(vec),
                            source_text=source_text,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                ok_count += 1
            session.commit()
            print(f"✅ 写入 {len(batch)} 条")

        print()
        print(f"总计：✅ {ok_count} 成功 / ❌ {err_count} 失败")
        return 0 if err_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
