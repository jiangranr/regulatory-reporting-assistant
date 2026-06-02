"""reporting_impact_analyzer.py

把监管变更信号 + 数据血缘上下文转化为结构化影响分析条目。

LLM 介入策略（2026-06-02 升级）：
- mock_ai=True  → 关键词路由 mock，能区分 8 种类型，不调 LLM
- mock_ai=False → 每个 impact 调一次 LLM，失败时自动 fallback 到 mock
- semantic 命中路径（COMPOSITE/SEMANTIC_FIELD_MATCH）继续走原有逻辑，不走 LLM
  （那条路径字段已由 composite_match 明确给出，LLM 加不了太多信息）
"""

from __future__ import annotations

import json
import logging
import re

from pydantic import BaseModel

from app.core.config import get_settings
from app.models.enums import RiskLevel
from app.services.llm_client import LLMClientError, complete_json
from app.services.reporting_change_extractor import ReportingChangeDraft
from app.services.reporting_seed import ReportingSeedCatalog
from app.services.ticket_scope_classifier import classify_scope_range_tickets

logger = logging.getLogger(__name__)

# =====================================================================
#  8 种影响类型定义（展示给评委 / 业务人员 / LLM prompt）
# =====================================================================
IMPACT_TYPES: dict[str, str] = {
    "INDICATOR_SCOPE":    "指标口径调整 — 统计范围、定义或计算基础变化，需重新确认指标含义与取数逻辑",
    "REPORT_STRUCTURE":   "报表结构调整 — 行列新增、删除或改名，报送字段层需适配",
    "SOURCE_FIELD_CHANGE":"源字段变更 — 源系统字段改名、类型或精度变化，血缘映射需更新",
    "ETL_LOGIC_CHANGE":   "加工逻辑变更 — 计算公式、汇总规则或分类逻辑变化，ETL 需改写",
    "INSTITUTION_SCOPE":  "机构范围调整 — 法人合并口径、分支机构范围或对手分类变化",
    "VALIDATION_RULE":    "校验规则变更 — 勾稽关系、跨表校验或数据质量规则变化",
    "SUPPLEMENT_DATA":    "补录要求新增 — 新增人工填报项或补充数据项",
    "FREQUENCY_DEADLINE": "频度/时限调整 — 报送频率或上报截止日期变化",
}

IMPACT_TYPE_KEYS = list(IMPACT_TYPES.keys())

# =====================================================================
#  LLM 系统提示
# =====================================================================
_SYSTEM_PROMPT = """你是一个金融监管报送影响分析专家，专注于银行1104报送体系。

给定一条监管变更信号和该指标的数据血缘上下文，你需要完成以下三项任务：

【任务1】判断影响类型
从以下8种类型中选择最匹配的1种（只返回key，不要返回说明文字）：
- INDICATOR_SCOPE: 指标口径调整，统计范围/定义/计算基础变化
- REPORT_STRUCTURE: 报表结构调整，行列新增/删除/改名
- SOURCE_FIELD_CHANGE: 源字段变更，字段改名/类型/精度变化
- ETL_LOGIC_CHANGE: 加工逻辑变更，计算公式/汇总规则/分类逻辑变化
- INSTITUTION_SCOPE: 机构范围调整，法人合并口径/分支范围/对手分类变化
- VALIDATION_RULE: 校验规则变更，勾稽关系/跨表校验/数据质量规则
- SUPPLEMENT_DATA: 补录要求新增，人工填报/补充数据项
- FREQUENCY_DEADLINE: 频度/时限调整，报送频率/截止日期变化

【任务2】写影响分析理由
用2-3句简洁的业务语言解释：这次变更具体影响了什么、为什么影响、哪些系统/字段需要关注。
避免复制粘贴证据原文，要站在数据团队负责人的视角说清楚。

【任务3】写推荐处置动作
用1-2句话写出最关键的处置步骤（比如"需先与业务确认XXX口径，再由数据开发修改YYY的ETL逻辑"）。
要有指向性，不要泛泛而谈。

严格按以下JSON格式返回，不要包含其他内容：
{
  "impact_type": "<8种类型key之一>",
  "impact_reason": "<2-3句影响分析>",
  "recommended_action": "<1-2句处置动作>"
}"""


# =====================================================================
#  数据模型
# =====================================================================
class ReportingImpactDraft(BaseModel):
    reporting_item_code: str
    reporting_item_name: str = ""
    impact_type: str
    impacted_reporting_field: str = ""
    impacted_reporting_field_name: str = ""
    impacted_source_fields: list[str] = []
    impacted_source_field_details: list[dict[str, str]] = []
    impacted_lineage_roles: list[str] = []
    impact_reason: str
    recommended_action: str
    ticket_parent_type: str = ""
    required_sub_ticket_types: list[str] = []
    conditional_sub_ticket_types: list[str] = []
    sub_ticket_triggers: dict[str, str] = {}
    confidence_level: str = "MEDIUM"
    risk_level: RiskLevel = RiskLevel.MEDIUM
    change_axis: str = "UNCLEAR"  # ROW / COLUMN / CELL / UNCLEAR
    llm_analyzed: bool = False    # 标记是否经过真实 LLM 分析（便于前端展示 AI 标签）


# =====================================================================
#  主函数
# =====================================================================
def analyze_reporting_impacts(
    changes: list[ReportingChangeDraft],
    catalog: ReportingSeedCatalog,
) -> list[ReportingImpactDraft]:
    lineage_by_item: dict[str, list[dict[str, str]]] = {}
    for lineage in catalog.lineage:
        lineage_by_item.setdefault(lineage["reporting_item_code"], []).append(lineage)

    item_names = {item["item_code"]: item["item_name"] for item in catalog.reporting_items}
    field_names = {field["field_code"]: field.get("field_name", "") for field in catalog.data_fields}

    # 按 reporting_item_code 去重合并多信号
    grouped: dict[str, list[ReportingChangeDraft]] = {}
    for change in changes:
        if not change.reporting_item_code:
            continue
        grouped.setdefault(change.reporting_item_code, []).append(change)

    settings = get_settings()
    impacts: list[ReportingImpactDraft] = []

    for item_code, group in grouped.items():
        change = max(group, key=lambda c: c.confidence_score)
        signal_count = len(group)

        # change_axis 取出现最多的（非 UNCLEAR）
        axis_counts: dict[str, int] = {}
        for c in group:
            axis_counts[c.change_axis] = axis_counts.get(c.change_axis, 0) + 1
        axis_counts.pop("UNCLEAR", None)
        group_axis = max(axis_counts, key=lambda k: axis_counts[k]) if axis_counts else "UNCLEAR"

        # composite / semantic 路径：字段已明确，不走 LLM
        semantic_impact = _semantic_change_to_impact(change)
        if semantic_impact is not None:
            impacts.append(semantic_impact.model_copy(update={"change_axis": group_axis}))
            continue

        # 构建血缘上下文
        lineage_rows = lineage_by_item.get(change.reporting_item_code, [])
        reporting_rows = [r for r in lineage_rows if r["lineage_role"] == "REPORT_FIELD"]
        source_rows = [
            r for r in lineage_rows
            if r["lineage_role"] in {"SOURCE_FIELD", "FILTER_FIELD", "DIMENSION_FIELD"}
        ]
        reporting_fields = [r["data_field_code"] for r in reporting_rows]
        source_fields    = [r["data_field_code"] for r in source_rows]
        roles = list(dict.fromkeys(r["lineage_role"] for r in lineage_rows))
        detail_rows = [*reporting_rows, *source_rows]

        item_name = item_names.get(change.reporting_item_code, change.reporting_item_code)
        reporting_field = reporting_fields[0] if reporting_fields else ""

        ticket_scope = classify_scope_range_tickets(
            change_type=change.change_type,
            lineage_roles=roles,
            source_fields=source_fields,
            evidence_text=change.evidence_text,
        )

        # ── LLM 分析 ─────────────────────────────────────────────
        impact_type, impact_reason, recommended_action, llm_analyzed = _get_impact_analysis(
            change=change,
            item_name=item_name,
            signal_count=signal_count,
            lineage_rows=lineage_rows,
            source_rows=source_rows,
            field_names=field_names,
            use_llm=not settings.mock_ai,
        )

        impacts.append(
            ReportingImpactDraft(
                reporting_item_code=change.reporting_item_code,
                reporting_item_name=item_name,
                impact_type=impact_type,
                impacted_reporting_field=reporting_field,
                impacted_reporting_field_name=_field_name_for_code(
                    reporting_field, reporting_rows, field_names,
                ),
                impacted_source_fields=list(dict.fromkeys(source_fields)),
                impacted_source_field_details=_source_field_details(detail_rows, field_names),
                impacted_lineage_roles=roles,
                impact_reason=impact_reason,
                recommended_action=recommended_action,
                ticket_parent_type=ticket_scope.ticket_parent_type,
                required_sub_ticket_types=ticket_scope.required_sub_ticket_types,
                conditional_sub_ticket_types=ticket_scope.conditional_sub_ticket_types,
                sub_ticket_triggers=ticket_scope.sub_ticket_triggers,
                confidence_level="HIGH" if change.confidence_score >= 0.8 else "MEDIUM",
                risk_level=RiskLevel.HIGH if change.reporting_object_code in {"G24", "G21", "G25"} else RiskLevel.MEDIUM,
                change_axis=group_axis,
                llm_analyzed=llm_analyzed,
            )
        )
    return impacts


# =====================================================================
#  LLM / mock 分析入口
# =====================================================================
def _get_impact_analysis(
    change: ReportingChangeDraft,
    item_name: str,
    signal_count: int,
    lineage_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    field_names: dict[str, str],
    use_llm: bool,
) -> tuple[str, str, str, bool]:
    """返回 (impact_type, impact_reason, recommended_action, llm_analyzed)"""
    if use_llm:
        try:
            result = _llm_analyze_impact(change, item_name, signal_count, lineage_rows, source_rows, field_names)
            return (*result, True)
        except (LLMClientError, Exception) as exc:
            logger.warning("LLM impact analysis failed for %s, falling back to mock: %s",
                           change.reporting_item_code, exc)

    return (*_mock_analyze_impact(change, item_name, signal_count, source_rows), False)


# =====================================================================
#  真实 LLM 分析
# =====================================================================
def _llm_analyze_impact(
    change: ReportingChangeDraft,
    item_name: str,
    signal_count: int,
    lineage_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    field_names: dict[str, str],
) -> tuple[str, str, str]:
    """调 LLM 生成影响类型 + 分析理由 + 推荐动作。"""

    # 构建血缘摘要（避免 prompt 过长）
    source_summary = _build_source_summary(source_rows, field_names, max_items=6)

    # 系统/源系统分布
    systems = list(dict.fromkeys(
        r.get("system_name") or r.get("system_code", "未知系统")
        for r in lineage_rows
        if r.get("lineage_role") in {"SOURCE_FIELD", "FILTER_FIELD"}
    ))
    system_str = "、".join(systems[:4]) if systems else "未知"

    user_msg = f"""## 监管变更信号

指标代码：{change.reporting_item_code}
指标名称：{item_name}
变更类型：{change.change_type}
置信度：{change.confidence_score:.0%}
合并信号数：{signal_count}

变更证据原文：
{(change.evidence_text or '（无原文）')[:600]}

## 数据血缘上下文

涉及源系统：{system_str}
源字段列表：
{source_summary}

## 要求

请根据以上信息完成影响分析，严格按JSON格式输出。"""

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": user_msg},
    ]

    result = _call_llm_with_json_fallback(messages)

    impact_type = str(result.get("impact_type", "")).strip()
    if impact_type not in IMPACT_TYPES:
        impact_type = "INDICATOR_SCOPE"  # 兜底

    impact_reason      = str(result.get("impact_reason", "")).strip()
    recommended_action = str(result.get("recommended_action", "")).strip()

    if not impact_reason:
        impact_reason = f"{item_name}发生{change.change_type}，需复核数据血缘与加工逻辑。"
    if not recommended_action:
        recommended_action = "生成对应类型工单，由相关团队协同处理。"

    return impact_type, impact_reason, recommended_action


def _call_llm_with_json_fallback(messages: list[dict]) -> dict:
    """调 LLM，兼容三种响应格式：
    1. 纯 JSON 字符串
    2. Markdown 代码块包裹的 JSON （```json ... ```）
    3. 文本中嵌套的 JSON 对象（用正则提取第一个 {...}）
    任一格式失败则抛 LLMClientError。
    """
    try:
        result, _raw, _model = complete_json(messages)
        return result
    except LLMClientError:
        pass

    # complete_json 失败：直接取原始 content 再尝试提取
    import httpx
    settings = get_settings()
    base_url = settings.llm_api_base.rstrip("/")
    payload = {"model": settings.llm_model, "messages": messages}
    try:
        with httpx.Client(timeout=settings.llm_timeout_seconds) as client:
            resp = client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        raise LLMClientError(f"LLM raw call failed: {exc}") from exc

    # 1. 去掉 markdown 代码块
    stripped = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("`").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # 2. 正则找第一个 {...} 块
    m = re.search(r"\{[\s\S]*\}", content)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise LLMClientError(f"Cannot extract JSON from LLM response: {content[:200]}")


def _build_source_summary(
    source_rows: list[dict[str, str]],
    field_names: dict[str, str],
    max_items: int = 6,
) -> str:
    lines = []
    seen: set[str] = set()
    for row in source_rows[:max_items]:
        code = row.get("data_field_code", "")
        if not code or code in seen:
            continue
        seen.add(code)
        name = row.get("data_field_name") or field_names.get(code, code)
        role = row.get("lineage_role", "SOURCE_FIELD")
        system = row.get("system_name") or row.get("system_code", "")
        role_zh = {"SOURCE_FIELD": "来源字段", "FILTER_FIELD": "过滤条件", "DIMENSION_FIELD": "维度字段"}.get(role, role)
        lines.append(f"  - [{role_zh}] {code}（{name}）@ {system}")
    if not lines:
        return "  （暂无血缘数据）"
    return "\n".join(lines)


# =====================================================================
#  关键词路由 Mock（mock_ai=True 时使用）
#  比原来的模板字符串强：能区分 8 种类型
# =====================================================================

# 每种类型的触发关键词（按优先级排列，越靠前权重越高）
_MOCK_RULES: list[tuple[str, list[str]]] = [
    ("FREQUENCY_DEADLINE", [
        "频率", "频度", "月报", "季报", "年报", "周报",
        "截止", "时限", "工作日", "T+", "上报日期",
        "提交时间", "报送时间", "不再报送", "停报",
    ]),
    ("REPORT_STRUCTURE", [
        "新增列", "新增行", "删除列", "删除行",
        "新增字段", "删除字段", "改名", "列名",
        "行名", "表头", "报表结构", "增加报送项",
        "停止填报", "不再填列",
    ]),
    ("SUPPLEMENT_DATA", [
        "人工填报", "补录", "手工录入", "人工维护",
        "补充填写", "额外说明", "附注", "备注栏",
    ]),
    ("VALIDATION_RULE", [
        "校验规则", "勾稽", "逻辑关系", "合计行",
        "数据质量", "一致性校验", "误差范围", "允许偏差",
    ]),
    ("INSTITUTION_SCOPE", [
        "法人", "合并", "分支机构", "境内外", "机构范围",
        "对手方", "交易对手", "金融机构类型", "机构类别",
        "纳入范围", "排除范围", "并表",
    ]),
    ("ETL_LOGIC_CHANGE", [
        "计算方法", "计算公式", "加工逻辑", "汇总方式",
        "分类方法", "折算", "换算", "归集", "汇总口径",
        "加权", "平均", "日均", "月均",
    ]),
    ("SOURCE_FIELD_CHANGE", [
        "字段名称", "字段定义", "数据类型", "精度",
        "来源系统", "源系统", "字段映射", "取数来源",
    ]),
    # 兜底：口径调整
    ("INDICATOR_SCOPE", [
        "口径", "统计范围", "定义", "认定标准",
        "认定条件", "填报范围", "适用范围", "包括",
        "不包括", "纳入", "剔除", "修订",
    ]),
]

_HIGH_RISK_OBJECTS = {"G24", "G21", "G25"}


def _mock_analyze_impact(
    change: ReportingChangeDraft,
    item_name: str,
    signal_count: int,
    source_rows: list[dict[str, str]],
) -> tuple[str, str, str]:
    """关键词路由决策影响类型，生成可读分析理由和推荐动作。"""
    evidence = (change.evidence_text or "") + " " + (change.indicator_hint or "")
    impact_type = _keyword_classify(evidence)

    # 组装分析理由：类型说明 + 变更轴 + 信号融合数
    type_desc = IMPACT_TYPES.get(impact_type, "")
    axis_note = ""
    if change.change_axis == "ROW":
        axis_note = "（行级变更）"
    elif change.change_axis == "COLUMN":
        axis_note = "（列级变更）"
    elif change.change_axis == "CELL":
        axis_note = "（单元格级变更）"

    signal_note = f"（合并 {signal_count} 条相关变更信号）" if signal_count > 1 else ""

    # 涉及的源系统
    systems = list(dict.fromkeys(
        r.get("system_name") or r.get("system_code", "")
        for r in source_rows if r.get("system_name") or r.get("system_code")
    ))
    system_note = f"涉及 {'/'.join(systems[:3])} 等系统。" if systems else ""

    impact_reason = (
        f"{item_name}{axis_note}发生{_change_type_zh(change.change_type)}{signal_note}，"
        f"影响类型判断为「{type_desc.split('—')[0].strip()}」。"
        f"{_type_specific_reason(impact_type, change, source_rows)}"
        f"{system_note}"
    )

    recommended_action = _type_specific_action(impact_type, change, source_rows)

    return impact_type, impact_reason, recommended_action


def _keyword_classify(text: str) -> str:
    """在证据文本中按规则表查关键词，返回命中优先级最高的类型。"""
    for impact_type, keywords in _MOCK_RULES:
        for kw in keywords:
            if kw in text:
                return impact_type
    return "INDICATOR_SCOPE"


def _change_type_zh(change_type: str) -> str:
    return {
        "ADD": "新增", "MODIFY": "修改", "DELETE": "删除",
        "SCOPE_ADJUST": "口径调整", "INSTRUCTION_ADJUST": "说明调整",
        "UNCLEAR": "变更",
    }.get(change_type, change_type)


def _type_specific_reason(
    impact_type: str,
    change: ReportingChangeDraft,
    source_rows: list[dict[str, str]],
) -> str:
    """根据影响类型生成针对性的补充说明句。"""
    source_count = len({r.get("data_field_code") for r in source_rows if r.get("data_field_code")})
    filter_count = len([r for r in source_rows if r.get("lineage_role") == "FILTER_FIELD"])
    dim_count    = len([r for r in source_rows if r.get("lineage_role") == "DIMENSION_FIELD"])

    if impact_type == "INDICATOR_SCOPE":
        return f"现有血缘关联 {source_count} 个源字段，需重新对齐统计口径后再验证取数逻辑。"
    if impact_type == "REPORT_STRUCTURE":
        return "报送字段层需新增/删除对应映射，同步触发数据开发和报送加工工单。"
    if impact_type == "ETL_LOGIC_CHANGE":
        return f"血缘中有 {source_count} 个来源字段，其汇总/计算规则需同步更新。"
    if impact_type == "INSTITUTION_SCOPE":
        return f"血缘包含 {dim_count} 个维度字段，对手/机构维度分类码值需随监管要求更新。"
    if impact_type == "VALIDATION_RULE":
        return "需更新数据质量平台的勾稽检查规则，并重跑历史回归验证。"
    if impact_type == "SOURCE_FIELD_CHANGE":
        return f"源字段映射路径共 {source_count} 条，字段层变化会导致全部映射失效，需重新确认。"
    if impact_type == "SUPPLEMENT_DATA":
        return "涉及人工填报项，需与业务条线确认数据来源及填报流程。"
    if impact_type == "FREQUENCY_DEADLINE":
        return "ETL 调度计划和报送系统截止配置均需同步调整，避免逾期风险。"
    return ""


def _type_specific_action(
    impact_type: str,
    change: ReportingChangeDraft,
    source_rows: list[dict[str, str]],
) -> str:
    """根据影响类型生成推荐处置动作。"""
    if impact_type == "INDICATOR_SCOPE":
        return "生成口径确认工单交业务复核，确认后由数据治理更新血缘并触发报送加工工单。"
    if impact_type == "REPORT_STRUCTURE":
        return "生成报表结构工单，由报送管理岗更新报送目录，数据开发同步适配 ETL 和报送加工。"
    if impact_type == "ETL_LOGIC_CHANGE":
        return "生成数据映射工单 + 报送加工工单，由数据开发修改 ETL 逻辑并经测试回归后上线。"
    if impact_type == "INSTITUTION_SCOPE":
        return "生成口径确认工单，与业务确认法人合并/机构范围口径，更新 CRMS 维表并触发数据开发工单。"
    if impact_type == "VALIDATION_RULE":
        return "生成校验规则工单，由数据质量团队更新勾稽规则，并重跑近 3 期历史数据验证。"
    if impact_type == "SOURCE_FIELD_CHANGE":
        return "生成血缘建链工单，由数据治理重新确认字段映射，源系统团队提供变更字段的兼容映射方案。"
    if impact_type == "SUPPLEMENT_DATA":
        return "生成口径确认工单，与业务条线确认补录数据来源及责任人，数据治理建立补录字段的血缘记录。"
    if impact_type == "FREQUENCY_DEADLINE":
        return "生成报送任务工单，由报送管理岗调整调度计划和截止配置，并通知相关源系统团队提前备数。"
    return "生成综合影响工单，由各责任团队协同评估后分别处置。"


# =====================================================================
#  semantic / composite 命中路径（保持原有逻辑）
# =====================================================================
def _semantic_change_to_impact(change: ReportingChangeDraft) -> ReportingImpactDraft | None:
    if change.match_status not in {"COMPOSITE_SEMANTIC_MATCH", "SEMANTIC_FIELD_MATCH"}:
        return None
    match = change.composite_match if isinstance(change.composite_match, dict) else {}
    if not match:
        return None

    field_roles: list[tuple[str, str, str]] = []
    for field in match.get("measure_fields") or []:
        if not isinstance(field, dict):
            continue
        field_code = str(field.get("field_code", "")).strip()
        if not field_code:
            continue
        field_roles.append((
            field_code,
            _normalise_semantic_field_role(str(field.get("field_role", ""))),
            str(field.get("field_name") or "").strip(),
        ))

    known_fields = {fc for fc, _, _ in field_roles}
    for field_code in match.get("measure_field_codes") or []:
        field_code = str(field_code).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((field_code, "SOURCE_FIELD", ""))
            known_fields.add(field_code)

    conditions = match.get("filter_conditions") or match.get("conditions") or []
    for condition in conditions:
        if not isinstance(condition, dict):
            continue
        field_code = str(condition.get("field_code", "")).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((
                field_code,
                "FILTER_FIELD",
                str(condition.get("field_name") or "").strip(),
            ))
            known_fields.add(field_code)

    for field_code in match.get("condition_field_codes") or []:
        field_code = str(field_code).strip()
        if field_code and field_code not in known_fields:
            field_roles.append((field_code, "FILTER_FIELD", ""))
            known_fields.add(field_code)

    if not field_roles:
        return None

    impacted_fields = [fc for fc, _, _ in field_roles]
    roles = list(dict.fromkeys(role for _, role, _ in field_roles))
    ticket_scope = classify_scope_range_tickets(
        change_type=change.change_type,
        lineage_roles=roles,
        source_fields=impacted_fields,
        evidence_text=change.evidence_text,
    )

    indicator_hint = (
        str(match.get("indicator_hint") or "").strip()
        or change.indicator_hint
        or change.reporting_item_code
    )
    match_type = str(match.get("match_type") or change.match_status)
    if match_type == "SEMANTIC_FIELD_MATCH":
        impact_type = "SEMANTIC_FIELD_SCOPE"
        reason = (
            f"{indicator_hint}未精确落格，已按报表范围内语义字段生成候选影响项，"
            "需要复核字段含义、口径适用范围和后续加工规则。"
        )
    else:
        impact_type = "COMPOSITE_SEMANTIC_SCOPE"
        measure_phrase   = str(match.get("measure_phrase") or "度量").strip()
        condition_phrase = str(match.get("condition_phrase") or "分类条件").strip()
        combo = f"{condition_phrase} + {measure_phrase}"
        reason = (
            f"{indicator_hint}未精确落格，已按「{combo}」"
            "生成组合候选影响项，需要复核金额字段、过滤条件和迁移口径。"
        )

    return ReportingImpactDraft(
        reporting_item_code=change.reporting_item_code,
        reporting_item_name=indicator_hint,
        impact_type=impact_type,
        impacted_reporting_field=indicator_hint,
        impacted_reporting_field_name=indicator_hint,
        impacted_source_fields=impacted_fields,
        impacted_source_field_details=[
            {"code": fc, "name": fname or fc, "role": role}
            for fc, role, fname in field_roles
        ],
        impacted_lineage_roles=roles,
        impact_reason=reason,
        recommended_action=(
            "生成口径确认工单、字段映射复核工单、报送加工调整工单和回归测试工单；"
            "保持待确认状态，人工确认后再固化到正式报送口径。"
        ),
        ticket_parent_type=ticket_scope.ticket_parent_type,
        required_sub_ticket_types=ticket_scope.required_sub_ticket_types,
        conditional_sub_ticket_types=ticket_scope.conditional_sub_ticket_types,
        sub_ticket_triggers=ticket_scope.sub_ticket_triggers,
        confidence_level="HIGH" if change.confidence_score >= 0.8 else "MEDIUM",
        risk_level=RiskLevel.MEDIUM,
    )


# =====================================================================
#  工具函数
# =====================================================================
def _normalise_semantic_field_role(field_role: str) -> str:
    role = field_role.strip().upper()
    if role in {"REPORT_FIELD", "REPORT_MEASURE_FIELD"}:
        return "REPORT_FIELD"
    if role in {"FILTER_FIELD", "CONDITION_FIELD"}:
        return "FILTER_FIELD"
    if role == "DIMENSION_FIELD":
        return "DIMENSION_FIELD"
    return "SOURCE_FIELD"


def _field_name_for_code(
    field_code: str,
    lineage_rows: list[dict[str, str]],
    field_names: dict[str, str],
) -> str:
    if not field_code:
        return ""
    for row in lineage_rows:
        if row.get("data_field_code") == field_code:
            return row.get("data_field_name") or field_names.get(field_code, "") or field_code
    return field_names.get(field_code, "") or field_code


def _source_field_details(
    lineage_rows: list[dict[str, str]],
    field_names: dict[str, str],
) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in lineage_rows:
        code = row.get("data_field_code", "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        details.append({
            "code":        code,
            "name":        row.get("data_field_name") or field_names.get(code, "") or code,
            "role":        row.get("lineage_role", ""),
            "system_code": row.get("system_code", "") or "",
            "system_name": row.get("system_name", "") or "",
            "system_type": row.get("system_type", "") or "",
            "owner_team":  row.get("owner_team", "") or "",
        })
    return details
