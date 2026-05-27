"""注册具体业务路径的 executor。

每个 executor 接受 case 的 `inputs` dict，调用真实业务函数，
返回 list[dict]（每条是一个 signal-like 字典，可用 framework 断言）。

新增 target 模板：

    @register_target("my_path")
    def _my_path(inputs: dict) -> list[dict]:
        result = call_some_service(inputs["foo"])
        return [s.model_dump() for s in result.signals]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes_concepts import match_concepts
from app.models.db_models import (
    RegReportingItem,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingTemplate,
    RegReportingTemplateCell,
    RegReportingVersion,
)
from app.models.schemas import ConceptMatchRequest
from app.services.concept_seed import seed_concepts_and_rule_cards
from app.services.excel_parser import ExcelParseResult, parse_excel
from app.services.g31_excel_diff import diff_excel_with_db
from app.services.item_resolver import ReportingItemResolver

from .framework import register_target

# .env 文件的路径（用于绕开 conftest 的 DATABASE_URL 覆盖）
_BACKEND_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _read_persistent_database_url() -> str | None:
    """从 backend/.env 直接读 REG_ASSISTANT_DATABASE_URL。

    为什么不用 app.core.config.get_settings()：
      - get_settings 用 pydantic-settings + lru_cache，conftest.py 在 import 时
        把 os.environ["REG_ASSISTANT_DATABASE_URL"] 改成 sqlite 测试库
      - 即使后续读 .env，环境变量优先级更高，settings 仍是 sqlite
      - 所以这里直接 dumb 读 .env 字符串，绕开覆盖
    """
    if not _BACKEND_ENV_PATH.exists():
        return None
    try:
        for raw_line in _BACKEND_ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "REG_ASSISTANT_DATABASE_URL":
                return value.strip().strip('"').strip("'")
    except Exception:
        return None
    return None

# 项目根路径（用于解析 case 里的相对路径）
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_path(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / raw).resolve()


def _session_with_template_seed(
    parse_result: ExcelParseResult,
    *,
    object_code: str,
    version_code: str,
) -> Session:
    """基于 baseline xls 解析结果，构造一个含模板/指标/单元格的内存 DB。

    与 `tests/test_g31_excel_diff.py::_session_with_g31_items` 等价，
    但抽出来供 eval framework 复用（不污染 unit test 的命名空间）。
    """

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    system = RegReportingSystem(system_code="1104", system_name="1104")
    session.add(system)
    session.commit()
    session.refresh(system)

    version = RegReportingVersion(
        reporting_system_id=system.id,
        version_code=version_code,
        version_name=version_code,
    )
    session.add(version)
    session.commit()
    session.refresh(version)

    obj = RegReportingObject(
        reporting_system_id=system.id,
        reporting_version_id=version.id,
        object_code=object_code,
        object_name=object_code,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)

    section = RegReportingSection(
        reporting_object_id=obj.id,
        section_code="PART_I",
        section_name="PART_I",
    )
    session.add(section)
    session.commit()
    session.refresh(section)

    # 把 baseline xls 的 template_cells 落进 DB，让 diff 路径能命中"老版表样"
    template = RegReportingTemplate(
        reporting_object_id=obj.id,
        template_code=f"{object_code}.PART_I.{version_code}",
        template_name=f"{object_code} {version_code}",
    )
    session.add(template)
    session.commit()
    session.refresh(template)

    for cell in parse_result.template_cells:
        session.add(
            RegReportingTemplateCell(
                template_id=template.id,
                sheet_name=cell["sheet_name"],
                row_index=int(cell["row_index"]),
                col_index=int(cell["col_index"]),
                excel_ref=cell["excel_ref"],
                raw_text=cell["raw_text"],
                cell_type=cell["cell_type"],
                style_json=cell["style_json"],
                merge_json=cell["merge_json"],
            )
        )

    for item in parse_result.items:
        session.add(
            RegReportingItem(
                reporting_object_id=obj.id,
                reporting_section_id=section.id,
                item_code=item["item_code"],
                item_name=item["item_name"],
                row_label=item["row_label"],
                column_label=item["column_label"],
                source_cell_ref=item["source_cell_ref"],
                cell_role=item["cell_role"],
                is_fillable=item["is_fillable"],
                is_derived=item["is_derived"],
            )
        )
    session.commit()
    return session


@register_target("triplet_excel_diff")
def _run_triplet_excel_diff(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """新版 xls vs 数据库 baseline 的 diff 路径（不调 LLM，纯规则）。

    inputs 期望字段：
      object_code: str            报表代码，如 "G31"
      baseline_file: str          老版表样 xls（相对项目根或绝对路径），用作 DB seed
      template_file: str          新版表样 xls，传给 diff 函数
      baseline_version: str=251   老版版本号（仅用于 DB 标识）
    """

    object_code = inputs["object_code"]
    baseline_path = _resolve_path(inputs["baseline_file"])
    new_path = _resolve_path(inputs["template_file"])
    baseline_version = inputs.get("baseline_version", "baseline")

    if not baseline_path.exists():
        raise FileNotFoundError(f"baseline_file 不存在: {baseline_path}")
    if not new_path.exists():
        raise FileNotFoundError(f"template_file 不存在: {new_path}")

    baseline_parse = parse_excel(baseline_path, object_code)
    session = _session_with_template_seed(
        baseline_parse,
        object_code=object_code,
        version_code=baseline_version,
    )

    new_parse = parse_excel(new_path, object_code)
    diffs = diff_excel_with_db(session, object_code, new_parse)

    # 把 ExcelDiffEntry 转成 signal-like dict（对齐 routes_documents._excel_diffs_to_profile_signals
    # 的关键字段，便于断言）
    _ = select  # 触发 import（避免 ruff 抱怨）
    signals: list[dict[str, Any]] = []
    diff_type_map = {
        "REMOVED": "DELETE",
        "NEW": "ADD",
        "LABEL_CHANGED": "MODIFY",
    }
    for diff in diffs:
        change_type = diff_type_map.get(diff.diff_type, "UNCLEAR")
        indicator_hint = f"{diff.row_label} × {diff.column_label}".strip(" ×")
        signals.append(
            {
                "table_code": object_code,
                "section_hint": "PART_I",
                "indicator_hint": indicator_hint,
                "change_type": change_type,
                "evidence_text": diff.row_label or diff.column_label or "",
                "item_code": diff.item_code,
                "row_label": diff.row_label,
                "column_label": diff.column_label,
                "diff_type": diff.diff_type,
            }
        )
    return signals


# ── concept_match target ────────────────────────────────────────────────


def _session_with_concept_seed() -> Session:
    """启一个内存 DB，灌入 35+ 概念种子；如果持久 DB 有 embedding 也一并克隆进来。

    为什么克隆 embedding：
      eval framework 默认走 in-memory DB（隔离、快、不污染生产数据），
      但这样 ConceptMatcher 路 4 (embedding 余弦相似度) 看到的向量表是空的，
      导致同义改写场景（如"拆放同业"）在 eval 里完全召不回 —— 与浏览器实测不一致。

    解决：seed 之后立即查询持久 DB 的 RegConceptEmbedding，把 (concept_code, vector,
    model_name, dim, source_text) 一一克隆到内存 DB。
      - 持久 DB 已建库（用户跑过 rebuild_concept_embeddings.py）→ 完整四路召回可测
      - 持久 DB 空 → 静默退路 1+2，与既有降级策略一致，不抛错
      - 持久 DB 不可达 → 同样静默退路 1+2

    Embedding 数据是只读克隆，不会写回任何 DB；测试隔离不受影响。
    """
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    seed_concepts_and_rule_cards(session)
    _clone_embeddings_from_persistent_db(session)
    return session


def _clone_embeddings_from_persistent_db(memory_session: Session) -> None:
    """把持久 DB 的 RegConceptEmbedding 按 concept_code 克隆到内存 session。

    关键：直接读 `.env` 里的 REG_ASSISTANT_DATABASE_URL 构造独立 engine，
    **不复用 app.core.database.engine** —— 因为 tests/conftest.py 会把
    DATABASE_URL 强制改成 sqlite 测试库，那里没有真实 embedding 数据。
    """
    try:
        from app.models.db_models import RegConcept, RegConceptEmbedding
    except Exception:
        return

    persistent_url = _read_persistent_database_url()
    if not persistent_url:
        return

    try:
        from sqlmodel import create_engine as _create_engine

        src_engine = _create_engine(persistent_url)
        with Session(src_engine) as src:
            rows = list(src.exec(
                select(RegConcept, RegConceptEmbedding).where(
                    RegConcept.id == RegConceptEmbedding.concept_id
                )
            ).all())
    except Exception:
        # 持久 DB 不可达（如本地未启动 MySQL）→ 静默退路 1+2
        return

    if not rows:
        return

    # 内存 session 里的 concept_id 跟持久 DB 的不一定一样，按 concept_code 重建 id 映射
    code_to_memory_id: dict[str, int] = {}
    for concept in memory_session.exec(select(RegConcept)).all():
        if concept.id is not None and concept.concept_code:
            code_to_memory_id[concept.concept_code] = concept.id

    cloned = 0
    for src_concept, src_embedding in rows:
        memory_concept_id = code_to_memory_id.get(src_concept.concept_code)
        if memory_concept_id is None:
            continue
        memory_session.add(RegConceptEmbedding(
            concept_id=memory_concept_id,
            model_name=src_embedding.model_name,
            dim=src_embedding.dim,
            vector=src_embedding.vector,
            source_text=src_embedding.source_text,
            created_at=src_embedding.created_at,
            updated_at=src_embedding.updated_at,
        ))
        cloned += 1
    memory_session.commit()


@register_target("concept_match")
def _run_concept_match(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """走 /api/concepts/match 的全流程。

    inputs 期望字段：
      text: str                   要匹配的发文片段
      reporting_system_scope: str=None  限制召回的体系（1104 / EAST / 一表通），默认全部
      top_k: int=20               最多返回多少条命中

    返回的每条 signal-like dict 字段：
      concept_code           主键，用于断言"必须命中 X 概念"
      canonical_name         概念规范名
      matched_alias          实际命中的别名文本
      match_offset           别名在 text 中的位置
      change_type            统一填 "MATCH"，方便走既有断言 spec
      indicator_hint         填 concept_code 让 keyword spec 可命中
      evidence_text          填 canonical_name + matched_alias 便于关键词匹配
      related_reporting_item_codes  通过该概念辐射的报送项
    """

    text = inputs["text"]
    request = ConceptMatchRequest(
        text=text,
        reporting_system_scope=inputs.get("reporting_system_scope"),
        top_k=int(inputs.get("top_k", 20)),
    )
    session = _session_with_concept_seed()
    response = match_concepts(request, session)

    signals: list[dict[str, Any]] = []
    for hit in response.hits:
        related = list(hit.related_reporting_item_codes or [])
        signals.append(
            {
                "concept_code": hit.concept_code,
                "canonical_name": hit.canonical_name,
                "matched_alias": hit.matched_alias,
                "match_offset": hit.match_offset,
                "change_type": "MATCH",
                "table_code": related[0].split(".")[0] if related else "",
                "indicator_hint": hit.concept_code,
                "evidence_text": f"{hit.canonical_name} | {hit.matched_alias}",
                "related_reporting_item_codes": related,
            }
        )
    return signals


# ── item_resolve target ─────────────────────────────────────────────────


@register_target("item_resolve")
def _run_item_resolve(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """走 ReportingItemResolver 全流程，验证 indicator_hint → item_code 落格。

    走持久 DB（与 ConceptMatcher 不同）—— 因为 item_resolver 需要完整的
    reg_reporting_items 数据（G31 有 455 条，构造内存 seed 不现实），
    且 item_resolver 不依赖任何外部 API，纯本地查询，无副作用。

    inputs 期望字段：
      table_code: str          报表代码，如 "G24" / "G31"
      indicator_hint: str      LLM 抽出的 indicator_hint

    输出 signal-like dict 字段：
      matched_item_code        FUZZY_PRECISE 时填，LANE/UNRESOLVED 时为空
      item_codes               候选清单（最多 _LANE_TOP_K 条）
      match_status             FUZZY_PRECISE / FUZZY_LANE / UNRESOLVED
      confidence               0~1
      paths                    ['alias', 'token', 'table-singleton'] 子集
      change_type              统一 'RESOLVE'，让既有断言 spec 复用
      indicator_hint           填首个 item_code，让 keyword spec 可命中
      evidence_text            填 status + matched + 前 3 个候选，便于关键词匹配
    """
    table_code = inputs.get("table_code", "")
    indicator_hint = inputs.get("indicator_hint", "")

    # 走真 DB（与 _clone_embeddings 同思路绕开 conftest 的 DATABASE_URL 覆盖）
    # item_resolver 依赖完整的 reg_reporting_items 数据，sqlite 测试库里没有
    persistent_url = _read_persistent_database_url()
    if not persistent_url:
        return []
    from sqlmodel import create_engine as _create_engine

    src_engine = _create_engine(persistent_url)
    with Session(src_engine) as session:
        resolver = ReportingItemResolver(session)
        result = resolver.resolve(table_code, indicator_hint)

    # FUZZY_PRECISE → 单 signal；LANE → 多 signal；UNRESOLVED → 空
    if result.match_status == "UNRESOLVED" or not result.item_codes:
        return []

    signals: list[dict[str, Any]] = []
    for code in result.item_codes:
        signals.append(
            {
                "matched_item_code": result.matched_item_code,
                "item_code": code,
                "match_status": result.match_status,
                "confidence": result.confidence,
                "paths": result.paths,
                "change_type": "RESOLVE",
                "table_code": table_code,
                "indicator_hint": code,
                "evidence_text": (
                    f"{result.match_status} matched={result.matched_item_code} "
                    f"top={', '.join(result.item_codes[:3])}"
                ),
            }
        )
    return signals
