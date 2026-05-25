from app.models.schemas import RuleItem


def extract_rules(text: str) -> list[RuleItem]:
    normalized = text.lower()
    is_repo = "回购" in text or "repo" in normalized
    is_offshore = "境外机构" in text or "offshore" in normalized

    if is_repo or is_offshore:
        return [
            RuleItem(
                rule_type="业务范围扩展",
                regulatory_object="境外机构投资者",
                requirement="支持符合条件的境外机构投资者开展债券回购业务。",
                source_excerpt=text[:160],
                confidence=0.86,
            ),
            RuleItem(
                rule_type="资金账户约束",
                regulatory_object="资金账户与投资渠道",
                requirement="回购资金收付应符合现券交易对应投资渠道和账户管理规定。",
                source_excerpt=text[:160],
                confidence=0.82,
            ),
        ]

    return [
        RuleItem(
            rule_type="待人工确认",
            regulatory_object="未知监管对象",
            requirement="未识别到明确样板域规则，需业务人员确认。",
            source_excerpt=text[:160],
            confidence=0.45,
        )
    ]
