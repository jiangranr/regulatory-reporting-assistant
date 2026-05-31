"""embedding_indexer.py

填报说明切片 + Embedding 构建服务。

切片策略（v2）：
  识别填报说明中 `[字段标签. 字段名]：` 模式，每个字段定义作为独立切片。
  未匹配到字段定义的段落（引言、章节说明、核对关系等）按字符数合并切片。

搜索策略（三级级联）：
  1. 精确匹配：item_name 与查询完全匹配
  2. 关键词匹配：chunk_text 包含查询关键词，按命中计分排序
  3. 语义匹配：embedding 余弦相似度（兜底）
"""
from __future__ import annotations

import math
import re
import struct
from pathlib import Path

from sqlmodel import Session, select

from app.models.db_models import RegInstructionChunk
from app.services.doc_parser import extract_doc_text
from app.services.llm_client import LLMClientError, embed_texts

# 一表通根目录
_BASE_DIR = Path(__file__).parent.parent.parent.parent / "一表通" / "附件4：报表表样和填报说明汇总"

_FILE_MAP: list[tuple[str, str, str]] = [
    (
        "G01",
        "G01《货币当局资产负债表》",
        "2.修订报表（基础类、业务类、支持发展类）/G01_IV/G01_IV填报说明（251）.doc",
    ),
    (
        "G01",
        "G01_V《货币当局资产负债表第五部分》",
        "5.填报说明及其他调整/G01_V填报说明（251版）.doc",
    ),
    (
        "G01",
        "G01_VII《货币当局资产负债表第七部分》",
        "5.填报说明及其他调整/G01_VII填报说明（251版）.doc",
    ),
    (
        "G01",
        "G01《货币当局资产负债表·主表》",
        "5.填报说明及其他调整/G01填报说明（251）.doc",
    ),
    (
        "G31",
        "G31《投资业务情况表》",
        "2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc",
    ),
]

# 字段定义行匹配：[B. 穿透前-xxx]：/ [C.修正久期]：/ [1.1 优先股]：
_FIELD_DEF_RE = re.compile(
    r'^\[([A-Za-z0-9][A-Za-z0-9._\-]*)[.\s]*([^\]]{1,40})\][：:]'
)

# 非字段切片的最大字符数
_MAX_CHUNK_CHARS = 400
_MIN_CHUNK_CHARS = 40


# ──────────────────────────────────────────────────────────────────────────────
# 公开接口
# ──────────────────────────────────────────────────────────────────────────────

def build_instruction_index(session: Session, force_rebuild: bool = False) -> dict:
    """解析所有填报说明文件，切片后存入 RegInstructionChunk。

    Returns:
        {files_processed, chunks_written, chunks_skipped, errors}
    """
    # 确保新列存在（幂等 ALTER TABLE）
    _ensure_columns(session)

    stats: dict = {"files_processed": 0, "chunks_written": 0, "chunks_skipped": 0, "errors": []}

    for object_code, label_prefix, rel_path in _FILE_MAP:
        file_path = _BASE_DIR / rel_path
        if not file_path.exists():
            stats["errors"].append(f"文件不存在: {rel_path}")
            continue

        source_file = file_path.name

        # 检查是否已建索引
        if not force_rebuild:
            existing = session.exec(
                select(RegInstructionChunk).where(
                    RegInstructionChunk.reporting_object_code == object_code,
                    RegInstructionChunk.source_file == source_file,
                )
            ).first()
            if existing:
                stats["chunks_skipped"] += 1
                continue

        # 删除旧记录
        old = session.exec(
            select(RegInstructionChunk).where(
                RegInstructionChunk.reporting_object_code == object_code,
                RegInstructionChunk.source_file == source_file,
            )
        ).all()
        for row in old:
            session.delete(row)
        session.commit()

        # 解析文本
        try:
            full_text = extract_doc_text(file_path)
        except Exception as e:
            stats["errors"].append(f"解析失败 {rel_path}: {e}")
            continue

        # 切片（v2：字段感知）
        chunks = _split_into_chunks(full_text, label_prefix)
        if not chunks:
            stats["errors"].append(f"切片结果为空: {rel_path}")
            continue

        # Embedding（分批，每批最多 20 条，避免大文件单次调用失败）
        texts = [c["text"] for c in chunks]
        vectors: list[list[float]] = []
        _BATCH = 20
        for start in range(0, len(texts), _BATCH):
            batch = texts[start: start + _BATCH]
            try:
                vectors.extend(embed_texts(batch))
            except LLMClientError:
                vectors.extend([[] for _ in batch])

        # 写入 DB
        model_ver = _get_model_version()
        for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
            emb_bytes = _vec_to_bytes(vec) if vec else None
            row = RegInstructionChunk(
                reporting_object_code=object_code,
                source_file=source_file,
                chunk_index=i,
                chunk_text=chunk["text"],
                source_label=chunk["label"],
                field_tag=chunk.get("field_tag", ""),
                item_name=chunk.get("item_name", ""),
                embedding=emb_bytes,
                model_version=model_ver if vec else "",
            )
            session.add(row)

        session.commit()
        stats["files_processed"] += 1
        stats["chunks_written"] += len(chunks)

    return stats


def search_instruction_chunks(
    query: str,
    object_codes: list[str] | None = None,
    top_k: int = 5,
    session: Session = None,  # type: ignore[assignment]
    item_name_hint: str = "",
) -> list[dict]:
    """三级级联检索填报说明切片。

    Level 1 精确匹配：item_name == item_name_hint（有 hint 时）
    Level 2 关键词匹配：chunk_text 包含查询关键词，按命中计分
    Level 3 语义匹配：embedding 余弦相似度

    返回去重合并后的 top_k 条，精确 / 关键词命中排最前。
    """
    results: list[dict] = []
    seen_ids: set[int] = set()

    def _to_dict(c: RegInstructionChunk, score: float, match_type: str) -> dict:
        return {
            "chunk_text": c.chunk_text,
            "source_label": c.source_label,
            "reporting_object_code": c.reporting_object_code,
            "field_tag": c.field_tag,
            "item_name": c.item_name,
            "score": round(score, 4),
            "match_type": match_type,
        }

    def _base_stmt():
        stmt = select(RegInstructionChunk)
        if object_codes:
            stmt = stmt.where(RegInstructionChunk.reporting_object_code.in_(object_codes))
        return stmt

    # ── Level 1: 精确 item_name 匹配 ──────────────────────────────────────────
    if item_name_hint:
        exact = session.exec(
            _base_stmt().where(RegInstructionChunk.item_name == item_name_hint)
        ).all()
        for c in exact:
            if c.id not in seen_ids:
                results.append(_to_dict(c, 1.0, "exact"))
                seen_ids.add(c.id)

    # ── Level 2: 关键词匹配 ────────────────────────────────────────────────────
    keywords = _extract_keywords(query, item_name_hint)
    if keywords:
        all_chunks = session.exec(_base_stmt()).all()
        kw_scored = []
        for c in all_chunks:
            if c.id in seen_ids:
                continue
            score = sum(1 for kw in keywords if kw in c.chunk_text)
            if score > 0:
                kw_scored.append((score, c))
        kw_scored.sort(key=lambda x: x[0], reverse=True)
        for score, c in kw_scored[:top_k]:
            results.append(_to_dict(c, score / max(len(keywords), 1), "keyword"))
            seen_ids.add(c.id)

    # 如果精确 + 关键词已经够 top_k，直接返回
    if len(results) >= top_k:
        return results[:top_k]

    # ── Level 3: 语义匹配（兜底）──────────────────────────────────────────────
    try:
        query_vec = list(embed_texts([query])[0])
    except LLMClientError:
        return results[:top_k]

    vec_chunks = session.exec(
        _base_stmt().where(RegInstructionChunk.embedding.is_not(None))
    ).all()

    dim = len(query_vec)
    sem_scored = []
    for c in vec_chunks:
        if c.id in seen_ids or not c.embedding:
            continue
        vec = _bytes_to_vec(c.embedding)
        if len(vec) != dim:
            continue
        sim = _cosine(query_vec, vec)
        sem_scored.append((sim, c))

    sem_scored.sort(key=lambda x: x[0], reverse=True)
    needed = top_k - len(results)
    for sim, c in sem_scored[:needed]:
        results.append(_to_dict(c, sim, "semantic"))
        seen_ids.add(c.id)

    return results[:top_k]


# ──────────────────────────────────────────────────────────────────────────────
# 切片（v2：字段感知）
# ──────────────────────────────────────────────────────────────────────────────

def _split_into_chunks(text: str, label_prefix: str) -> list[dict]:
    """切片策略：

    - 遇到 `[字段标签. 字段名]：` 行，开启新切片，独立存储该字段定义。
    - 未匹配字段定义的段落按字符数合并，控制在 _MAX_CHUNK_CHARS 内。
    - 识别章节标题更新 current_section，写入 label。
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    chunks: list[dict] = []
    current_section = ""
    # 当前非字段段落缓冲
    buf_lines: list[str] = []

    def _flush_buf() -> None:
        """把段落缓冲切成若干不超过 _MAX_CHUNK_CHARS 的普通块。"""
        blob = "\n".join(buf_lines).strip()
        if not blob:
            return
        # 按字符数拆
        start = 0
        while start < len(blob):
            end = start + _MAX_CHUNK_CHARS
            snippet = blob[start:end].strip()
            if len(snippet) >= _MIN_CHUNK_CHARS:
                label = f"{label_prefix} · {current_section}" if current_section else label_prefix
                chunks.append({"text": snippet, "label": label,
                                "field_tag": "", "item_name": ""})
            start = end
        buf_lines.clear()

    i = 0
    while i < len(lines):
        line = lines[i]

        # 识别章节标题
        if line and len(line) < 35 and _is_section_header(line):
            current_section = line
            buf_lines.append(line)
            i += 1
            continue

        # 尝试匹配字段定义行
        m = _FIELD_DEF_RE.match(line)
        if m:
            # 先把前面攒的普通段落 flush
            _flush_buf()

            field_tag = m.group(1).strip()
            item_name = m.group(2).strip()

            # 收集该字段定义的全部内容（直到下一个字段定义 or 章节标题 or 空行后的新字段）
            field_lines = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                # 遇到下一个字段定义行，停止
                if _FIELD_DEF_RE.match(next_line):
                    break
                # 遇到章节标题，停止
                if next_line and len(next_line) < 35 and _is_section_header(next_line):
                    break
                field_lines.append(next_line)
                j += 1

            field_text = "\n".join(field_lines).strip()
            if len(field_text) >= _MIN_CHUNK_CHARS:
                label = f"{label_prefix} · {current_section}" if current_section else label_prefix
                chunks.append({
                    "text": field_text,
                    "label": label,
                    "field_tag": field_tag,
                    "item_name": item_name,
                })
            i = j
        else:
            # 普通行，加入缓冲
            if line:
                buf_lines.append(line)
            elif buf_lines:
                # 空行作为段落分隔
                blob = "\n".join(buf_lines).strip()
                if len(blob) >= _MAX_CHUNK_CHARS:
                    _flush_buf()
                else:
                    buf_lines.append("")
            i += 1

    _flush_buf()
    return chunks


def _is_section_header(line: str) -> bool:
    prefixes = ("第一", "第二", "第三", "第四", "第五", "第六",
                "一、", "二、", "三、", "四、", "五、", "六、",
                "（一）", "（二）", "（三）", "引言", "说明", "附注")
    return any(line.startswith(p) for p in prefixes)


def _extract_keywords(query: str, item_name_hint: str = "") -> list[str]:
    """从查询和 item_name 中提取2字以上中文关键词。"""
    text = query + " " + item_name_hint
    return list(dict.fromkeys(re.findall(r'[一-鿿]{2,8}', text)))


# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _vec_to_bytes(vec: list[float]) -> bytes:
    return struct.pack(f"<{len(vec)}f", *vec)


def _bytes_to_vec(raw: bytes) -> list[float]:
    dim = len(raw) // 4
    return list(struct.unpack(f"<{dim}f", raw))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _get_model_version() -> str:
    from app.core.config import get_settings
    return get_settings().embedding_model


def _ensure_columns(session: Session) -> None:
    """幂等添加 field_tag / item_name 列。

    MySQL TEXT 列不允许 DEFAULT，改用 VARCHAR(200)，SQLite 用 TEXT。
    """
    from sqlalchemy import text, inspect
    conn = session.connection()
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("reg_instruction_chunks")}

    # 判断数据库方言
    dialect = conn.dialect.name  # 'mysql' | 'sqlite' | 'postgresql'

    if dialect == "mysql":
        col_ddl = "VARCHAR(200) NULL"
    else:
        col_ddl = "TEXT DEFAULT ''"

    if "field_tag" not in cols:
        conn.execute(text(f"ALTER TABLE reg_instruction_chunks ADD COLUMN field_tag {col_ddl}"))
    if "item_name" not in cols:
        conn.execute(text(f"ALTER TABLE reg_instruction_chunks ADD COLUMN item_name {col_ddl}"))
    session.commit()
