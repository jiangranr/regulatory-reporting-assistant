from app.models.schemas import ImpactItem, RuleItem


def generate_ticket_markdown(title: str, rules: list[RuleItem], impacts: list[ImpactItem]) -> str:
    rule_lines = "\n".join(
        f"- {rule.rule_type}：{rule.regulatory_object} - {rule.requirement}" for rule in rules
    )
    impact_lines = "\n".join(
        "- "
        f"{impact.business_object} / {impact.impacted_system} / {impact.impacted_field}："
        f"{impact.recommended_action}"
        for impact in impacts
    )
    return f"""# {title}工单草稿

## 监管规则摘要

{rule_lines}

## 影响范围

{impact_lines}

## 建议动作

- 业务确认监管口径和适用主体。
- 开发确认字段、接口、清算路径和校验实现范围。
- 数据治理确认码值、字段映射、血缘和责任团队。
- 复核通过后进入正式工单系统。
"""
