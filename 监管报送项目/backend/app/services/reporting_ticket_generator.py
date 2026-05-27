"""
监管报送工单生成：母单（按监管变更场景）+ 子单（按责任团队×处理动作）。

调用顺序：
    classification = classify_change(...)
    plan = build_ticket_plan(classification, impacts, task_title)
    plan.parent + plan.children 落库
"""

from dataclasses import dataclass, field

from app.models.enums import (
    ActionTicketType,
    ChangeTicketType,
    ResponsibleRole,
    SeverityLevel,
)
from app.services.change_severity_classifier import (
    ChangeClassification,
    SeverityScore,
)
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_card_builder import (
    TicketTaskCard,
    build_ticket_card,
)
from app.services.ticket_quality_checker import (
    TicketQualityResult,
    check_ticket_card_quality,
)
from app.services.ticket_trigger_engine import (
    TicketTrigger,
    build_ticket_triggers,
)


# ----------------- 子单规格 -----------------


@dataclass(frozen=True)
class ActionTicketSpec:
    action_type: ActionTicketType
    name_zh: str
    owner_role: ResponsibleRole          # A：最终负责
    executor_role: ResponsibleRole       # R：干活
    depends_on_lineage: bool             # 是否依赖存量血缘
    business_signoff_required: bool      # 是否需要业务签字


_ACTION_SPECS: dict[ActionTicketType, ActionTicketSpec] = {
    ActionTicketType.SCOPE_CONFIRM: ActionTicketSpec(
        ActionTicketType.SCOPE_CONFIRM, "口径确认子单",
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        depends_on_lineage=False,
        business_signoff_required=True,
    ),
    ActionTicketType.DATA_MAPPING: ActionTicketSpec(
        ActionTicketType.DATA_MAPPING, "数据映射子单",
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        depends_on_lineage=True,
        business_signoff_required=True,
    ),
    ActionTicketType.LINEAGE_BUILD: ActionTicketSpec(
        ActionTicketType.LINEAGE_BUILD, "血缘建链子单",
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        depends_on_lineage=False,
        business_signoff_required=True,
    ),
    ActionTicketType.CATALOG_INIT: ActionTicketSpec(
        ActionTicketType.CATALOG_INIT, "报送目录初始化子单",
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        depends_on_lineage=False,
        business_signoff_required=True,
    ),
    ActionTicketType.SOURCE_SYSTEM_CHANGE: ActionTicketSpec(
        ActionTicketType.SOURCE_SYSTEM_CHANGE, "源系统改造子单",
        owner_role=ResponsibleRole.SOURCE_SYSTEM,
        executor_role=ResponsibleRole.SOURCE_SYSTEM,
        depends_on_lineage=False,
        business_signoff_required=False,
    ),
    ActionTicketType.REPORT_PROCESSING: ActionTicketSpec(
        ActionTicketType.REPORT_PROCESSING, "报送加工子单",
        owner_role=ResponsibleRole.DATA_DEV,
        executor_role=ResponsibleRole.DATA_DEV,
        depends_on_lineage=True,
        business_signoff_required=False,
    ),
    ActionTicketType.VALIDATION_RULE: ActionTicketSpec(
        ActionTicketType.VALIDATION_RULE, "校验规则子单",
        owner_role=ResponsibleRole.DATA_QUALITY,
        executor_role=ResponsibleRole.DATA_QUALITY,
        depends_on_lineage=False,
        business_signoff_required=False,
    ),
    ActionTicketType.HISTORICAL_DATA: ActionTicketSpec(
        ActionTicketType.HISTORICAL_DATA, "历史数据处理子单",
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.DATA_DEV,
        depends_on_lineage=True,
        business_signoff_required=True,
    ),
    ActionTicketType.TASK_INIT: ActionTicketSpec(
        ActionTicketType.TASK_INIT, "报送任务初始化子单",
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        depends_on_lineage=False,
        business_signoff_required=False,
    ),
    ActionTicketType.TEST_ACCEPTANCE: ActionTicketSpec(
        ActionTicketType.TEST_ACCEPTANCE, "测试验收子单",
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.QA,
        depends_on_lineage=False,
        business_signoff_required=True,
    ),
    ActionTicketType.ARCHIVE_REVIEW: ActionTicketSpec(
        ActionTicketType.ARCHIVE_REVIEW, "归档复盘子单",
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        depends_on_lineage=False,
        business_signoff_required=False,
    ),
    ActionTicketType.MERGED_LIGHTWEIGHT: ActionTicketSpec(
        ActionTicketType.MERGED_LIGHTWEIGHT, "合并轻量工单",
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.DATA_DEV,
        depends_on_lineage=False,
        business_signoff_required=True,
    ),
}


# ----------------- 母单→子单展开矩阵 -----------------

_DEFAULT_REVISION_L4 = [
    ActionTicketType.SCOPE_CONFIRM,
    ActionTicketType.DATA_MAPPING,
    ActionTicketType.SOURCE_SYSTEM_CHANGE,
    ActionTicketType.REPORT_PROCESSING,
    ActionTicketType.VALIDATION_RULE,
    ActionTicketType.HISTORICAL_DATA,
    ActionTicketType.TEST_ACCEPTANCE,
    ActionTicketType.ARCHIVE_REVIEW,
]


_EXPANSION_MATRIX: dict[ChangeTicketType, dict[SeverityLevel, list[ActionTicketType]]] = {
    ChangeTicketType.REPORT_ONBOARDING: {
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.CATALOG_INIT,
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.LINEAGE_BUILD,
            ActionTicketType.SOURCE_SYSTEM_CHANGE,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TASK_INIT,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: [
            ActionTicketType.CATALOG_INIT,
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.LINEAGE_BUILD,
            ActionTicketType.SOURCE_SYSTEM_CHANGE,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.HISTORICAL_DATA,
            ActionTicketType.TASK_INIT,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
    },
    ChangeTicketType.REPORT_REVISION: {
        SeverityLevel.L2_LIGHT: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
        ],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.DATA_MAPPING,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: _DEFAULT_REVISION_L4,
    },
    ChangeTicketType.SCOPE_ADJUSTMENT: {
        SeverityLevel.L2_LIGHT: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.DATA_MAPPING,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: _DEFAULT_REVISION_L4,
    },
    ChangeTicketType.INDICATOR_ADD: {
        SeverityLevel.L2_LIGHT: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.DATA_MAPPING,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
        ],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.DATA_MAPPING,
            ActionTicketType.SOURCE_SYSTEM_CHANGE,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: _DEFAULT_REVISION_L4,
    },
    ChangeTicketType.VALIDATION_CHANGE: {
        SeverityLevel.L2_LIGHT: [
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TEST_ACCEPTANCE,
        ],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.HISTORICAL_DATA,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
    },
    ChangeTicketType.INSTITUTION_FREQ_CHANGE: {
        SeverityLevel.L2_LIGHT: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.TASK_INIT,
            ActionTicketType.TEST_ACCEPTANCE,
        ],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.TASK_INIT,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.TASK_INIT,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.VALIDATION_RULE,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
    },
    ChangeTicketType.REPORT_DECOMMISSION: {
        SeverityLevel.L4_MAJOR: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.HISTORICAL_DATA,
            ActionTicketType.TASK_INIT,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
    },
    ChangeTicketType.MANUAL_REVIEW: {
        SeverityLevel.L2_LIGHT: [ActionTicketType.SCOPE_CONFIRM],
        SeverityLevel.L3_STANDARD: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
        SeverityLevel.L4_MAJOR: [
            ActionTicketType.SCOPE_CONFIRM,
            ActionTicketType.DATA_MAPPING,
            ActionTicketType.REPORT_PROCESSING,
            ActionTicketType.TEST_ACCEPTANCE,
            ActionTicketType.ARCHIVE_REVIEW,
        ],
    },
}


# ----------------- 输出结构 -----------------


@dataclass
class ChildTicketPlan:
    action_type: ActionTicketType
    title: str
    spec: ActionTicketSpec
    content_markdown: str
    related_impact_codes: list[str] = field(default_factory=list)
    # Task 4 升级：触发器路径会同时挂结构化任务卡 + 质量评分。
    # 旧矩阵分支（L1 兜底、新流程没命中时）仍走 Markdown，card/quality 保持 None，
    # 以兼容前端按结构化字段优先、否则回退 Markdown 的渲染策略。
    card: TicketTaskCard | None = None
    quality: TicketQualityResult | None = None


@dataclass
class ParentTicketPlan:
    change_ticket_type: ChangeTicketType
    severity: SeverityScore
    title: str
    content_markdown: str
    overall_owner_role: ResponsibleRole = ResponsibleRole.REPORTING_MGMT
    closure_review_required: bool = True


@dataclass
class TicketPlan:
    parent: ParentTicketPlan
    children: list[ChildTicketPlan]


# ----------------- 母单/子单展开主入口 -----------------


def build_ticket_plan(
    classification: ChangeClassification,
    impacts: list[ReportingImpactDraft],
    task_title: str,
    rule_cards_by_key: dict[str, list[dict]] | None = None,
    historical_cases_by_key: dict[str, list[dict]] | None = None,
    document_text: str = "",
) -> TicketPlan:
    """生成母子单计划。

    Task 4 升级：非 L1 分支优先用触发器引擎决定子单集合，旧的"母单类型 + 等级"
    固定矩阵 (_EXPANSION_MATRIX) 作为触发器空返回时的兜底，保持向后兼容。

    参数：
      rule_cards_by_key: "报送项/报表对象 → 规则卡片" 映射，挂到工单 Markdown 底部。
      historical_cases_by_key: "reporting_item_code → 历史相似决策" 映射（W2 后真实化）。
      document_text: 原文摘录，用于触发器识别"加工/校验/跨表/追溯"等文本信号。
    """
    rule_cards_by_key = rule_cards_by_key or {}
    historical_cases_by_key = historical_cases_by_key or {}
    parent_title = (
        f"{task_title}｜{_change_type_label(classification.change_ticket_type)}"
        f"（{classification.severity.level.value}）"
    )
    parent = ParentTicketPlan(
        change_ticket_type=classification.change_ticket_type,
        severity=classification.severity,
        title=parent_title,
        content_markdown=_render_parent_markdown(classification, impacts, task_title),
    )

    if classification.severity.level == SeverityLevel.L1_TRIVIAL:
        children = [
            _build_merged_lightweight_child(task_title, impacts, rule_cards_by_key)
        ]
    else:
        triggers = build_ticket_triggers(impacts, document_text=document_text)
        if triggers:
            children = [
                _build_child_plan_from_trigger(
                    trigger,
                    task_title,
                    impacts,
                    rule_cards_by_key,
                    historical_cases_by_key,
                )
                for trigger in triggers
            ]
        else:
            # 兜底：触发器全部未命中（例如纯文档级变更、没有任何影响项），
            # 退回固定矩阵保证旧契约。这条分支也保留 Markdown 内容，前端可正常渲染。
            action_types = _select_action_types(
                classification.change_ticket_type, classification.severity.level
            )
            children = [
                _build_child_plan(action_type, task_title, impacts, rule_cards_by_key)
                for action_type in action_types
            ]

    return TicketPlan(parent=parent, children=children)


def _select_action_types(
    change_type: ChangeTicketType, level: SeverityLevel
) -> list[ActionTicketType]:
    matrix = _EXPANSION_MATRIX.get(change_type, {})
    if level in matrix:
        return matrix[level]
    fallback_order = [
        SeverityLevel.L4_MAJOR,
        SeverityLevel.L3_STANDARD,
        SeverityLevel.L2_LIGHT,
    ]
    for fb in fallback_order:
        if fb in matrix:
            return matrix[fb]
    return [ActionTicketType.SCOPE_CONFIRM]


# ----------------- 子单内容渲染 -----------------


def _build_child_plan(
    action_type: ActionTicketType,
    task_title: str,
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]] | None = None,
) -> ChildTicketPlan:
    """旧路径：固定矩阵展开，保留作为触发器空返回时的兜底。"""
    spec = _ACTION_SPECS[action_type]
    return ChildTicketPlan(
        action_type=action_type,
        title=f"{task_title}｜{spec.name_zh}",
        spec=spec,
        content_markdown=_render_child_markdown(spec, impacts, rule_cards_by_key or {}),
        related_impact_codes=[i.reporting_item_code for i in impacts if i.reporting_item_code],
    )


def _build_child_plan_from_trigger(
    trigger: TicketTrigger,
    task_title: str,
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]] | None = None,
    historical_cases_by_key: dict[str, list[dict]] | None = None,
) -> ChildTicketPlan:
    """新路径：触发器 → 结构化任务卡 + 质量评分 + 短模板 Markdown。

    historical_cases_by_key 在 W2 之前是 stub（全部空），结构上预留。
    """
    spec = _ACTION_SPECS[trigger.action_type]
    related_impacts = [
        impact
        for impact in impacts
        if not trigger.related_impact_codes
        or impact.reporting_item_code in trigger.related_impact_codes
    ]
    historical_cases = _historical_cases_for_impacts(
        related_impacts, historical_cases_by_key or {}
    )
    card = build_ticket_card(trigger, related_impacts, historical_cases=historical_cases)
    quality = check_ticket_card_quality(card)
    return ChildTicketPlan(
        action_type=trigger.action_type,
        title=f"{task_title}｜{spec.name_zh}",
        spec=spec,
        content_markdown=_render_card_markdown(card, rule_cards_by_key or {}),
        related_impact_codes=list(trigger.related_impact_codes),
        card=card,
        quality=quality,
    )


def _historical_cases_for_impacts(
    impacts: list[ReportingImpactDraft],
    historical_cases_by_key: dict[str, list[dict]],
) -> list[dict]:
    """聚合本工单所有 impact 的历史相似决策案例，去重并裁顶 3 条。"""
    seen: set[str] = set()
    cases: list[dict] = []
    for impact in impacts:
        for case in historical_cases_by_key.get(impact.reporting_item_code, []):
            key = str(case.get("ticket_id") or case.get("id") or id(case))
            if key in seen:
                continue
            seen.add(key)
            cases.append(case)
            if len(cases) >= 3:
                return cases
    return cases


def _render_card_markdown(
    card: TicketTaskCard,
    rule_cards_by_key: dict[str, list[dict]],
) -> str:
    """把结构化任务卡渲染成短 Markdown，作为前端结构化字段的兜底回退视图。

    设计原则（对照 P0 验收标准）：
      - 默认只展示 5 个核心区块：摘要 / 责任 / 资产 / 必须动作 / 验收
      - 待确认、阻塞、产出资产、规则卡片只在非空时输出
      - 规则卡片正文不再塞进每个子单 Markdown，只展示数量与入口指示
    """
    lines: list[str] = [
        "## 工单摘要",
        "",
        card.summary,
        "",
        "## 责任分配",
        "",
        f"- 责任系统：{card.responsible_system.value}",
        f"- 出口责任 (A)：{card.owner_role.value}",
        f"- 执行人 (R)：{card.executor_role.value}",
        "",
        "## 受影响资产",
        "",
    ]
    asset_lines = [
        f"- {key}：{', '.join(values[:5])}"
        for key, values in card.affected_assets.items()
        if values
    ]
    if asset_lines:
        lines.extend(asset_lines)
    else:
        lines.append("- （未识别到具体资产，详见原文证据）")

    if card.must_do:
        lines.extend(["", "## 必须动作", ""])
        lines.extend(f"- {item}" for item in card.must_do)

    if card.must_confirm:
        lines.extend(["", "## 待确认问题", ""])
        lines.extend(f"- {item}" for item in card.must_confirm)

    if card.acceptance_criteria:
        lines.extend(["", "## 验收标准", ""])
        lines.extend(f"- {item}" for item in card.acceptance_criteria)

    if card.blockers:
        lines.extend(["", "## 阻塞点", ""])
        lines.extend(f"- {item}" for item in card.blockers)

    if card.output_artifacts:
        lines.extend(["", "## 治理资产产出", ""])
        lines.extend(f"- {item}" for item in card.output_artifacts)

    # 规则卡片：只挂"入口提示"，详情留给前端折叠抽屉
    related_card_codes = _collect_related_rule_card_codes(card, rule_cards_by_key)
    if related_card_codes:
        lines.extend(["", "## 参考规则卡片", ""])
        lines.append(
            f"- 共 {len(related_card_codes)} 张可参考卡片："
            f"{', '.join(related_card_codes[:5])}"
            + ("…" if len(related_card_codes) > 5 else "")
        )

    return "\n".join(lines) + "\n"


def _collect_related_rule_card_codes(
    card: TicketTaskCard,
    rule_cards_by_key: dict[str, list[dict]],
) -> list[str]:
    """从 affected_assets 反查关联的规则卡片代码（去重，保序）。"""
    if not rule_cards_by_key:
        return []
    keys: list[str] = []
    for values in card.affected_assets.values():
        for value in values:
            if not value:
                continue
            keys.append(value)
            if "." in value:
                keys.append(value.split(".")[0])
    seen: set[str] = set()
    codes: list[str] = []
    for key in keys:
        for rule_card in rule_cards_by_key.get(key, []):
            code = rule_card.get("card_code")
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
    return codes


def _build_merged_lightweight_child(
    task_title: str,
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]] | None = None,
) -> ChildTicketPlan:
    spec = _ACTION_SPECS[ActionTicketType.MERGED_LIGHTWEIGHT]
    cards_block = _rule_cards_block(impacts, rule_cards_by_key or {})
    content = (
        "## 工单说明\n\n"
        "本次变更经评估为 L1 微调，无需拆分子单，由报送管理岗牵头一次性处理。\n\n"
        f"## 影响范围\n\n{_impact_lines(impacts) or '- 暂未识别到具体影响项'}\n\n"
        "## 处理动作\n\n"
        "- 由报送管理岗确认口径并直接通知数据开发完成 SQL/ETL 调整\n"
        "- 完成后业务方一次性验收并归档\n\n"
        "## 验收标准\n\n"
        "- 报送结果与监管原文一致\n"
        "- 业务方书面确认\n"
    )
    return ChildTicketPlan(
        action_type=ActionTicketType.MERGED_LIGHTWEIGHT,
        title=f"{task_title}｜L1 合并轻量工单",
        spec=spec,
        content_markdown=content + cards_block,
        related_impact_codes=[i.reporting_item_code for i in impacts if i.reporting_item_code],
    )


def _render_child_markdown(
    spec: ActionTicketSpec,
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]] | None = None,
) -> str:
    lineage_block = ""
    if spec.depends_on_lineage:
        lineage_block = (
            "\n## 关联血缘\n\n"
            + (_lineage_lines(impacts) or "- 未召回血缘，需人工补充")
            + "\n"
        )

    cards_block = _rule_cards_block(impacts, rule_cards_by_key or {})

    return (
        f"## 责任分配\n\n"
        f"- 出口责任 (A)：{spec.owner_role.value}\n"
        f"- 执行人 (R)：{spec.executor_role.value}\n"
        f"- 是否依赖存量血缘：{'是' if spec.depends_on_lineage else '否'}\n"
        f"- 业务签字要求：{'必须' if spec.business_signoff_required else '不需要'}\n\n"
        f"## 处理动作\n\n{_action_hints(spec.action_type)}\n"
        f"{lineage_block}"
        f"\n## 影响范围\n\n{_impact_lines(impacts) or '- 由分析阶段补充'}\n\n"
        f"## 待确认问题\n\n{_open_questions(spec.action_type)}\n\n"
        f"## 验收标准\n\n{_acceptance(spec.action_type)}\n"
        f"{cards_block}"
    )


def _rule_cards_block(
    impacts: list[ReportingImpactDraft],
    rule_cards_by_key: dict[str, list[dict]],
) -> str:
    """根据子单的影响项查 lookup,把命中的规则卡片以 Markdown 形式追加。"""
    if not rule_cards_by_key:
        return ""

    keys: list[str] = []
    for impact in impacts:
        code = impact.reporting_item_code
        if not code:
            continue
        keys.append(code)
        if "." in code:
            keys.append(code.split(".")[0])  # 对象级 key
    # 去重保序
    seen_keys: set[str] = set()
    ordered_keys = [k for k in keys if not (k in seen_keys or seen_keys.add(k))]

    # 收集卡片(去重 by card_code)
    seen_codes: set[str] = set()
    collected: list[dict] = []
    for key in ordered_keys:
        for card in rule_cards_by_key.get(key, []):
            code = card.get("card_code")
            if not code or code in seen_codes:
                continue
            seen_codes.add(code)
            collected.append(card)

    if not collected:
        return ""

    lines = ["\n## 参考填报规则卡片\n"]
    for card in collected:
        level = card.get("card_level", "L1")
        title = card.get("card_title", "")
        text = card.get("card_text", "")
        source = card.get("source_location", "")
        verified = card.get("evidence_verified", False)
        verified_badge = "✓ 原文已锚定" if verified else "⚠ 未核对原文"
        concept_codes = card.get("related_concept_codes", []) or []
        concept_line = (
            f"  - 关联概念：{', '.join(concept_codes)}\n" if concept_codes else ""
        )
        lines.append(
            f"### {card.get('card_code', '')} · {title} [{level}]\n"
            f"> {text}\n\n"
            f"  - 来源：{source}\n"
            f"{concept_line}"
            f"  - 证据状态：{verified_badge}\n"
        )
    return "\n".join(lines) + "\n"


def _render_parent_markdown(
    classification: ChangeClassification,
    impacts: list[ReportingImpactDraft],
    task_title: str,
) -> str:
    sev = classification.severity
    forced = f"\n- 强制规则：{sev.forced_reason}" if sev.forced_reason else ""
    signals = (
        "\n  - " + "\n  - ".join(sev.triggered_signals)
        if sev.triggered_signals
        else "（无）"
    )
    return (
        f"# {task_title}｜母单\n\n"
        f"## 母单类型\n\n- {_change_type_label(classification.change_ticket_type)}\n\n"
        f"## 严重等级\n\n"
        f"- 等级：{sev.level.value}\n"
        f"- 总分：{sev.score}\n"
        f"- 打分依据：{signals}{forced}\n\n"
        f"## 兜底负责人\n\n"
        f"- 母单 Owner：报送管理岗（对监管负总责）\n"
        f"- 关闭前需做合规复核\n\n"
        f"## 影响范围\n\n{_impact_lines(impacts) or '- 暂未识别到具体影响项'}\n"
    )


# ----------------- 渲染辅助 -----------------


def _change_type_label(t: ChangeTicketType) -> str:
    return {
        ChangeTicketType.REPORT_ONBOARDING: "报表新增母单",
        ChangeTicketType.REPORT_REVISION: "报表修订母单",
        ChangeTicketType.SCOPE_ADJUSTMENT: "口径/范围调整母单",
        ChangeTicketType.INDICATOR_ADD: "指标新增母单",
        ChangeTicketType.VALIDATION_CHANGE: "校验规则变更母单",
        ChangeTicketType.INSTITUTION_FREQ_CHANGE: "机构范围/频度调整母单",
        ChangeTicketType.REPORT_DECOMMISSION: "报表停报母单",
        ChangeTicketType.MANUAL_REVIEW: "待人工复核母单",
    }[t]


def _impact_lines(impacts: list[ReportingImpactDraft]) -> str:
    if not impacts:
        return ""
    return "\n".join(
        f"- {impact.reporting_item_code}：{impact.impact_reason}"
        for impact in impacts
        if impact.reporting_item_code
    )


def _lineage_lines(impacts: list[ReportingImpactDraft]) -> str:
    rows = []
    for impact in impacts:
        if not impact.impacted_reporting_field and not impact.impacted_source_fields:
            continue
        sources = ", ".join(impact.impacted_source_fields) or "—"
        rows.append(
            f"- {impact.reporting_item_code}：报送字段 {impact.impacted_reporting_field or '—'} ← 源字段 {sources}"
        )
    return "\n".join(rows)


def _action_hints(action_type: ActionTicketType) -> str:
    return {
        ActionTicketType.SCOPE_CONFIRM: (
            "- 对照监管原文确认新旧口径差异\n"
            "- 明确是否需要追溯、特殊场景列表、生效时点"
        ),
        ActionTicketType.DATA_MAPPING: (
            "- 基于存量血缘核对报送字段→源字段映射\n"
            "- 补充新增维度或过滤字段的映射候选\n"
            "- 由业务方做语义复核（不签 SQL）"
        ),
        ActionTicketType.LINEAGE_BUILD: (
            "- 报表首次落地，从零建立报送字段↔源字段映射\n"
            "- 与源系统团队对齐采集方式、码值维表"
        ),
        ActionTicketType.CATALOG_INIT: (
            "- 新建报送对象、报送项、报送字段元数据\n"
            "- 维护版本与生效区间"
        ),
        ActionTicketType.SOURCE_SYSTEM_CHANGE: (
            "- 补齐缺失源字段、扩展码值、调整采集接口\n"
            "- 与上游系统对齐发布节奏"
        ),
        ActionTicketType.REPORT_PROCESSING: (
            "- 给出 SQL/ETL 修改点（候选 diff），不直接发布\n"
            "- 调整调度依赖、汇总逻辑\n"
            "- 准备回滚方案"
        ),
        ActionTicketType.VALIDATION_RULE: (
            "- 新增/修改表内、表间、跨期校验规则\n"
            "- 标记阈值变化"
        ),
        ActionTicketType.HISTORICAL_DATA: (
            "- 明确追溯范围、补报口径\n"
            "- 准备差异分析 SQL 和监管解释材料\n"
            "- 业务与数据开发联签"
        ),
        ActionTicketType.TASK_INIT: (
            "- 配置报送任务调度、权限、机构范围、报送频度"
        ),
        ActionTicketType.TEST_ACCEPTANCE: (
            "- 准备样例数据、回归用例\n"
            "- 出具新旧口径差异分析\n"
            "- 业务终签后方可发布"
        ),
        ActionTicketType.ARCHIVE_REVIEW: (
            "- 记录最终口径、决策依据、监管反馈\n"
            "- 沉淀可复用经验标签"
        ),
        ActionTicketType.MERGED_LIGHTWEIGHT: "- 一次性处理，详见正文",
    }[action_type]


def _open_questions(action_type: ActionTicketType) -> str:
    return {
        ActionTicketType.SCOPE_CONFIRM: (
            "- 是否需要追溯存量数据？\n"
            "- 是否存在特殊场景/豁免？\n"
            "- 生效时点是否分阶段？"
        ),
        ActionTicketType.DATA_MAPPING: (
            "- 现有源字段语义是否覆盖新口径？\n"
            "- 是否需要新增码值维表？"
        ),
        ActionTicketType.LINEAGE_BUILD: (
            "- 源系统是否已有该数据？\n"
            "- 是否需要新建中间表？"
        ),
        ActionTicketType.CATALOG_INIT: (
            "- 报送对象版本号怎么管理？\n"
            "- 是否影响历史版本归档？"
        ),
        ActionTicketType.SOURCE_SYSTEM_CHANGE: (
            "- 新增字段的取数口径是否已与业务确认？\n"
            "- 上游发布周期是否能匹配监管时限？"
        ),
        ActionTicketType.REPORT_PROCESSING: (
            "- 是否影响其他下游报表？\n"
            "- 回滚预案是否完备？"
        ),
        ActionTicketType.VALIDATION_RULE: (
            "- 阈值变化是否需业务确认？\n"
            "- 是否影响历史期数据通过率？"
        ),
        ActionTicketType.HISTORICAL_DATA: (
            "- 追溯至哪个时点？\n"
            "- 是否需要监管报备？"
        ),
        ActionTicketType.TASK_INIT: (
            "- 涉及机构清单是否齐全？\n"
            "- 报送时点是否冲突？"
        ),
        ActionTicketType.TEST_ACCEPTANCE: (
            "- 验收样本是否覆盖关键场景？\n"
            "- 差异容忍度是多少？"
        ),
        ActionTicketType.ARCHIVE_REVIEW: "- 是否有需要沉淀的复用经验？",
        ActionTicketType.MERGED_LIGHTWEIGHT: "- 是否真的属于 L1，无遗漏影响？",
    }[action_type]


def _acceptance(action_type: ActionTicketType) -> str:
    return {
        ActionTicketType.SCOPE_CONFIRM: "- 业务方书面确认新旧口径\n- 特殊场景清单完整",
        ActionTicketType.DATA_MAPPING: "- 报送字段↔源字段映射全覆盖\n- 业务语义复核签字",
        ActionTicketType.LINEAGE_BUILD: "- 新建血缘 100% 落库\n- 经数据治理和业务双签",
        ActionTicketType.CATALOG_INIT: "- 报送对象/项/字段元数据齐全且版本化",
        ActionTicketType.SOURCE_SYSTEM_CHANGE: "- 新增字段在生产可查\n- 上游接口联调通过",
        ActionTicketType.REPORT_PROCESSING: "- SQL/ETL 通过 code review\n- 测试环境跑数无差异",
        ActionTicketType.VALIDATION_RULE: "- 新规则在测试环境无误报\n- 误差范围业务接受",
        ActionTicketType.HISTORICAL_DATA: "- 重算结果通过业务复核\n- 监管解释材料就绪",
        ActionTicketType.TASK_INIT: "- 调度配置生效\n- 机构权限全部下发",
        ActionTicketType.TEST_ACCEPTANCE: "- 回归用例全部通过\n- 业务终签",
        ActionTicketType.ARCHIVE_REVIEW: "- 复盘文档归档\n- 经验标签入库",
        ActionTicketType.MERGED_LIGHTWEIGHT: "- 报送结果符合监管原文\n- 业务方一次性确认",
    }[action_type]


# ----------------- 向后兼容入口 -----------------


def generate_reporting_ticket_markdown(
    title: str, impacts: list[ReportingImpactDraft]
) -> str:
    """旧调用入口，保留兼容。建议改用 build_ticket_plan。"""
    impact_lines = "\n".join(
        f"- {impact.reporting_item_code}：{impact.impact_reason}\n"
        f"  - 报送字段：{impact.impacted_reporting_field}\n"
        f"  - 源字段：{', '.join(impact.impacted_source_fields)}\n"
        f"  - 建议动作：{impact.recommended_action}"
        for impact in impacts
    )
    return (
        f"# {title}工单草稿（兼容旧版）\n\n"
        f"> 建议改用母子单结构，调用 build_ticket_plan。\n\n"
        f"## 影响范围\n\n{impact_lines}\n"
    )
