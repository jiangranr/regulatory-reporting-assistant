"""
变更分级与母单类型判定。

输入：变更信号 + 影响项 + 文档原文
输出：(母单类型, 严重等级, 打分依据)

判定顺序：
  1. 硬规则强制升级到 L4 / 强制降级到 L1
  2. 否则按维度打分映射到 L1/L2/L3/L4
"""

from dataclasses import dataclass, field

from app.models.enums import ChangeTicketType, SeverityLevel
from app.services.reporting_change_extractor import ReportingChangeDraft
from app.services.reporting_impact_analyzer import ReportingImpactDraft


# ----------------- 关键词常量 -----------------
# 严重等级硬规则用的关键词（仍保留）：信号强、低噪声，只用来"加重"等级，不用来判型。
_FORCE_L4_KEYWORDS_RETRO = ("追溯", "重算", "补报", "历史数据修正", "历史数据重报")
_FORCE_L4_KEYWORDS_MAJOR = ("重大调整", "结构性变化", "结构性调整", "重大变更")

# 母单类型判定不再使用原文关键词。
# 信号来源：上游 document_profiler/change_extractor 已把监管原文结构化为 change_signals。
# 下游母单分类只看 change_type 集合 + object_code 是否在存量目录。
#
# 当前 change_type 枚举（来自 reporting_change_extractor._CHANGE_TYPE_MAP）：
#   INDICATOR_ADD / INDICATOR_SCOPE_CHANGE / INDICATOR_REMOVE / INSTRUCTION_CHANGE / MANUAL_REVIEW
#
# 以下三类母单当前没有对应的上游结构化信号，需要后续扩展 document_profiler
# 让其在 change_signals 里额外产出，再由本模块识别（见下面 TODO）：
#   - INSTITUTION_FREQ_CHANGE  机构范围/报送频度调整
#   - VALIDATION_CHANGE        校验规则变更
#   - REPORT_DECOMMISSION      报表停报
# 在上游支持前，这三类只能由人工调级覆盖。

_INDICATOR_ADD_CHANGE_TYPES = {"INDICATOR_ADD"}
_INDICATOR_REMOVE_CHANGE_TYPES = {"INDICATOR_REMOVE"}
_SCOPE_CHANGE_TYPES = {"INDICATOR_SCOPE_CHANGE"}
_INSTRUCTION_CHANGE_TYPES = {"INSTRUCTION_CHANGE"}
_UNCLEAR_CHANGE_TYPES = {"MANUAL_REVIEW"}


@dataclass
class SeverityScore:
    level: SeverityLevel
    score: int
    triggered_signals: list[str] = field(default_factory=list)
    forced_reason: str | None = None


@dataclass
class ChangeClassification:
    change_ticket_type: ChangeTicketType
    severity: SeverityScore


# ----------------- 母单类型判定 -----------------


def _classify_change_ticket_type(
    changes: list[ReportingChangeDraft],
    existing_report_codes: set[str],
) -> ChangeTicketType:
    """
    只根据上游结构化信号判定母单类型。

    判定顺序（优先级从高到低）：
      1. 报表新增：变更命中的 object_code 全部不在存量目录里
      2. 报表停报：所有变更都是 INDICATOR_REMOVE，且覆盖了同一张表的全部参与变更项
      3. 指标新增：change_types 主要为 INDICATOR_ADD
      4. 口径调整：change_types 含 INDICATOR_SCOPE_CHANGE 或 INSTRUCTION_CHANGE
      5. 人工复核：全部信号无法识别
      6. 报表修订：其他

    TODO：INSTITUTION_FREQ_CHANGE / VALIDATION_CHANGE 需要 document_profiler
    在 change_signals 里产出 INSTITUTION_CHANGE / VALIDATION_CHANGE 两个新 change_type
    后才能从规则识别；当前只能依赖人工调级。
    """
    referenced_objects = {c.reporting_object_code for c in changes if c.reporting_object_code}
    if referenced_objects and not (referenced_objects & existing_report_codes):
        return ChangeTicketType.REPORT_ONBOARDING

    change_types = {c.change_type for c in changes if c.change_type}

    # 整表删除：所有变更都是 INDICATOR_REMOVE → 报表停报
    if change_types and change_types <= _INDICATOR_REMOVE_CHANGE_TYPES:
        return ChangeTicketType.REPORT_DECOMMISSION

    if change_types & _INDICATOR_ADD_CHANGE_TYPES:
        return ChangeTicketType.INDICATOR_ADD

    if change_types & _SCOPE_CHANGE_TYPES:
        return ChangeTicketType.SCOPE_ADJUSTMENT

    if change_types & _INSTRUCTION_CHANGE_TYPES:
        return ChangeTicketType.SCOPE_ADJUSTMENT  # 填报说明调整归口为口径调整

    if not change_types or change_types <= _UNCLEAR_CHANGE_TYPES:
        return ChangeTicketType.MANUAL_REVIEW

    return ChangeTicketType.REPORT_REVISION


# ----------------- 严重等级打分 -----------------


def _hard_rules_force_l4(
    change_ticket_type: ChangeTicketType,
    changes: list[ReportingChangeDraft],
    document_text: str,
) -> str | None:
    """命中任意硬规则则强制 L4，返回原因。"""
    if change_ticket_type in {
        ChangeTicketType.REPORT_ONBOARDING,
        ChangeTicketType.REPORT_DECOMMISSION,
    }:
        return f"母单类型 {change_ticket_type.value} 直接定为 L4"

    systems = {c.reporting_system_code for c in changes if c.reporting_system_code}
    if len(systems) >= 2:
        return f"影响 {len(systems)} 个报送体系（{', '.join(sorted(systems))}），跨体系强制 L4"

    text = document_text or ""
    for kw in _FORCE_L4_KEYWORDS_RETRO:
        if kw in text:
            return f"监管原文出现「{kw}」，涉及历史追溯强制 L4"
    for kw in _FORCE_L4_KEYWORDS_MAJOR:
        if kw in text:
            return f"监管原文出现「{kw}」，定性为重大变更强制 L4"

    return None


def _hard_rules_force_l1(
    change_ticket_type: ChangeTicketType,
    changes: list[ReportingChangeDraft],
    impacts: list[ReportingImpactDraft],
) -> str | None:
    """命中任意硬规则则强制 L1，返回原因。"""
    change_types = {c.change_type for c in changes}
    # 仅填报说明文字调整、且没有命中血缘
    if change_types == _INSTRUCTION_CHANGE_TYPES:
        any_lineage = any(
            impact.impacted_reporting_field or impact.impacted_source_fields
            for impact in impacts
        )
        if not any_lineage:
            return "仅填报说明文字调整且未命中血缘，强制 L1"
    return None


def _score_signals(
    changes: list[ReportingChangeDraft],
    impacts: list[ReportingImpactDraft],
) -> tuple[int, list[str]]:
    """
    打分只用结构化信号，不看文档原文关键词。
    每个维度独立累加；signals 列表用于审计展示。
    """
    score = 0
    signals: list[str] = []

    # 维度 1：影响指标数
    indicator_codes = {
        impact.reporting_item_code for impact in impacts if impact.reporting_item_code
    }
    n_items = len(indicator_codes)
    if n_items >= 6:
        score += 5
        signals.append(f"影响指标数 {n_items} 个 (+5)")
    elif n_items >= 2:
        score += 2
        signals.append(f"影响指标数 {n_items} 个 (+2)")

    # 维度 2：影响报送字段数
    field_set: set[str] = set()
    for impact in impacts:
        if impact.impacted_reporting_field:
            field_set.add(impact.impacted_reporting_field)
    n_fields = len(field_set)
    if n_fields >= 5:
        score += 4
        signals.append(f"影响报送字段 {n_fields} 个 (+4)")
    elif n_fields >= 2:
        score += 2
        signals.append(f"影响报送字段 {n_fields} 个 (+2)")

    # 维度 3：跨报送对象（多张表）
    object_codes = {c.reporting_object_code for c in changes if c.reporting_object_code}
    if len(object_codes) >= 2:
        score += 3
        signals.append(f"跨 {len(object_codes)} 张报表 (+3)")

    # 维度 4：是否新增源字段（启发式——存在指标但没有任何源字段命中，很可能要新增源字段）
    has_indicator_without_source = any(
        impact.reporting_item_code and not impact.impacted_source_fields for impact in impacts
    )
    if has_indicator_without_source:
        score += 4
        signals.append("存在指标无源字段命中，可能需新增源字段 (+4)")

    # 维度 5：变更信号置信度低
    low_confidence = any(
        c.confidence_score < 0.6 or c.change_type == "MANUAL_REVIEW" for c in changes
    )
    if low_confidence:
        score += 3
        signals.append("变更信号置信度低，保守升级 (+3)")

    return score, signals


def _score_to_level(score: int) -> SeverityLevel:
    if score <= 1:
        return SeverityLevel.L1_TRIVIAL
    if score <= 5:
        return SeverityLevel.L2_LIGHT
    if score <= 10:
        return SeverityLevel.L3_STANDARD
    return SeverityLevel.L4_MAJOR


# ----------------- 对外入口 -----------------


def classify_change(
    changes: list[ReportingChangeDraft],
    impacts: list[ReportingImpactDraft],
    document_text: str,
    existing_report_codes: set[str] | None = None,
) -> ChangeClassification:
    """
    一次性给出母单类型 + 严重等级。
    existing_report_codes：当前 reporting_seed 已收录的报表 object_code 集合，用于识别报表新增。
    """
    existing_report_codes = existing_report_codes or set()

    change_ticket_type = _classify_change_ticket_type(changes, existing_report_codes)

    # 硬规则 L1（优先级最高，避免拿不准的微调被打分误升）
    forced_l1 = _hard_rules_force_l1(change_ticket_type, changes, impacts)
    if forced_l1:
        return ChangeClassification(
            change_ticket_type=change_ticket_type,
            severity=SeverityScore(
                level=SeverityLevel.L1_TRIVIAL,
                score=0,
                triggered_signals=[],
                forced_reason=forced_l1,
            ),
        )

    # 硬规则 L4
    forced_l4 = _hard_rules_force_l4(change_ticket_type, changes, document_text)
    if forced_l4:
        return ChangeClassification(
            change_ticket_type=change_ticket_type,
            severity=SeverityScore(
                level=SeverityLevel.L4_MAJOR,
                score=999,
                triggered_signals=[],
                forced_reason=forced_l4,
            ),
        )

    # 维度打分
    score, signals = _score_signals(changes, impacts)
    level = _score_to_level(score)
    return ChangeClassification(
        change_ticket_type=change_ticket_type,
        severity=SeverityScore(
            level=level,
            score=score,
            triggered_signals=signals,
            forced_reason=None,
        ),
    )
