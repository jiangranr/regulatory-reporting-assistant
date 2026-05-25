from dataclasses import dataclass
import json


@dataclass(frozen=True)
class ReportingSeedCatalog:
    reporting_systems: list[dict[str, str]]
    reporting_versions: list[dict[str, str | int]]
    reporting_objects: list[dict[str, str]]
    reporting_sections: list[dict[str, str | int]]
    reporting_items: list[dict[str, str]]
    reporting_instructions: list[dict[str, str]]
    reporting_rules: list[dict[str, str]]
    data_systems: list[dict[str, str]]
    data_fields: list[dict[str, str]]
    data_field_code_values: list[dict[str, str]]
    business_concept_value_mappings: list[dict[str, str | float]]
    measure_field_mappings: list[dict[str, str | int | float]]
    lineage: list[dict[str, str]]


def build_1104_seed_catalog() -> ReportingSeedCatalog:
    return ReportingSeedCatalog(
        reporting_systems=[
            {
                "system_code": "1104",
                "system_name": "1104 非现场监管报表",
                "regulator": "国家金融监督管理总局",
                "description": "银行业非现场监管报表体系，一期聚焦资金同业域。",
                "status": "ACTIVE",
            }
        ],
        reporting_versions=[
            {
                "reporting_system_code": "1104",
                "version_code": "2025_251",
                "version_name": "2025 年 251 版",
                "effective_year": 2025,
                "status": "ACTIVE",
            }
        ],
        reporting_objects=[
            _object("G21", "流动性期限缺口统计表", "基础类报表/流动性风险", "月"),
            _object("G24", "最大百家金融机构同业融入情况表", "基础类报表/流动性风险", "季"),
            _object("G25", "流动性覆盖率和净稳定融资比例情况表", "基础类报表/流动性风险", "月"),
            _object("G27", "主要负债项目明细表", "业务类报表/负债业务", "季"),
            _object("G31", "投资业务情况表第 I 部分：底层资产投资情况", "业务类报表/投资业务", "季"),
        ],
        reporting_sections=[
            _section("G21", "MAIN", "主表", 1),
            _section("G24", "MAIN", "主表", 1),
            _section("G25", "PART_I", "第 I 部分：流动性覆盖率", 1),
            _section("G27", "MAIN", "主表", 1),
            _section("G31", "PART_I", "第 I 部分：底层资产投资情况", 1),
        ],
        reporting_items=[
            _item("G21", "MAIN", "G21.MAIN.LIQUIDITY_GAP_30D", "30 日内流动性期限缺口", "30 日内", "期限缺口", "缺口"),
            _item("G24", "MAIN", "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "最大百家金融机构同业融入余额", "金融机构同业融入", "余额", "余额"),
            _item("G25", "PART_I", "G25.PART_I.HQLA_BALANCE", "合格优质流动性资产余额", "合格优质流动性资产", "余额", "余额"),
            _item("G25", "PART_I", "G25.PART_I.NET_CASH_OUTFLOW_30D", "未来 30 日现金净流出量", "未来 30 日", "现金净流出", "金额"),
            _item("G27", "MAIN", "G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "同业存放余额", "同业存放", "余额", "余额"),
            _item("G31", "PART_I", "G31.PART_I.BOND_INVESTMENT_BALANCE", "债券投资余额", "债券投资", "余额", "余额"),
        ],
        reporting_instructions=[
            _instruction("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "统计最大百家金融机构同业融入余额，需识别交易对手金融机构、同业负债产品、余额和到期日。"),
            _instruction("G21.MAIN.LIQUIDITY_GAP_30D", "按剩余期限统计未来 30 日内资产负债现金流入流出并计算期限缺口。"),
            _instruction("G25.PART_I.HQLA_BALANCE", "统计符合监管口径的合格优质流动性资产余额。"),
            _instruction("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "统计主要负债项目中的同业存放余额。"),
            _instruction("G31.PART_I.BOND_INVESTMENT_BALANCE", "统计投资业务底层资产中的债券投资余额。"),
        ],
        reporting_rules=[
            _rule(
                "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
                "RR_G24_INTERBANK_BORROWING_SCOPE",
                "同业融入余额统计口径",
                "INDICATOR_SCOPE",
                "counterparty.type = 'FINANCIAL_INSTITUTION' and interbank_deal.direction = 'BORROWING'",
            )
        ],
        data_systems=[
            _data_system("RPT", "监管报送系统", "REPORTING", "监管报送团队"),
            _data_system("DM_TREASURY", "资金同业数据集市", "MART", "数据平台团队"),
            _data_system("INTERBANK_CORE", "同业业务系统", "SOURCE", "金融市场科技团队"),
            _data_system("TREASURY_CORE", "资金交易系统", "SOURCE", "资金交易科技团队"),
            _data_system("COUNTERPARTY_MDM", "交易对手主数据系统", "MDM", "数据治理团队"),
            _data_system("DM_INVESTMENT", "投资业务数据集市", "MART", "数据平台团队"),
            _data_system("ODS_INVEST", "投资持仓源系统", "SOURCE", "金融市场科技团队"),
        ],
        data_fields=[
            _field("RPT", "rpt_g24", "interbank_borrowing_bal_top100", "rpt_g24.interbank_borrowing_bal_top100", "G24 最大百家金融机构同业融入余额"),
            _field("RPT", "rpt_g21", "liquidity_gap_30d", "rpt_g21.liquidity_gap_30d", "G21 30 日内流动性期限缺口"),
            _field("RPT", "rpt_g25", "hqla_balance", "rpt_g25.hqla_balance", "G25 合格优质流动性资产余额"),
            _field("RPT", "rpt_g25", "net_cash_outflow_30d", "rpt_g25.net_cash_outflow_30d", "G25 未来 30 日现金净流出量"),
            _field("RPT", "rpt_g27", "interbank_deposit_balance", "rpt_g27.interbank_deposit_balance", "G27 同业存放余额"),
            _field("RPT", "rpt_g31", "bond_investment_balance", "rpt_g31.bond_investment_balance", "G31 债券投资余额"),
            _field("DM_TREASURY", "dm_interbank_position", "balance", "dm_interbank_position.balance", "同业业务余额"),
            _field("DM_TREASURY", "dm_interbank_position", "maturity_date", "dm_interbank_position.maturity_date", "到期日"),
            _field("DM_TREASURY", "dm_liquidity_cashflow", "cashflow_amount", "dm_liquidity_cashflow.cashflow_amount", "流动性现金流金额"),
            _field("INTERBANK_CORE", "interbank_deal", "balance", "interbank_deal.balance", "同业交易余额"),
            _field("INTERBANK_CORE", "interbank_deal", "counterparty_fin_org_code", "interbank_deal.counterparty_fin_org_code", "金融机构交易对手代码"),
            _field("INTERBANK_CORE", "interbank_deal", "product_type", "interbank_deal.product_type", "同业产品类型"),
            _field("TREASURY_CORE", "bond_investment", "book_balance", "bond_investment.book_balance", "债券投资账面余额"),
            _field("TREASURY_CORE", "bond_investment", "issuer_type", "bond_investment.issuer_type", "债券发行人类型"),
            _field("COUNTERPARTY_MDM", "counterparty", "institution_type", "counterparty.institution_type", "交易对手机构类型"),
            _field("COUNTERPARTY_MDM", "counterparty", "country_code", "counterparty.country_code", "交易对手国别代码"),
            # G25 / 流动性覆盖率新增源字段
            _field("DM_TREASURY", "dm_hqla_position", "hqla_balance", "dm_hqla_position.hqla_balance", "合格优质流动性资产余额"),
            _field("DM_TREASURY", "dm_hqla_position", "hqla_level", "dm_hqla_position.hqla_level", "HQLA 级别（L1/L2A/L2B）"),
            _field("DM_TREASURY", "dm_cash_outflow", "outflow_amount", "dm_cash_outflow.outflow_amount", "未来 30 日现金流出金额"),
            _field("DM_TREASURY", "dm_cash_outflow", "runoff_factor", "dm_cash_outflow.runoff_factor", "流失率/折扣率"),
            # G27 / 主要负债项目源字段
            _field("INTERBANK_CORE", "interbank_deal", "direction", "interbank_deal.direction", "同业交易方向"),
            # G31 / 投资余额组合命中字段
            _field("RPT", "rpt_g31_part_i", "pre_lookthrough_balance", "rpt_g31_part_i.pre_lookthrough_balance", "G31 穿透前期末余额"),
            _field("DM_INVESTMENT", "dm_g31_position", "position_balance", "dm_g31_position.position_balance", "投资持仓余额"),
            _field("ODS_INVEST", "ods_invest_position", "book_balance", "ods_invest_position.book_balance", "投资账面余额"),
            _field("ODS_INVEST", "ods_invest_position", "asset_type", "ods_invest_position.asset_type", "投资资产类型"),
        ],
        data_field_code_values=[
            _code_value(
                "ods_invest_position.asset_type",
                "INVEST_ASSET_TYPE",
                "PREFERRED_STOCK",
                "优先股",
                ("优先股", "优先股投资"),
                parent_value_code="EQUITY",
                confidence_level="HIGH",
            ),
            _code_value(
                "ods_invest_position.asset_type",
                "INVEST_ASSET_TYPE",
                "BANK_ACCEPTANCE_BILL",
                "银行承兑汇票",
                ("银行承兑汇票", "银票", "银行承兑票据"),
                parent_value_code="BILL",
                confidence_level="HIGH",
            ),
            _code_value(
                "ods_invest_position.asset_type",
                "INVEST_ASSET_TYPE",
                "COMMERCIAL_ACCEPTANCE_BILL",
                "商业承兑汇票",
                ("商业承兑汇票", "商票", "商业承兑票据"),
                parent_value_code="BILL",
                confidence_level="HIGH",
            ),
        ],
        business_concept_value_mappings=[
            _concept_value_mapping(
                "CON_PREFERRED_STOCK",
                "优先股",
                "ods_invest_position.asset_type",
                "PREFERRED_STOCK",
                "优先股",
                ("优先股", "优先股投资"),
                confidence_score=0.95,
            ),
            _concept_value_mapping(
                "CON_BILL",
                "票据",
                "ods_invest_position.asset_type",
                "BANK_ACCEPTANCE_BILL",
                "银行承兑汇票",
                ("票据", "票据投资"),
                confidence_score=0.9,
            ),
            _concept_value_mapping(
                "CON_BILL",
                "票据",
                "ods_invest_position.asset_type",
                "COMMERCIAL_ACCEPTANCE_BILL",
                "商业承兑汇票",
                ("票据", "票据投资"),
                confidence_score=0.9,
            ),
        ],
        measure_field_mappings=[
            _measure_field_mapping(
                "MEASURE_INVESTMENT_BALANCE",
                "投资余额",
                "G31",
                "rpt_g31_part_i.pre_lookthrough_balance",
                "REPORT_MEASURE_FIELD",
                priority=10,
                confidence_score=0.9,
            ),
            _measure_field_mapping(
                "MEASURE_INVESTMENT_BALANCE",
                "投资余额",
                "G31",
                "dm_g31_position.position_balance",
                "MEASURE_FIELD",
                priority=20,
                confidence_score=0.9,
            ),
            _measure_field_mapping(
                "MEASURE_INVESTMENT_BALANCE",
                "投资余额",
                "G31",
                "ods_invest_position.book_balance",
                "SOURCE_MEASURE_FIELD",
                priority=30,
                confidence_score=0.85,
            ),
        ],
        lineage=[
            # G24 · 最大百家同业融入（主线，链路最完整）
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "rpt_g24.interbank_borrowing_bal_top100", "REPORT_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "dm_interbank_position.balance", "SOURCE_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "interbank_deal.balance", "SOURCE_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "interbank_deal.counterparty_fin_org_code", "DIMENSION_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "interbank_deal.direction", "FILTER_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "counterparty.institution_type", "FILTER_FIELD"),
            _lineage("G24.MAIN.INTERBANK_BORROWING_BAL_TOP100", "counterparty.country_code", "DIMENSION_FIELD"),
            # G21 · 流动性期限缺口（与 G24 共享 dm_interbank_position）
            _lineage("G21.MAIN.LIQUIDITY_GAP_30D", "rpt_g21.liquidity_gap_30d", "REPORT_FIELD"),
            _lineage("G21.MAIN.LIQUIDITY_GAP_30D", "dm_liquidity_cashflow.cashflow_amount", "SOURCE_FIELD"),
            _lineage("G21.MAIN.LIQUIDITY_GAP_30D", "dm_interbank_position.balance", "SOURCE_FIELD"),
            _lineage("G21.MAIN.LIQUIDITY_GAP_30D", "dm_interbank_position.maturity_date", "FILTER_FIELD"),
            _lineage("G21.MAIN.LIQUIDITY_GAP_30D", "interbank_deal.balance", "SOURCE_FIELD"),
            # G25 · HQLA 余额 + 净现金流出
            _lineage("G25.PART_I.HQLA_BALANCE", "rpt_g25.hqla_balance", "REPORT_FIELD"),
            _lineage("G25.PART_I.HQLA_BALANCE", "dm_hqla_position.hqla_balance", "SOURCE_FIELD"),
            _lineage("G25.PART_I.HQLA_BALANCE", "dm_hqla_position.hqla_level", "DIMENSION_FIELD"),
            _lineage("G25.PART_I.HQLA_BALANCE", "bond_investment.issuer_type", "FILTER_FIELD"),
            _lineage("G25.PART_I.NET_CASH_OUTFLOW_30D", "rpt_g25.net_cash_outflow_30d", "REPORT_FIELD"),
            _lineage("G25.PART_I.NET_CASH_OUTFLOW_30D", "dm_cash_outflow.outflow_amount", "SOURCE_FIELD"),
            _lineage("G25.PART_I.NET_CASH_OUTFLOW_30D", "dm_cash_outflow.runoff_factor", "FILTER_FIELD"),
            _lineage("G25.PART_I.NET_CASH_OUTFLOW_30D", "interbank_deal.direction", "FILTER_FIELD"),
            # G27 · 同业存放余额（与 G24/G21 共享 dm_interbank_position 与 counterparty）
            _lineage("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "rpt_g27.interbank_deposit_balance", "REPORT_FIELD"),
            _lineage("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "dm_interbank_position.balance", "SOURCE_FIELD"),
            _lineage("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "interbank_deal.direction", "FILTER_FIELD"),
            _lineage("G27.MAIN.INTERBANK_DEPOSIT_BALANCE", "counterparty.institution_type", "FILTER_FIELD"),
            # G31 · 债券投资余额
            _lineage("G31.PART_I.BOND_INVESTMENT_BALANCE", "rpt_g31.bond_investment_balance", "REPORT_FIELD"),
            _lineage("G31.PART_I.BOND_INVESTMENT_BALANCE", "bond_investment.book_balance", "SOURCE_FIELD"),
            _lineage("G31.PART_I.BOND_INVESTMENT_BALANCE", "bond_investment.issuer_type", "DIMENSION_FIELD"),
        ],
    )


def _object(code: str, name: str, category: str, frequency: str) -> dict[str, str]:
    return {"object_code": code, "object_name": name, "object_type": "REPORT", "category": category, "frequency": frequency, "status": "ACTIVE"}


def _section(object_code: str, section_code: str, section_name: str, order_no: int) -> dict[str, str | int]:
    return {"object_code": object_code, "section_code": section_code, "section_name": section_name, "order_no": order_no, "status": "ACTIVE"}


def _item(object_code: str, section_code: str, item_code: str, item_name: str, row_label: str, column_label: str, measure_type: str) -> dict[str, str]:
    return {"object_code": object_code, "section_code": section_code, "item_code": item_code, "item_name": item_name, "item_type": "INDICATOR", "row_label": row_label, "column_label": column_label, "measure_type": measure_type, "unit": "万元", "status": "ACTIVE"}


def _instruction(item_code: str, text: str) -> dict[str, str]:
    return {"item_code": item_code, "instruction_text": text, "source_location": "1104 资金同业一期样板", "status": "ACTIVE"}


def _rule(item_code: str, rule_code: str, rule_name: str, rule_type: str, expression: str) -> dict[str, str]:
    return {"item_code": item_code, "rule_code": rule_code, "rule_name": rule_name, "rule_type": rule_type, "rule_expression": expression, "confidence_level": "MEDIUM", "review_status": "PENDING", "status": "ACTIVE"}


def _data_system(code: str, name: str, system_type: str, owner_team: str) -> dict[str, str]:
    return {"system_code": code, "system_name": name, "system_type": system_type, "owner_team": owner_team, "status": "ACTIVE"}


def _field(system_code: str, table_name: str, column_name: str, field_code: str, field_name: str) -> dict[str, str]:
    return {"system_code": system_code, "table_name": table_name, "column_name": column_name, "field_code": field_code, "field_name": field_name, "data_type": "VARCHAR", "business_meaning": field_name, "owner_team": "", "status": "ACTIVE"}


def _lineage(item_code: str, field_code: str, role: str) -> dict[str, str]:
    return {"reporting_item_code": item_code, "data_field_code": field_code, "lineage_role": role, "transform_logic": "", "evidence_type": "SAMPLE", "evidence_ref": "1104 资金同业一期样板", "confidence_level": "MEDIUM", "review_status": "PENDING", "status": "ACTIVE"}


def _code_value(
    field_code: str,
    code_set: str,
    value_code: str,
    value_name: str,
    aliases: tuple[str, ...],
    parent_value_code: str = "",
    confidence_level: str = "MEDIUM",
) -> dict[str, str]:
    return {
        "field_code": field_code,
        "code_set": code_set,
        "value_code": value_code,
        "value_name": value_name,
        "value_aliases": json.dumps(list(aliases), ensure_ascii=False),
        "parent_value_code": parent_value_code,
        "source": "1104_seed",
        "confidence_level": confidence_level,
        "status": "ACTIVE",
    }


def _concept_value_mapping(
    concept_code: str,
    concept_name: str,
    field_code: str,
    value_code: str,
    value_name: str,
    aliases: tuple[str, ...],
    confidence_score: float,
) -> dict[str, str | float]:
    return {
        "concept_code": concept_code,
        "concept_name": concept_name,
        "field_code": field_code,
        "value_code": value_code,
        "value_name": value_name,
        "match_aliases": json.dumps(list(aliases), ensure_ascii=False),
        "mapping_status": "CONFIRMED",
        "confidence_score": confidence_score,
        "evidence_text": "1104_seed",
    }


def _measure_field_mapping(
    measure_concept_code: str,
    measure_concept_name: str,
    reporting_object_code: str,
    field_code: str,
    field_role: str,
    priority: int,
    confidence_score: float,
) -> dict[str, str | int | float]:
    return {
        "measure_concept_code": measure_concept_code,
        "measure_concept_name": measure_concept_name,
        "reporting_system_code": "1104",
        "reporting_object_code": reporting_object_code,
        "reporting_section_code": "PART_I",
        "field_code": field_code,
        "field_role": field_role,
        "priority": priority,
        "confidence_score": confidence_score,
        "status": "ACTIVE",
        "evidence_text": "1104_seed",
    }
