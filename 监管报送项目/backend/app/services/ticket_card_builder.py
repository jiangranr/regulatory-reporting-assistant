from pydantic import BaseModel, Field

from app.models.enums import ActionTicketType, ResponsibleRole, ResponsibleSystem
from app.services.reporting_impact_analyzer import ReportingImpactDraft
from app.services.ticket_trigger_engine import TicketTrigger


class TicketTaskCard(BaseModel):
    action_type: ActionTicketType
    owner_role: ResponsibleRole
    executor_role: ResponsibleRole
    # 旧 trigger 路径传 ResponsibleSystem.xxx.value（字符串），新影响范围复核路径
    # 传具体 system_code（如 "RPT_1104"/"VALUATION"）；两个都是字符串，下游
    # 序列化/展示直接当字符串用即可。
    responsible_system: str
    summary: str
    affected_assets: dict
    must_do: list[str]
    must_confirm: list[str]
    output_artifacts: list[str]
    acceptance_criteria: list[str]
    blockers: list[str]
    evidence_refs: list[dict]
    historical_cases: list[dict] = Field(default_factory=list)


class _ActionCardSpec(BaseModel):
    owner_role: ResponsibleRole
    executor_role: ResponsibleRole
    summary: str
    must_do: list[str]
    must_confirm: list[str]
    output_artifacts: list[str]
    acceptance_criteria: list[str]


_ACTION_CARD_SPECS: dict[ActionTicketType, _ActionCardSpec] = {
    ActionTicketType.SCOPE_CONFIRM: _ActionCardSpec(
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        summary="确认受影响报送项的新旧监管口径和适用范围。",
        must_do=[
            "对照监管原文确认新旧口径差异。",
            "明确生效时点、追溯范围和特殊场景。",
            "输出需下游执行的业务口径结论。",
        ],
        must_confirm=["是否需要追溯历史数据。", "是否存在豁免或特殊处理场景。"],
        output_artifacts=["业务口径确认记录", "特殊场景清单"],
        acceptance_criteria=["业务方确认新旧口径差异。", "特殊场景和生效时点已记录。"],
    ),
    ActionTicketType.DATA_MAPPING: _ActionCardSpec(
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        summary="确认受影响报送项的数据映射和血缘口径。",
        must_do=[
            "核对报送字段到源字段的现有映射关系。",
            "补充新增维度、过滤字段或度量字段的映射候选。",
            "标记缺失或语义不一致的源字段。",
            "提交业务语义复核结论。",
            "沉淀字段映射调整记录。",
        ],
        must_confirm=["现有源字段语义是否覆盖新口径。", "是否需要新增码值维表或过滤条件。"],
        output_artifacts=["形成可复用的数据映射记录", "字段血缘复核清单"],
        acceptance_criteria=["报送字段到源字段映射全覆盖。", "业务语义复核结论已留痕。"],
    ),
    ActionTicketType.LINEAGE_BUILD: _ActionCardSpec(
        owner_role=ResponsibleRole.DATA_GOVERNANCE,
        executor_role=ResponsibleRole.DATA_GOVERNANCE,
        summary="建立受影响报送项的数据血缘链路。",
        must_do=[
            "识别报送字段、源字段和过滤条件。",
            "建立报送字段到源字段的血缘关系。",
            "与源系统团队确认采集方式。",
        ],
        must_confirm=["源系统是否已有该数据。", "是否需要新建中间表或码值维表。"],
        output_artifacts=["血缘建链记录", "源字段采集确认记录"],
        acceptance_criteria=["新建血缘已落库。", "数据治理和业务复核完成。"],
    ),
    ActionTicketType.CATALOG_INIT: _ActionCardSpec(
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        summary="初始化受影响报送对象和字段目录。",
        must_do=[
            "维护报送对象、报送项和报送字段元数据。",
            "配置版本、生效区间和停用状态。",
        ],
        must_confirm=["目录版本号和生效区间。", "是否影响历史目录归档。"],
        output_artifacts=["报送目录初始化记录"],
        acceptance_criteria=["报送元数据齐全且版本化。"],
    ),
    ActionTicketType.SOURCE_SYSTEM_CHANGE: _ActionCardSpec(
        owner_role=ResponsibleRole.SOURCE_SYSTEM,
        executor_role=ResponsibleRole.SOURCE_SYSTEM,
        summary="补齐源系统字段或采集接口能力。",
        must_do=[
            "确认缺失源字段和采集口径。",
            "评估源系统表结构、接口或码值扩展方案。",
            "与下游报送加工排期对齐。",
        ],
        must_confirm=["新增字段取数口径是否已确认。", "上游发布周期是否满足监管时限。"],
        output_artifacts=["源系统改造方案", "接口联调记录"],
        acceptance_criteria=["新增字段在测试或生产环境可查。", "上游接口联调通过。"],
    ),
    ActionTicketType.REPORT_PROCESSING: _ActionCardSpec(
        owner_role=ResponsibleRole.DATA_DEV,
        executor_role=ResponsibleRole.DATA_DEV,
        summary="调整受影响报送项的数据加工逻辑。",
        must_do=[
            "定位 SQL、ETL 或调度修改点。",
            "调整汇总、过滤和维表关联逻辑。",
            "准备回滚方案和差异核对脚本。",
        ],
        must_confirm=["是否影响其他下游报表。", "回滚预案是否完备。"],
        output_artifacts=["加工逻辑调整记录", "差异核对脚本"],
        acceptance_criteria=["加工逻辑通过代码评审。", "测试环境跑数差异已解释。"],
    ),
    ActionTicketType.VALIDATION_RULE: _ActionCardSpec(
        owner_role=ResponsibleRole.DATA_QUALITY,
        executor_role=ResponsibleRole.DATA_QUALITY,
        summary="调整受影响报送项的数据校验规则。",
        must_do=[
            "确认表内、表间或跨期校验规则变化。",
            "维护阈值、容差和例外条件。",
            "验证新规则误报和漏报情况。",
        ],
        must_confirm=["阈值变化是否需业务确认。", "是否影响历史期数据通过率。"],
        output_artifacts=["校验规则调整记录", "校验结果样例"],
        acceptance_criteria=["新规则在测试环境无误报。", "误差范围已被业务接受。"],
    ),
    ActionTicketType.HISTORICAL_DATA: _ActionCardSpec(
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.DATA_DEV,
        summary="评估并处理受影响历史报送数据。",
        must_do=[
            "明确历史追溯范围和补报口径。",
            "准备重算脚本和差异分析。",
            "形成监管解释材料。",
        ],
        must_confirm=["追溯至哪个时点。", "是否需要监管报备。"],
        output_artifacts=["历史数据重算记录", "监管解释材料"],
        acceptance_criteria=["重算结果通过业务复核。", "监管解释材料就绪。"],
    ),
    ActionTicketType.TASK_INIT: _ActionCardSpec(
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        summary="配置报送任务调度和权限。",
        must_do=[
            "配置报送任务调度。",
            "维护机构范围、报送频度和权限。",
        ],
        must_confirm=["涉及机构清单是否齐全。", "报送时点是否冲突。"],
        output_artifacts=["报送任务配置记录"],
        acceptance_criteria=["调度配置生效。", "机构权限全部下发。"],
    ),
    ActionTicketType.TEST_ACCEPTANCE: _ActionCardSpec(
        owner_role=ResponsibleRole.BUSINESS,
        executor_role=ResponsibleRole.QA,
        summary="完成受影响报送项的测试验收。",
        must_do=[
            "准备样例数据和回归用例。",
            "执行新旧口径差异核对。",
            "收集业务终签结论。",
        ],
        must_confirm=["验收样本是否覆盖关键场景。", "差异容忍度是多少。"],
        output_artifacts=["测试验收记录", "新旧口径差异分析"],
        acceptance_criteria=["回归用例全部通过。", "业务完成终签。"],
    ),
    ActionTicketType.ARCHIVE_REVIEW: _ActionCardSpec(
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.REPORTING_MGMT,
        summary="归档监管变更处理过程和复用经验。",
        must_do=[
            "记录最终口径、处理结论和决策依据。",
            "沉淀可复用经验标签。",
        ],
        must_confirm=["是否有需要沉淀的复用经验。"],
        output_artifacts=["复盘归档记录", "经验标签"],
        acceptance_criteria=["复盘文档归档。", "经验标签入库。"],
    ),
    ActionTicketType.MERGED_LIGHTWEIGHT: _ActionCardSpec(
        owner_role=ResponsibleRole.REPORTING_MGMT,
        executor_role=ResponsibleRole.DATA_DEV,
        summary="合并处理轻量级报送变更事项。",
        must_do=[
            "确认变更属于轻量处理范围。",
            "一次性完成口径、加工和验收留痕。",
        ],
        must_confirm=["是否确属轻量变更且无遗漏影响。"],
        output_artifacts=["轻量工单处理记录"],
        acceptance_criteria=["报送结果符合监管原文。", "业务方一次性确认。"],
    ),
}


def build_ticket_card(
    trigger: TicketTrigger,
    impacts: list[ReportingImpactDraft],
    historical_cases: list[dict],
) -> TicketTaskCard:
    selected_impacts = _select_impacts(trigger, impacts)
    spec = _ACTION_CARD_SPECS[trigger.action_type]

    return TicketTaskCard(
        action_type=trigger.action_type,
        owner_role=spec.owner_role,
        executor_role=spec.executor_role,
        responsible_system=trigger.responsible_system.value,
        summary=spec.summary,
        affected_assets=_build_affected_assets(selected_impacts),
        must_do=spec.must_do[:5],
        must_confirm=spec.must_confirm,
        output_artifacts=spec.output_artifacts,
        acceptance_criteria=spec.acceptance_criteria,
        blockers=_build_blockers(selected_impacts),
        evidence_refs=_build_evidence_refs(trigger, selected_impacts),
        historical_cases=historical_cases[:3],
    )


def _select_impacts(
    trigger: TicketTrigger,
    impacts: list[ReportingImpactDraft],
) -> list[ReportingImpactDraft]:
    related_codes = {
        code.strip()
        for code in trigger.related_impact_codes
        if code and code.strip()
    }
    if not related_codes:
        return impacts
    return [
        impact
        for impact in impacts
        if impact.reporting_item_code.strip() in related_codes
    ]


def _build_affected_assets(impacts: list[ReportingImpactDraft]) -> dict[str, list[str]]:
    return {
        "reporting_items": _dedupe_asset_dicts(
            {
                "code": impact.reporting_item_code,
                "name": impact.reporting_item_name or impact.reporting_item_code,
            }
            for impact in impacts
        ),
        "reporting_fields": _dedupe_asset_dicts(
            {
                "code": impact.impacted_reporting_field,
                "name": impact.impacted_reporting_field_name or impact.impacted_reporting_field,
            }
            for impact in impacts
        ),
        "source_fields": _dedupe_asset_dicts(
            _source_field_asset(impact, field)
            for impact in impacts
            for field in impact.impacted_source_fields
        ),
        "lineage_roles": _dedupe(
            role
            for impact in impacts
            for role in impact.impacted_lineage_roles
        ),
    }


def _build_blockers(impacts: list[ReportingImpactDraft]) -> list[str]:
    blockers: list[str] = []
    for impact in impacts:
        code = impact.reporting_item_code.strip()
        if code and not impact.impacted_source_fields:
            blockers.append(f"{code} 缺少受影响源字段，需先补充源字段候选或确认无需源字段改造。")
    return _dedupe(blockers)


def _build_evidence_refs(
    trigger: TicketTrigger,
    impacts: list[ReportingImpactDraft],
) -> list[dict]:
    refs: list[dict] = [
        {
            "type": "trigger_reason",
            "src": "工单触发规则",
            "text": _trigger_reason_text(reason),
        }
        for reason in _dedupe(trigger.trigger_reasons)
    ]
    refs.extend(
        {
            "type": "impact",
            "src": f"影响分析 · {impact.reporting_item_code}",
            "text": impact.impact_reason,
            "reporting_item_code": impact.reporting_item_code,
            "impact_type": impact.impact_type,
            "reason": impact.impact_reason,
        }
        for impact in impacts
    )
    return refs


_TRIGGER_REASON_TEXT: dict[str, str] = {
    "REPORTING_ITEM_SCOPE_CHANGE": "报送项口径或适用范围发生变化。",
    "REPORT_OR_SOURCE_FIELD_IMPACT": "报送字段或源字段映射受到影响。",
    "SOURCE_FIELD_GAP": "存在源字段缺口，需要补充字段候选或确认无需改造。",
    "PROCESSING_LOGIC_SIGNAL": "监管原文命中加工逻辑调整信号。",
    "VALIDATION_RULE_SIGNAL": "监管原文命中校验规则调整信号。",
    "HISTORICAL_DATA_SIGNAL": "监管原文命中历史数据追溯或重算信号。",
    "TEST_ACCEPTANCE_REQUIRED": "变更需要测试验收和业务确认。",
    "ARCHIVE_REQUIRED": "变更处理过程需要归档复盘。",
    "L1_LIGHTWEIGHT_MERGED_TICKET": "L1 轻量变更合并为单张工单处理。",
}


def _trigger_reason_text(reason: str) -> str:
    return _TRIGGER_REASON_TEXT.get(reason, reason)


def _source_field_asset(impact: ReportingImpactDraft, field_code: str) -> dict[str, str]:
    for detail in impact.impacted_source_field_details:
        if detail.get("code") == field_code:
            return {
                "code": field_code,
                "name": detail.get("name") or field_code,
                "role": detail.get("role") or "",
            }
    role = ""
    if len(impact.impacted_source_fields) == len(impact.impacted_lineage_roles):
        index = impact.impacted_source_fields.index(field_code)
        role = impact.impacted_lineage_roles[index]
    return {"code": field_code, "name": field_code, "role": role}


def _dedupe_asset_dicts(values) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        code = str(value.get("code") or "").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append({
            key: str(raw).strip()
            for key, raw in value.items()
            if raw is not None and str(raw).strip()
        })
    return deduped


def _dedupe(values) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped
