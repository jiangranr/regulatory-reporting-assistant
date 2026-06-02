import re

from pydantic import BaseModel, Field

from app.services.hallucination_guard import is_signal_eligible_for_downstream


class ReportingChangeDraft(BaseModel):
    evidence_text: str
    reporting_system_code: str
    reporting_object_code: str
    reporting_item_code: str
    change_type: str
    confidence_score: float = 0.7
    indicator_hint: str = ""
    match_status: str = ""
    composite_match: dict = Field(default_factory=dict)
    change_axis: str = "UNCLEAR"  # ROW / COLUMN / CELL / UNCLEAR


# 新版：将文档画像的 change_signals 转换为 ReportingChangeDraft
# change_signals 是从 document_profiler 提取的精准变更信号（含表号、指标提示、变更类型、原文证据）

_CHANGE_TYPE_MAP: dict[str, str] = {
    "ADD": "INDICATOR_ADD",
    "MODIFY": "INDICATOR_SCOPE_CHANGE",
    "DELETE": "INDICATOR_REMOVE",
    "SCOPE_ADJUST": "INDICATOR_SCOPE_CHANGE",
    "INSTRUCTION_ADJUST": "INSTRUCTION_CHANGE",
    "UNCLEAR": "MANUAL_REVIEW",
}


def signals_to_changes(
    signals: list[dict],
    item_catalog: list[dict],
) -> list[ReportingChangeDraft]:
    """
    将 document_profiler 提取的 change_signals 转换为 ReportingChangeDraft。
    每条 signal 含 table_code、indicator_hint、change_type、evidence_text、confidence。
    item_catalog 为 reporting_seed 的 reporting_items 列表（list[dict]），
    用于将 indicator_hint 模糊匹配到具体的 item_code。
    """
    # 构建 table_code → items 索引
    items_by_table: dict[str, list[dict]] = {}
    for item in item_catalog:
        table_code = item["item_code"].split(".")[0]
        items_by_table.setdefault(table_code, []).append(item)

    changes: list[ReportingChangeDraft] = []
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        if not is_signal_eligible_for_downstream(signal):
            continue
        table_code = str(signal.get("table_code", "")).strip().upper()
        if not table_code:
            continue
        raw_change_type = str(signal.get("change_type", "UNCLEAR")).strip().upper()
        change_type = _CHANGE_TYPE_MAP.get(raw_change_type, "MANUAL_REVIEW")
        indicator_hint = str(signal.get("indicator_hint", "")).strip()
        evidence_text = str(signal.get("evidence_text", "")).strip()
        raw_axis = str(signal.get("change_axis", "")).strip().upper()
        change_axis = raw_axis if raw_axis in {"ROW", "COLUMN", "CELL", "UNCLEAR"} else "UNCLEAR"
        try:
            confidence = min(max(float(signal.get("confidence", 0.7)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.7

        table_items = items_by_table.get(table_code, [])
        matched_item_code = str(signal.get("matched_item_code", "")).strip()
        match_status = str(signal.get("match_status", "")).strip().upper()
        composite_match = signal.get("composite_match") if isinstance(signal.get("composite_match"), dict) else {}
        if matched_item_code:
            item_code = matched_item_code
        elif match_status in {"COMPOSITE_SEMANTIC_MATCH", "SEMANTIC_FIELD_MATCH"} and composite_match:
            item_code = _semantic_candidate_code(table_code, match_status, indicator_hint)
        elif match_status.startswith("UNMATCHED_"):
            item_code = ""
        else:
            item_code = _match_item(indicator_hint, table_items)

        changes.append(
            ReportingChangeDraft(
                evidence_text=evidence_text[:500],
                reporting_system_code="1104",
                reporting_object_code=table_code,
                reporting_item_code=item_code,
                change_type=change_type,
                confidence_score=confidence,
                indicator_hint=indicator_hint,
                match_status=match_status,
                composite_match=composite_match,
                change_axis=change_axis,
            )
        )

    if not changes:
        changes.append(
            ReportingChangeDraft(
                evidence_text="",
                reporting_system_code="1104",
                reporting_object_code="",
                reporting_item_code="",
                change_type="MANUAL_REVIEW",
                confidence_score=0.4,
            )
        )
    return changes


def _semantic_candidate_code(table_code: str, match_status: str, indicator_hint: str) -> str:
    kind = "COMPOSITE" if match_status == "COMPOSITE_SEMANTIC_MATCH" else "SEMANTIC_FIELD"
    label = re.sub(r"\s+", "", indicator_hint.strip()) or "UNKNOWN"
    label = re.sub(r"[/.]+", "_", label)
    return f"{table_code}.{kind}.{label}"


def _match_item(indicator_hint: str, items: list[dict]) -> str:
    """根据 indicator_hint 从 items 中找最匹配的 item_code。

    匹配优先级（高 → 低）：
      1. 整段子串互含 item_name —— 最强信号，命中即取最具体（item_code 最长）。
      2. "行 × 列" 双轴匹配 —— 把 hint 按 ×/x/× 拆成 (row_hint, col_hint)，
         分别和 row_label / column_label 标准化后做子串匹配，两轴都命中才算。
         这是 cell 级 item（如 G31 的 455 个 cell）的主路径，因为它们的
         item_name 形如 "1 行·D 列 · ..."，与 hint "债券投资合计 × D_因持有非底层"
         字符串差距很大，整段匹配根本无效。
      3. 没有可靠匹配时返回空字符串，交给人工复核。
    """
    if not items:
        return ""

    if indicator_hint:
        # ── 1. 整段子串
        hits = [
            it for it in items
            if (n := it.get("item_name", "")) and (indicator_hint in n or n in indicator_hint)
        ]
        if hits:
            return max(hits, key=lambda it: len(it.get("item_code", "")))["item_code"]

        # ── 1.5. 去前缀后的 row_label 归一化子串匹配
        # 解决 DB 行号与信号行号不一致的情况（如 Excel 把 "11.a.2" 解析成 "11.a.1"，
        # 但业务名称"通过第三方互联网平台吸收的个人活期存款"是相同的）。
        # 要求去前缀后至少 6 字符，避免"活期""贷款"等短标签产生误匹配。
        hint_norm = _norm_label(indicator_hint)
        if hint_norm and len(hint_norm) >= 6:
            norm_hits = [
                it for it in items
                if (rl := _norm_label(it.get("row_label", "")))
                and len(rl) >= 6
                and (hint_norm in rl or rl in hint_norm)
            ]
            if norm_hits:
                return max(norm_hits, key=lambda it: len(it.get("item_code", "")))["item_code"]

        # ── 2. 行 × 列 双轴
        parts = re.split(r"\s*[×xX]\s*", indicator_hint, maxsplit=1)
        col_hint = ""
        if len(parts) == 2:
            row_hint, col_hint = parts[0].strip(), parts[1].strip()
            rh, ch = _norm_label(row_hint), _norm_label(col_hint)
            if rh and ch:
                cands = []
                for it in items:
                    rl = _norm_label(it.get("row_label", ""))
                    cl = _norm_label(it.get("column_label", ""))
                    if not rl or not cl:
                        continue
                    if (rh in rl or rl in rh) and (ch in cl or cl in ch):
                        cands.append(it)
                if cands:
                    return max(cands, key=lambda it: len(it.get("item_code", "")))["item_code"]

        # ── 3. 只命中列：这是底层数据缺失"行语义标签"时的妥协路径。
        # 保留列维度的差异（A/B/C/D/E），代价是把 16 个不同 row 信号折叠到代表行（row 1）。
        # 比无差异 fallback 好得多。
        if col_hint:
            ch = _norm_label(col_hint)
            if ch:
                col_cands = [
                    it for it in items
                    if (cl := _norm_label(it.get("column_label", ""))) and (ch in cl or cl in ch)
                ]
                if col_cands:
                    # 在同列里挑 row_label 最有语义的（含中文字符）
                    chinese_re = re.compile(r"[一-鿿]")
                    def _semantic_score(it: dict) -> tuple[int, int]:
                        rl = it.get("row_label", "")
                        return (len(chinese_re.findall(rl)), -len(it.get("item_code", "")))
                    return max(col_cands, key=_semantic_score)["item_code"]

    # ── 4. 没有可靠字面匹配：保留为说明级信号，不伪造字段级影响项。
    return ""


def _norm_label(s: str) -> str:
    """归一化行/列标签，去掉序号前缀、标点、空白，便于子串比较。

    例子：
      "1.债券投资合计"                 → "债券投资合计"
      "11.a.1通过第三方互联网平台..." → "通过第三方互联网平台..."
      "11.a.2通过第三方互联网平台..." → "通过第三方互联网平台..."（与上行去前缀后相同，能互相命中）
      "D·因持有非底层资产..."         → "D因持有非底层资产..."
    """
    if not s:
        return ""
    # 去掉行号前缀，支持纯数字段（1. / 10.）和含字母段（11.a. / 11.a.1.）
    s = re.sub(r"^\d+(?:\.[a-zA-Z0-9]+)*\s*[\-．\.·]?\s*", "", s)
    # 去掉所有标点和空白
    s = re.sub(r"[·_\-．\.\s、，：（）\(\)]+", "", s)
    return s


# 兜底：关键词匹配（在无 profile 时使用）
def extract_reporting_changes(text: str) -> list[ReportingChangeDraft]:
    normalized = text.upper().replace("Ｇ", "G").replace("Ⅰ", "I").replace("_Ⅰ", "_I")
    rules = [
        ("G24", ["同业融入", "金融机构同业融入"], "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", 0.86),
        ("G21", ["流动性期限缺口", "期限缺口"], "G21.MAIN.LIQUIDITY_GAP_30D", 0.8),
        ("G25", ["流动性覆盖率", "优质流动性资产", "现金净流出"], "G25.PART_I.HQLA_BALANCE", 0.78),
        ("G27", ["同业存放", "主要负债"], "G27.MAIN.INTERBANK_DEPOSIT_BALANCE", 0.76),
        ("G31", ["投资业务", "债券投资", "底层资产"], "G31.PART_I.BOND_INVESTMENT_BALANCE", 0.74),
    ]
    changes: list[ReportingChangeDraft] = []
    for object_code, keywords, item_code, confidence in rules:
        if object_code in normalized or any(keyword in text for keyword in keywords):
            changes.append(
                ReportingChangeDraft(
                    evidence_text=text[:500],
                    reporting_system_code="1104",
                    reporting_object_code=object_code,
                    reporting_item_code=item_code,
                    change_type="INDICATOR_SCOPE_CHANGE",
                    confidence_score=confidence,
                )
            )
    if not changes:
        changes.append(
            ReportingChangeDraft(
                evidence_text=text[:500],
                reporting_system_code="1104",
                reporting_object_code="",
                reporting_item_code="",
                change_type="MANUAL_REVIEW",
                confidence_score=0.4,
            )
        )
    return changes
