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
    catalog = _build_1104_seed_catalog_raw()
    # 把 lineage 行回填 system_code/system_name/system_type/owner_team，
    # 让 in-memory 路径和 load_catalog_from_db 路径产出的 lineage 形状一致，
    # 下游 analyzer 能稳定拿到每条 lineage 的真实归属系统。
    system_by_code = {s["system_code"]: s for s in catalog.data_systems}
    system_by_field: dict[str, dict[str, str]] = {}
    for field in catalog.data_fields:
        sys_dict = system_by_code.get(field.get("system_code") or "", {})
        system_by_field[field["field_code"]] = {
            "system_code": field.get("system_code") or "",
            "system_name": sys_dict.get("system_name", ""),
            "system_type": sys_dict.get("system_type", ""),
            "owner_team": field.get("owner_team") or sys_dict.get("owner_team", ""),
            "field_name": field.get("field_name", ""),
        }
    enriched_lineage = []
    for row in catalog.lineage:
        meta = system_by_field.get(row["data_field_code"], {})
        merged = {**row}
        merged.setdefault("data_field_name", meta.get("field_name", ""))
        merged.setdefault("system_code", meta.get("system_code", ""))
        merged.setdefault("system_name", meta.get("system_name", ""))
        merged.setdefault("system_type", meta.get("system_type", ""))
        merged.setdefault("owner_team", meta.get("owner_team", ""))
        enriched_lineage.append(merged)
    return ReportingSeedCatalog(
        reporting_systems=catalog.reporting_systems,
        reporting_versions=catalog.reporting_versions,
        reporting_objects=catalog.reporting_objects,
        reporting_sections=catalog.reporting_sections,
        reporting_items=catalog.reporting_items,
        reporting_instructions=catalog.reporting_instructions,
        reporting_rules=catalog.reporting_rules,
        data_systems=catalog.data_systems,
        data_fields=catalog.data_fields,
        data_field_code_values=catalog.data_field_code_values,
        business_concept_value_mappings=catalog.business_concept_value_mappings,
        measure_field_mappings=catalog.measure_field_mappings,
        lineage=enriched_lineage,
    )


def _build_1104_seed_catalog_raw() -> ReportingSeedCatalog:
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
            # ── 监管报送系统报表字段（已有血缘） ──────────────────────────────
            _field("RPT", "rpt_g24", "interbank_borrowing_bal_top100", "rpt_g24.interbank_borrowing_bal_top100", "G24 最大百家金融机构同业融入余额"),
            _field("RPT", "rpt_g21", "liquidity_gap_30d", "rpt_g21.liquidity_gap_30d", "G21 30 日内流动性期限缺口"),
            _field("RPT", "rpt_g25", "hqla_balance", "rpt_g25.hqla_balance", "G25 合格优质流动性资产余额"),
            _field("RPT", "rpt_g25", "net_cash_outflow_30d", "rpt_g25.net_cash_outflow_30d", "G25 未来 30 日现金净流出量"),
            _field("RPT", "rpt_g27", "interbank_deposit_balance", "rpt_g27.interbank_deposit_balance", "G27 同业存放余额"),
            _field("RPT", "rpt_g31", "bond_investment_balance", "rpt_g31.bond_investment_balance", "G31 债券投资余额"),
            _field("RPT", "rpt_g31_part_i", "pre_lookthrough_balance", "rpt_g31_part_i.pre_lookthrough_balance", "G31 穿透前期末余额"),
            # ── interbank_deal 全字段（含已有血缘字段 + 扩充字段） ───────────
            _field("INTERBANK_CORE", "interbank_deal", "balance", "interbank_deal.balance", "同业交易余额"),
            _field("INTERBANK_CORE", "interbank_deal", "counterparty_fin_org_code", "interbank_deal.counterparty_fin_org_code", "金融机构交易对手代码"),
            _field("INTERBANK_CORE", "interbank_deal", "product_type", "interbank_deal.product_type", "同业产品类型（同业存放/拆借/回购/同业理财等）"),
            _field("INTERBANK_CORE", "interbank_deal", "direction", "interbank_deal.direction", "同业交易方向（资金融出/资金融入）"),
            _field("INTERBANK_CORE", "interbank_deal", "deal_date", "interbank_deal.deal_date", "交易起始日期"),
            _field("INTERBANK_CORE", "interbank_deal", "maturity_date", "interbank_deal.maturity_date", "合同到期日期"),
            _field("INTERBANK_CORE", "interbank_deal", "currency_code", "interbank_deal.currency_code", "交易币种代码"),
            _field("INTERBANK_CORE", "interbank_deal", "interest_rate", "interbank_deal.interest_rate", "交易利率（年化）"),
            _field("INTERBANK_CORE", "interbank_deal", "collateral_type", "interbank_deal.collateral_type", "质押品类型（信用/债券质押/票据等）"),
            _field("INTERBANK_CORE", "interbank_deal", "remaining_days", "interbank_deal.remaining_days", "剩余期限（天数，按报告日计算）"),
            _field("INTERBANK_CORE", "interbank_deal", "deal_status", "interbank_deal.deal_status", "交易状态（有效/到期/提前终止）"),
            # ── bond_investment 全字段 ────────────────────────────────────────
            _field("TREASURY_CORE", "bond_investment", "book_balance", "bond_investment.book_balance", "债券投资账面余额"),
            _field("TREASURY_CORE", "bond_investment", "issuer_type", "bond_investment.issuer_type", "债券发行人类型（政府/金融机构/企业等）"),
            _field("TREASURY_CORE", "bond_investment", "bond_code", "bond_investment.bond_code", "债券代码（Wind/Bloomberg/交易所代码）"),
            _field("TREASURY_CORE", "bond_investment", "bond_name", "bond_investment.bond_name", "债券名称"),
            _field("TREASURY_CORE", "bond_investment", "bond_type", "bond_investment.bond_type", "债券类型（国债/地方债/政策性金融债/企业债/ABS等）"),
            _field("TREASURY_CORE", "bond_investment", "maturity_date", "bond_investment.maturity_date", "债券到期日"),
            _field("TREASURY_CORE", "bond_investment", "coupon_rate", "bond_investment.coupon_rate", "票面利率"),
            _field("TREASURY_CORE", "bond_investment", "modified_duration", "bond_investment.modified_duration", "修正久期，衡量债券价格对收益率变动的敏感度"),
            _field("TREASURY_CORE", "bond_investment", "market_value", "bond_investment.market_value", "债券投资市值（公允价值）"),
            _field("TREASURY_CORE", "bond_investment", "holding_purpose", "bond_investment.holding_purpose", "持有目的分类（AC摊余成本/FVTPL公允价值损益/FVTOCI公允价值其他综合收益）"),
            _field("TREASURY_CORE", "bond_investment", "credit_rating", "bond_investment.credit_rating", "债券信用评级（AAA/AA+/AA等）"),
            _field("TREASURY_CORE", "bond_investment", "green_bond_flag", "bond_investment.green_bond_flag", "绿色债券标识，标注是否为监管认可的绿色债券"),
            _field("TREASURY_CORE", "bond_investment", "remaining_days", "bond_investment.remaining_days", "债券剩余期限（天数）"),
            # ── counterparty 全字段 ───────────────────────────────────────────
            _field("COUNTERPARTY_MDM", "counterparty", "institution_type", "counterparty.institution_type", "交易对手机构类型"),
            _field("COUNTERPARTY_MDM", "counterparty", "country_code", "counterparty.country_code", "交易对手注册国别代码"),
            _field("COUNTERPARTY_MDM", "counterparty", "counterparty_name", "counterparty.counterparty_name", "交易对手名称"),
            _field("COUNTERPARTY_MDM", "counterparty", "credit_rating", "counterparty.credit_rating", "交易对手外部信用评级"),
            _field("COUNTERPARTY_MDM", "counterparty", "is_related_party", "counterparty.is_related_party", "是否关联方（集团内关联机构标识）"),
            _field("COUNTERPARTY_MDM", "counterparty", "group_code", "counterparty.group_code", "所属集团代码，用于最大百家同业集团归并"),
            _field("COUNTERPARTY_MDM", "counterparty", "financial_org_flag", "counterparty.financial_org_flag", "是否金融机构标识（1104 报送口径判断依据）"),
            _field("COUNTERPARTY_MDM", "counterparty", "top100_flag", "counterparty.top100_flag", "是否纳入最大百家金融机构同业统计"),
            # ── dm_interbank_position 全字段 ──────────────────────────────────
            _field("DM_TREASURY", "dm_interbank_position", "balance", "dm_interbank_position.balance", "同业业务余额"),
            _field("DM_TREASURY", "dm_interbank_position", "maturity_date", "dm_interbank_position.maturity_date", "到期日"),
            _field("DM_TREASURY", "dm_interbank_position", "deal_direction", "dm_interbank_position.deal_direction", "资金方向（融出/融入）"),
            _field("DM_TREASURY", "dm_interbank_position", "counterparty_code", "dm_interbank_position.counterparty_code", "交易对手代码"),
            _field("DM_TREASURY", "dm_interbank_position", "remaining_days", "dm_interbank_position.remaining_days", "剩余期限天数"),
            _field("DM_TREASURY", "dm_interbank_position", "interest_accrued", "dm_interbank_position.interest_accrued", "应计利息金额"),
            _field("DM_TREASURY", "dm_interbank_position", "product_category", "dm_interbank_position.product_category", "同业产品大类"),
            # ── dm_hqla_position 全字段 ───────────────────────────────────────
            _field("DM_TREASURY", "dm_hqla_position", "hqla_balance", "dm_hqla_position.hqla_balance", "合格优质流动性资产余额"),
            _field("DM_TREASURY", "dm_hqla_position", "hqla_level", "dm_hqla_position.hqla_level", "HQLA 级别（L1/L2A/L2B）"),
            _field("DM_TREASURY", "dm_hqla_position", "asset_code", "dm_hqla_position.asset_code", "资产编码"),
            _field("DM_TREASURY", "dm_hqla_position", "haircut_ratio", "dm_hqla_position.haircut_ratio", "折扣率（压力情景下的资产价值折算比例）"),
            _field("DM_TREASURY", "dm_hqla_position", "currency_code", "dm_hqla_position.currency_code", "币种代码"),
            _field("DM_TREASURY", "dm_hqla_position", "is_central_bank_eligible", "dm_hqla_position.is_central_bank_eligible", "是否央行合格抵押品"),
            # ── dm_cash_outflow 全字段 ────────────────────────────────────────
            _field("DM_TREASURY", "dm_cash_outflow", "outflow_amount", "dm_cash_outflow.outflow_amount", "未来 30 日现金流出金额"),
            _field("DM_TREASURY", "dm_cash_outflow", "runoff_factor", "dm_cash_outflow.runoff_factor", "流失率/折扣率（压力情景下的现金流出乘数）"),
            _field("DM_TREASURY", "dm_cash_outflow", "liability_type", "dm_cash_outflow.liability_type", "负债类型（零售存款/企业存款/同业负债等）"),
            _field("DM_TREASURY", "dm_cash_outflow", "counterparty_type", "dm_cash_outflow.counterparty_type", "交易对手类型"),
            _field("DM_TREASURY", "dm_liquidity_cashflow", "cashflow_amount", "dm_liquidity_cashflow.cashflow_amount", "流动性现金流金额"),
            _field("DM_TREASURY", "dm_liquidity_cashflow", "cashflow_direction", "dm_liquidity_cashflow.cashflow_direction", "现金流方向（流入/流出）"),
            _field("DM_TREASURY", "dm_liquidity_cashflow", "maturity_bucket", "dm_liquidity_cashflow.maturity_bucket", "期限分桶（1D/7D/14D/30D等）"),
            # ── ods_invest_position 全字段 ────────────────────────────────────
            _field("ODS_INVEST", "ods_invest_position", "book_balance", "ods_invest_position.book_balance", "投资账面余额"),
            _field("ODS_INVEST", "ods_invest_position", "asset_type", "ods_invest_position.asset_type", "投资资产类型（债券/权益/公募基金/私募/ABS等）"),
            _field("ODS_INVEST", "ods_invest_position", "investment_type", "ods_invest_position.investment_type", "投资管理方式（自主管理/委托管理）"),
            _field("ODS_INVEST", "ods_invest_position", "lookthrough_flag", "ods_invest_position.lookthrough_flag", "是否需穿透（非底层资产标识）"),
            _field("ODS_INVEST", "ods_invest_position", "underlying_asset_type", "ods_invest_position.underlying_asset_type", "穿透后底层资产类型"),
            _field("ODS_INVEST", "ods_invest_position", "fund_manager", "ods_invest_position.fund_manager", "基金管理人名称（委托管理时填写）"),
            _field("ODS_INVEST", "ods_invest_position", "risk_level", "ods_invest_position.risk_level", "投资风险等级"),
            _field("ODS_INVEST", "ods_invest_position", "green_investment_flag", "ods_invest_position.green_investment_flag", "绿色投资标识，标注是否符合绿色金融认定标准"),
            # ── dm_g31_position 全字段 ────────────────────────────────────────
            _field("DM_INVESTMENT", "dm_g31_position", "position_balance", "dm_g31_position.position_balance", "投资持仓余额"),
            _field("DM_INVESTMENT", "dm_g31_position", "asset_category", "dm_g31_position.asset_category", "资产类别（债券/权益/公募基金等）"),
            _field("DM_INVESTMENT", "dm_g31_position", "lookthrough_balance", "dm_g31_position.lookthrough_balance", "穿透后余额（非底层资产穿透计算结果）"),
            _field("DM_INVESTMENT", "dm_g31_position", "bond_modified_duration", "dm_g31_position.bond_modified_duration", "债券修正久期（持仓加权平均）"),
            _field("DM_INVESTMENT", "dm_g31_position", "investment_income_ytd", "dm_g31_position.investment_income_ytd", "年初至报告期末投资收入"),
            _field("DM_INVESTMENT", "dm_g31_position", "portfolio_code", "dm_g31_position.portfolio_code", "投资组合代码"),
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
