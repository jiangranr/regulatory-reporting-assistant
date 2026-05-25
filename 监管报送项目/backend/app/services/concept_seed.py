"""一期 P0 种子：监管报送概念知识库 + 报送规则卡片。

设计依据: docs/rule-card-and-concept-kb-design.md 第 4.3 / 6.11 节。

注意:
- G31 卡片正文是基于公开 1104 G31 投资业务报表常识起草的"准真实"内容,
  evidence_verified=False (P1 会从真实填报说明 doc 抽并核对)。
- G24/G21 概念为支撑"跨表辐射"演示,手工灌入,evidence_text 标注为 manual_seed。
- 整个函数幂等：concept_code / card_code 已存在则跳过。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.models.db_models import (
    RegConcept,
    RegConceptAlias,
    RegConceptReportingItemMap,
    RegReportingRuleCard,
    RegReportingRuleCardConceptMap,
)


@dataclass(frozen=True)
class ConceptSeed:
    concept_code: str
    canonical_name: str
    short_definition: str
    concept_type: str  # METRIC / SCOPE / CLASSIFICATION / CALCULATION / DIMENSION / ENTITY
    reporting_system_scope: str
    aliases: tuple[str, ...]
    related_items: tuple[tuple[str, str], ...]  # (reporting_item_code, role)


@dataclass(frozen=True)
class RuleCardSeed:
    card_code: str
    reporting_object_code: str | None  # 对象级时填,指标级时可同时填 reporting_item_code
    reporting_item_code: str | None
    card_level: str
    card_title: str
    card_text: str
    source_location: str
    evidence_text: str
    confidence_level: str
    related_concept_codes: tuple[tuple[str, str], ...]  # (concept_code, role)


# --------------------------------------------------------------------------- #
# 20 个初始概念
# --------------------------------------------------------------------------- #

CONCEPTS_G31: list[ConceptSeed] = [
    ConceptSeed(
        "CON_UNDERLYING_ASSET", "底层资产", "投资业务穿透到的最终标的资产",
        "SCOPE", "1104",
        ("底层资产", "穿透后资产", "最终标的"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "ANNOTATION"),),
    ),
    ConceptSeed(
        "CON_INVESTMENT_BIZ", "投资业务", "银行表内/表外的投资类业务总称",
        "SCOPE", "1104",
        ("投资业务",),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "ANNOTATION"),),
    ),
    ConceptSeed(
        "CON_BOND_INVESTMENT_BAL", "债券投资余额", "G31 中按债券类型分类的投资账面余额",
        "METRIC", "1104",
        ("债券投资余额", "债券投资账面余额", "持有债券余额"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "PRIMARY_METRIC"),),
    ),
    ConceptSeed(
        "CON_ASSET_MGMT_PRODUCT", "资产管理产品", "公募基金、理财、信托、ABS 等结构化产品的统称",
        "CLASSIFICATION", "1104",
        ("资产管理产品", "资管产品", "资管计划"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "ANNOTATION"),),
    ),
    ConceptSeed(
        "CON_LOOK_THROUGH", "穿透原则", "把结构化产品按底层资产类型还原到对应报送行的口径",
        "CALCULATION", "1104",
        ("穿透原则", "穿透填报", "穿透法"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "FILTER"),),
    ),
    ConceptSeed(
        "CON_ACCRUED_INTEREST", "应收利息", "计提日已发生但尚未实际收到的利息款项",
        "SCOPE", "1104",
        ("应收利息", "已计提未收利息"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "ANNOTATION"),),
    ),
    ConceptSeed(
        "CON_BANKING_BOOK_PROPRIETARY", "表内自营投资", "银行用自有资金、计入表内的投资业务",
        "SCOPE", "1104",
        ("表内自营投资", "自营投资", "自营头寸"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "FILTER"),),
    ),
    ConceptSeed(
        "CON_EQUITY_INVESTMENT", "股票投资", "普通股、优先股等权益类投资",
        "CLASSIFICATION", "1104",
        ("股票投资", "权益投资", "股权投资"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "EXCLUSION"),),
    ),
    ConceptSeed(
        "CON_ISSUER_TYPE", "发行人类型", "政府/央行/政策性银行/商业银行/企业等",
        "DIMENSION", "1104",
        ("发行人类型", "发行人分类", "issuer type"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "DIMENSION"),),
    ),
    ConceptSeed(
        "CON_BOOK_BALANCE", "投资账面余额", "会计账面口径的余额(含减值准备前/后口径区分)",
        "METRIC", "1104",
        ("投资账面余额", "账面余额", "账面价值"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "PRIMARY_METRIC"),),
    ),
    ConceptSeed(
        "CON_PREFERRED_STOCK", "优先股", "兼具权益属性和固定收益特征的优先股投资分类",
        "CLASSIFICATION", "1104",
        ("优先股", "优先股投资"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "EXCLUSION"),),
    ),
    ConceptSeed(
        "CON_BILL", "票据", "银行承兑汇票、商业承兑汇票等票据类投资资产",
        "CLASSIFICATION", "1104",
        ("票据", "票据投资"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "EXCLUSION"),),
    ),
    ConceptSeed(
        "MEASURE_INVESTMENT_BALANCE", "投资余额", "投资业务余额类度量概念，可落到报送字段、集市字段或源系统账面余额字段",
        "MEASURE", "1104",
        ("投资余额", "账面余额", "期末余额", "穿透前期末余额"),
        (
            ("G31.PART_I.BOND_INVESTMENT_BALANCE", "PRIMARY_METRIC"),
            ("G31.PART_I.1_0.A_穿透前_期末余额", "PRIMARY_METRIC"),
        ),
    ),
    ConceptSeed(
        "CON_RWA", "风险加权资产", "按 RWA 口径折算的资产规模",
        "METRIC", "CROSS",
        ("风险加权资产", "RWA"),
        (),
    ),
    ConceptSeed(
        "CON_ABS", "资产支持证券(ABS)", "以基础资产产生的现金流作为偿付来源的证券",
        "CLASSIFICATION", "1104",
        ("资产支持证券", "ABS", "资产证券化"),
        (("G31.PART_I.BOND_INVESTMENT_BALANCE", "ANNOTATION"),),
    ),
]

CONCEPTS_CROSS_TABLE: list[ConceptSeed] = [
    ConceptSeed(
        "CON_INTERBANK_BORROWING_BAL", "同业融入余额",
        "商业银行向其他金融机构融入资金的余额",
        "METRIC", "1104",
        ("同业融入余额", "同业融入", "拆入资金余额"),
        (("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "PRIMARY_METRIC"),),
    ),
    ConceptSeed(
        "CON_FINANCIAL_INSTITUTION", "金融机构",
        "央行/政策银行/商业银行/证券/保险/信托等",
        "ENTITY", "CROSS",
        ("金融机构", "金融机构同业", "fin org"),
        (
            ("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "FILTER"),
            ("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "FILTER"),
        ),
    ),
    ConceptSeed(
        "CON_TOP_100", "最大百家",
        "按余额排序的前 100 家交易对手",
        "SCOPE", "1104",
        ("最大百家", "最大 100 家", "Top 100"),
        (("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "FILTER"),),
    ),
    ConceptSeed(
        "CON_COUNTERPARTY", "交易对手",
        "同业交易、衍生品、回购等业务的对手方",
        "ENTITY", "CROSS",
        ("交易对手", "对手方", "counterparty"),
        (
            ("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "DIMENSION"),
            ("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "DIMENSION"),
        ),
    ),
    ConceptSeed(
        "CON_LIQUIDITY_GAP", "流动性期限缺口",
        "未来某时段内资产现金流入与负债现金流出之差",
        "METRIC", "1104",
        ("流动性期限缺口", "期限缺口", "liquidity gap"),
        (("G21.MAIN.LIQUIDITY_GAP_30D", "PRIMARY_METRIC"),),
    ),
    ConceptSeed(
        "CON_HQLA", "合格优质流动性资产",
        "LCR 计算中符合监管口径的高流动性资产",
        "METRIC", "1104",
        ("合格优质流动性资产", "HQLA", "高质量流动性资产"),
        (("G25.PART_I.HQLA_BALANCE", "PRIMARY_METRIC"),),
    ),
    ConceptSeed(
        "CON_LCR", "流动性覆盖率",
        "HQLA 余额 / 未来 30 日现金净流出",
        "METRIC", "1104",
        ("流动性覆盖率", "LCR"),
        (
            ("G25.PART_I.HQLA_BALANCE", "PRIMARY_METRIC"),
            ("G25.PART_I.NET_CASH_OUTFLOW_30D", "DENOMINATOR"),
        ),
    ),
    ConceptSeed(
        "CON_INTERBANK_DEPOSIT", "同业存放",
        "其他金融机构存放在本机构的资金余额",
        "METRIC", "1104",
        ("同业存放", "同业存放余额"),
        (("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "PRIMARY_METRIC"),),
    ),
]


ALL_CONCEPTS: list[ConceptSeed] = CONCEPTS_G31 + CONCEPTS_CROSS_TABLE


# --------------------------------------------------------------------------- #
# G31 L1 规则卡片(P0 手工种子,evidence_verified=False;P1 用 LLM 重抽并核对)
# --------------------------------------------------------------------------- #

RULE_CARDS_G31: list[RuleCardSeed] = [
    RuleCardSeed(
        "RC_G31_SCOPE_001", "G31", None, "L1",
        "G31 表统计范围",
        "本表统计银行业金融机构表内自营投资业务的底层资产分布情况，不含表内自营投资中的股票投资以及衍生品投资。资产管理产品按穿透原则填报。",
        "G31 填报说明 §1.1 总体说明",
        "本表统计银行业金融机构表内自营投资业务的底层资产分布情况",
        "HIGH",
        (
            ("CON_BANKING_BOOK_PROPRIETARY", "SUBJECT"),
            ("CON_UNDERLYING_ASSET", "OBJECT"),
            ("CON_EQUITY_INVESTMENT", "QUALIFIER"),
            ("CON_LOOK_THROUGH", "RELATED"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_BOND_BAL_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "债券投资余额包含应收利息",
        "债券投资余额按账面价值口径填报，含已计提的应收利息。计提日应不晚于报告日。",
        "G31 填报说明 §3.2 债券投资",
        "债券投资余额按账面价值口径填报，含已计提的应收利息",
        "HIGH",
        (
            ("CON_BOND_INVESTMENT_BAL", "SUBJECT"),
            ("CON_ACCRUED_INTEREST", "OBJECT"),
            ("CON_BOOK_BALANCE", "QUALIFIER"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_BOND_BAL_002", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "股票投资不计入债券投资余额",
        "债券投资余额不包括股票、优先股以及其他权益类投资。",
        "G31 填报说明 §3.2 债券投资",
        "不包括股票、优先股以及其他权益类投资",
        "HIGH",
        (
            ("CON_BOND_INVESTMENT_BAL", "SUBJECT"),
            ("CON_EQUITY_INVESTMENT", "OBJECT"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_ABS_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "资产支持证券按底层资产穿透填报",
        "投资资产支持证券(ABS)的，应按底层基础资产类型归入相应债券类别填报；穿透有困难的，单列资产支持证券。",
        "G31 填报说明 §3.4 资产支持证券",
        "应按底层基础资产类型归入相应债券类别填报",
        "HIGH",
        (
            ("CON_ABS", "SUBJECT"),
            ("CON_LOOK_THROUGH", "RELATED"),
            ("CON_UNDERLYING_ASSET", "OBJECT"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_ISSUER_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "按发行人类型分别填报",
        "应按发行人类型分别填报：政府债券、央行票据、政策性金融债、商业银行债、企业债、同业存单、其他。",
        "G31 填报说明 §3.3 发行人分类",
        "应按发行人类型分别填报：政府债券、央行票据、政策性金融债、商业银行债、企业债、同业存单、其他",
        "HIGH",
        (
            ("CON_ISSUER_TYPE", "SUBJECT"),
            ("CON_BOND_INVESTMENT_BAL", "RELATED"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_AMP_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "资产管理产品穿透到底层资产",
        "投资公募基金、理财、信托等资产管理产品的，应穿透到底层资产填报；无法穿透的部分单独列示并注明原因。",
        "G31 填报说明 §3.5 资产管理产品",
        "应穿透到底层资产填报；无法穿透的部分单独列示并注明原因",
        "HIGH",
        (
            ("CON_ASSET_MGMT_PRODUCT", "SUBJECT"),
            ("CON_LOOK_THROUGH", "RELATED"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_NCD_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "同业存单纳入债券投资统计",
        "投资同业存单(NCD)的，应纳入债券投资范围，按发行机构类型归入「商业银行债」或单列同业存单。",
        "G31 填报说明 §3.3 发行人分类 - 注 2",
        "投资同业存单(NCD)的，应纳入债券投资范围",
        "MEDIUM",
        (
            ("CON_BOND_INVESTMENT_BAL", "SUBJECT"),
            ("CON_ISSUER_TYPE", "QUALIFIER"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_FX_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "境外发行人单独标识",
        "对于境外发行人发行的债券，应在发行人类型中标注「境外」前缀，并按报告日汇率折算为人民币填报。",
        "G31 填报说明 §3.6 境外资产",
        "对于境外发行人发行的债券，应在发行人类型中标注境外前缀",
        "MEDIUM",
        (
            ("CON_ISSUER_TYPE", "SUBJECT"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_BILL_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "票据投资单独列示",
        "票据(包括银行承兑汇票、商业承兑汇票)投资不纳入债券投资余额，应在其他投资项中单独列示。",
        "G31 填报说明 §3.7 票据投资",
        "票据投资不纳入债券投资余额，应在其他投资项中单独列示",
        "MEDIUM",
        (
            ("CON_BOND_INVESTMENT_BAL", "SUBJECT"),
        ),
    ),
    RuleCardSeed(
        "RC_G31_VALUATION_001", "G31", "G31.PART_I.BOND_INVESTMENT_BALANCE", "L1",
        "采用账面余额口径,与会计科目对应",
        "本表投资余额采用账面余额口径，与会计核算「债权投资」「其他债权投资」「交易性金融资产」科目对应。",
        "G31 填报说明 §2.1 计量口径",
        "本表投资余额采用账面余额口径",
        "HIGH",
        (
            ("CON_BOOK_BALANCE", "SUBJECT"),
            ("CON_BOND_INVESTMENT_BAL", "RELATED"),
        ),
    ),
]

# 跨表 demo 卡片(为了让 ImpactView 概念辐射有跨表画面)
RULE_CARDS_CROSS: list[RuleCardSeed] = [
    RuleCardSeed(
        "RC_G24_SCOPE_001", "G24", "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "L1",
        "最大百家同业融入余额统计口径",
        "按余额排序，统计期末融入余额最大的前 100 家金融机构同业融入余额，含信用拆借、买入返售、同业存放(被动)的对手方。",
        "G24 填报说明 §1 总体说明",
        "统计期末融入余额最大的前 100 家金融机构",
        "HIGH",
        (
            ("CON_INTERBANK_BORROWING_BAL", "SUBJECT"),
            ("CON_TOP_100", "QUALIFIER"),
            ("CON_FINANCIAL_INSTITUTION", "OBJECT"),
            ("CON_COUNTERPARTY", "RELATED"),
        ),
    ),
    RuleCardSeed(
        "RC_G21_GAP_001", "G21", "G21.MAIN.LIQUIDITY_GAP_30D", "L1",
        "流动性期限缺口按剩余期限统计",
        "按剩余期限统计未来 30 日内资产负债现金流入流出并计算期限缺口；缺口 = 流入 - 流出。",
        "G21 填报说明 §2 计算方法",
        "按剩余期限统计未来 30 日内资产负债现金流入流出",
        "HIGH",
        (
            ("CON_LIQUIDITY_GAP", "SUBJECT"),
        ),
    ),
]


ALL_RULE_CARDS: list[RuleCardSeed] = RULE_CARDS_G31 + RULE_CARDS_CROSS


# --------------------------------------------------------------------------- #
# 写入逻辑
# --------------------------------------------------------------------------- #


def seed_concepts_and_rule_cards(session: Session) -> dict[str, int]:
    """幂等地灌入 20 概念 + 12 卡片 + 关联映射。

    返回各类数量的统计字典,供 API 响应。
    """
    stats = {
        "concepts_added": 0,
        "aliases_added": 0,
        "concept_item_maps_added": 0,
        "rule_cards_added": 0,
        "card_concept_maps_added": 0,
    }

    concept_id_by_code: dict[str, int] = {}

    # 1. 概念主表
    for seed in ALL_CONCEPTS:
        existing = session.exec(
            select(RegConcept).where(RegConcept.concept_code == seed.concept_code)
        ).first()
        if existing:
            concept_id_by_code[seed.concept_code] = existing.id  # type: ignore[assignment]
            continue
        concept = RegConcept(
            concept_code=seed.concept_code,
            canonical_name=seed.canonical_name,
            short_definition=seed.short_definition,
            full_definition=seed.short_definition,
            concept_type=seed.concept_type,
            reporting_system_scope=seed.reporting_system_scope,
            current_version_no=1,
            is_locked=False,
            status="ACTIVE",
            created_by="P0_SEED",
            reviewed_by="P0_SEED",
        )
        session.add(concept)
        session.flush()
        concept_id_by_code[seed.concept_code] = concept.id  # type: ignore[assignment]
        stats["concepts_added"] += 1

    # 2. 别名
    for seed in ALL_CONCEPTS:
        concept_id = concept_id_by_code[seed.concept_code]
        # 先写一条 canonical_name 自身作为 alias 方便匹配
        all_aliases = (seed.canonical_name,) + seed.aliases
        for alias in all_aliases:
            existing = session.exec(
                select(RegConceptAlias)
                .where(RegConceptAlias.concept_id == concept_id)
                .where(RegConceptAlias.alias_text == alias)
            ).first()
            if existing:
                continue
            session.add(
                RegConceptAlias(
                    concept_id=concept_id,
                    alias_text=alias,
                    alias_source="INTERNAL" if alias == seed.canonical_name else "SYNONYM",
                    evidence_text="manual_seed",
                )
            )
            stats["aliases_added"] += 1

    # 3. 概念 ↔ 报送项 映射
    for seed in ALL_CONCEPTS:
        concept_id = concept_id_by_code[seed.concept_code]
        for item_code, role in seed.related_items:
            existing = session.exec(
                select(RegConceptReportingItemMap)
                .where(RegConceptReportingItemMap.concept_id == concept_id)
                .where(RegConceptReportingItemMap.reporting_item_code == item_code)
                .where(RegConceptReportingItemMap.role == role)
            ).first()
            if existing:
                continue
            session.add(
                RegConceptReportingItemMap(
                    concept_id=concept_id,
                    reporting_item_code=item_code,
                    role=role,
                    confidence_level="HIGH",
                )
            )
            stats["concept_item_maps_added"] += 1

    # 4. 规则卡片
    card_id_by_code: dict[str, int] = {}
    for seed in ALL_RULE_CARDS:
        existing = session.exec(
            select(RegReportingRuleCard).where(RegReportingRuleCard.card_code == seed.card_code)
        ).first()
        if existing:
            card_id_by_code[seed.card_code] = existing.id  # type: ignore[assignment]
            continue
        card = RegReportingRuleCard(
            card_code=seed.card_code,
            reporting_object_code=seed.reporting_object_code,
            reporting_item_code=seed.reporting_item_code,
            card_level=seed.card_level,
            card_title=seed.card_title,
            card_text=seed.card_text,
            source_location=seed.source_location,
            evidence_text=seed.evidence_text,
            evidence_verified=False,  # P0 手工种子，未做原文锚定核对
            effective_from_version="2025_251",
            confidence_level=seed.confidence_level,
            review_status="CONFIRMED",  # 种子数据按"已确认"入库以便 demo
            status="ACTIVE",
            created_by="P0_SEED",
            updated_by="P0_SEED",
        )
        session.add(card)
        session.flush()
        card_id_by_code[seed.card_code] = card.id  # type: ignore[assignment]
        stats["rule_cards_added"] += 1

    # 5. 卡片 ↔ 概念 映射
    for seed in ALL_RULE_CARDS:
        card_id = card_id_by_code[seed.card_code]
        for concept_code, role in seed.related_concept_codes:
            concept_id = concept_id_by_code.get(concept_code)
            if concept_id is None:
                continue
            existing = session.exec(
                select(RegReportingRuleCardConceptMap)
                .where(RegReportingRuleCardConceptMap.card_id == card_id)
                .where(RegReportingRuleCardConceptMap.concept_id == concept_id)
                .where(RegReportingRuleCardConceptMap.role == role)
            ).first()
            if existing:
                continue
            session.add(
                RegReportingRuleCardConceptMap(
                    card_id=card_id, concept_id=concept_id, role=role
                )
            )
            stats["card_concept_maps_added"] += 1

    session.commit()
    return stats
