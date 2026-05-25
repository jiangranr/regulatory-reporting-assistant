"""Seed reference lineage mappings for parsed G31 reporting items.

This script inserts simulated but realistic lineage relationships for the
currently parsed G31 Excel item codes. It is idempotent and can be rerun.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine
from app.models.db_models import DataFieldCatalog, DataSystemCatalog, RegReportingItem, ReportingItemLineage


DATA_SYSTEMS = [
    {
        "system_code": "RPT_1104",
        "system_name": "1104报送集市",
        "system_type": "REPORTING",
        "owner_team": "监管报送团队",
        "description": "1104监管报送最终加工和出表层",
    },
    {
        "system_code": "DM_INVESTMENT",
        "system_name": "投资业务数据主题层",
        "system_type": "DM",
        "owner_team": "金融市场数据团队",
        "description": "投资持仓、收益、久期和穿透明细主题数据",
    },
    {
        "system_code": "ODS_INVEST",
        "system_name": "投资交易ODS",
        "system_type": "ODS",
        "owner_team": "投资系统团队",
        "description": "投资管理系统交易、持仓、收益明细落地层",
    },
    {
        "system_code": "IMS",
        "system_name": "投资管理系统",
        "system_type": "SOURCE",
        "owner_team": "金融市场系统团队",
        "description": "投资交易、持仓和产品管理源系统",
    },
    {
        "system_code": "VALUATION",
        "system_name": "估值计量系统",
        "system_type": "SOURCE",
        "owner_team": "估值核算团队",
        "description": "债券估值、价格和风险指标系统",
    },
    {
        "system_code": "GL",
        "system_name": "总账核算系统",
        "system_type": "SOURCE",
        "owner_team": "财务核算团队",
        "description": "投资收益、利息收入和损益核算系统",
    },
    {
        "system_code": "CRMS",
        "system_name": "交易对手与授信系统",
        "system_type": "SOURCE",
        "owner_team": "风险管理系统团队",
        "description": "交易对手、授信和大额风险暴露系统",
    },
]


DATA_FIELDS = [
    ("RPT_1104", "rpt_g31_part_i.pre_lookthrough_balance", "G31穿透前期末余额", "rpt_g31_part_i", "pre_lookthrough_balance", "DECIMAL", "G31表Ⅰ穿透前期末余额最终报送字段"),
    ("RPT_1104", "rpt_g31_part_i.income_ytd", "G31投资收入年初至今", "rpt_g31_part_i", "income_ytd", "DECIMAL", "G31表Ⅰ投资收入年初至报告期末数最终报送字段"),
    ("RPT_1104", "rpt_g31_part_i.modified_duration", "G31修正久期", "rpt_g31_part_i", "modified_duration", "DECIMAL", "G31表Ⅰ修正久期最终报送字段"),
    ("RPT_1104", "rpt_g31_part_i.indirect_holding_balance", "G31间接持有期末余额", "rpt_g31_part_i", "indirect_holding_balance", "DECIMAL", "G31表Ⅰ因持有非底层资产而间接持有期末余额最终报送字段"),
    ("RPT_1104", "rpt_g31_part_i.post_lookthrough_balance", "G31穿透后期末余额", "rpt_g31_part_i", "post_lookthrough_balance", "DECIMAL", "G31表Ⅰ穿透后期末余额最终报送字段"),
    ("DM_INVESTMENT", "dm_g31_position.position_balance", "投资持仓余额", "dm_g31_position", "position_balance", "DECIMAL", "投资资产期末账面余额"),
    ("DM_INVESTMENT", "dm_g31_position.asset_type", "资产类型", "dm_g31_position", "asset_type", "VARCHAR", "债券、基金、资管计划等资产分类"),
    ("DM_INVESTMENT", "dm_g31_income.income_ytd", "投资收入年初至今", "dm_g31_income", "income_ytd", "DECIMAL", "投资收益累计发生额"),
    ("DM_INVESTMENT", "dm_g31_risk.modified_duration", "修正久期", "dm_g31_risk", "modified_duration", "DECIMAL", "投资资产修正久期主题指标"),
    ("DM_INVESTMENT", "dm_g31_lookthrough.underlying_balance", "穿透后底层资产余额", "dm_g31_lookthrough", "underlying_balance", "DECIMAL", "穿透资管、基金、SPV后的底层资产余额"),
    ("DM_INVESTMENT", "dm_g31_lookthrough.indirect_balance", "间接持有底层资产余额", "dm_g31_lookthrough", "indirect_balance", "DECIMAL", "因持有非底层资产而间接持有的底层资产余额"),
    ("ODS_INVEST", "ods_invest_position.book_balance", "投资账面余额", "ods_invest_position", "book_balance", "DECIMAL", "投资系统持仓账面余额"),
    ("ODS_INVEST", "ods_invest_position.market_value", "投资市值", "ods_invest_position", "market_value", "DECIMAL", "投资资产估值市值"),
    ("ODS_INVEST", "ods_invest_position.product_id", "产品代码", "ods_invest_position", "product_id", "VARCHAR", "投资产品唯一标识"),
    ("ODS_INVEST", "ods_invest_position.security_id", "证券代码", "ods_invest_position", "security_id", "VARCHAR", "债券或证券代码"),
    ("ODS_INVEST", "ods_invest_position.asset_type", "投资资产类型", "ods_invest_position", "asset_type", "VARCHAR", "投资持仓资产类型"),
    ("ODS_INVEST", "ods_invest_income.interest_income", "利息收入", "ods_invest_income", "interest_income", "DECIMAL", "债券利息收入"),
    ("ODS_INVEST", "ods_invest_income.investment_gain", "投资收益", "ods_invest_income", "investment_gain", "DECIMAL", "买卖价差、估值变动等投资收益"),
    ("VALUATION", "valuation_bond_metric.modified_duration", "债券修正久期", "valuation_bond_metric", "modified_duration", "DECIMAL", "估值系统计算的债券修正久期"),
    ("VALUATION", "valuation_bond_price.full_price", "债券全价", "valuation_bond_price", "full_price", "DECIMAL", "债券估值全价"),
    ("GL", "gl_investment_income.amount", "总账投资收益金额", "gl_investment_income", "amount", "DECIMAL", "总账投资收益入账金额"),
    ("GL", "gl_accounting_entry.account_code", "会计科目", "gl_accounting_entry", "account_code", "VARCHAR", "投资收益、利息收入等核算科目"),
    ("CRMS", "crms_counterparty.counterparty_id", "交易对手编号", "crms_counterparty", "counterparty_id", "VARCHAR", "投资发行人、管理人或交易对手编号"),
    ("CRMS", "crms_counterparty.institution_type", "机构类型", "crms_counterparty", "institution_type", "VARCHAR", "银行、券商、基金、保险、SPV等机构类型"),
    ("CRMS", "crms_large_exposure.exposure_amount", "大额风险暴露金额", "crms_large_exposure", "exposure_amount", "DECIMAL", "交易对手大额风险暴露口径金额"),
]


LINEAGE = [
    ("G31.PART_I.1_0.A_穿透前_期末余额", "rpt_g31_part_i.pre_lookthrough_balance", "REPORT_FIELD", "direct_mapping", "HIGH"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "dm_g31_position.position_balance", "SOURCE_FIELD", "sum(position_balance)", "HIGH"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "ods_invest_position.book_balance", "SOURCE_FIELD", "sum(book_balance)", "HIGH"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "ods_invest_position.market_value", "SOURCE_FIELD", "fallback market_value when book_balance missing", "MEDIUM"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "dm_g31_position.asset_type", "FILTER_FIELD", "asset_type in ('BOND','ABS','NCD')", "MEDIUM"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "ods_invest_position.security_id", "DIMENSION_FIELD", "group by security_id", "MEDIUM"),
    ("G31.PART_I.1_0.A_穿透前_期末余额", "ods_invest_position.product_id", "DIMENSION_FIELD", "trace investment product", "MEDIUM"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "rpt_g31_part_i.income_ytd", "REPORT_FIELD", "direct_mapping", "HIGH"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "dm_g31_income.income_ytd", "SOURCE_FIELD", "sum(income_ytd)", "HIGH"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "ods_invest_income.interest_income", "SOURCE_FIELD", "sum(interest_income)", "HIGH"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "ods_invest_income.investment_gain", "SOURCE_FIELD", "sum(investment_gain)", "HIGH"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "gl_investment_income.amount", "SOURCE_FIELD", "reconcile sum(amount)", "MEDIUM"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "gl_accounting_entry.account_code", "FILTER_FIELD", "account_code in investment_income_accounts", "MEDIUM"),
    ("G31.PART_I.1_0.B_投资收入_年初至报告期末数", "ods_invest_position.asset_type", "FILTER_FIELD", "asset_type in ('BOND','ABS','NCD')", "MEDIUM"),
    ("G31.PART_I.1_0.C_修正久期", "rpt_g31_part_i.modified_duration", "REPORT_FIELD", "direct_mapping", "HIGH"),
    ("G31.PART_I.1_0.C_修正久期", "dm_g31_risk.modified_duration", "SOURCE_FIELD", "weighted_avg(modified_duration, position_balance)", "HIGH"),
    ("G31.PART_I.1_0.C_修正久期", "valuation_bond_metric.modified_duration", "SOURCE_FIELD", "latest metric as of report_date", "HIGH"),
    ("G31.PART_I.1_0.C_修正久期", "valuation_bond_price.full_price", "SOURCE_FIELD", "duration weight validation", "MEDIUM"),
    ("G31.PART_I.1_0.C_修正久期", "ods_invest_position.book_balance", "SOURCE_FIELD", "weight by book_balance", "MEDIUM"),
    ("G31.PART_I.1_0.C_修正久期", "ods_invest_position.security_id", "DIMENSION_FIELD", "join valuation by security_id", "MEDIUM"),
    ("G31.PART_I.1_0.C_修正久期", "ods_invest_position.asset_type", "FILTER_FIELD", "asset_type in ('BOND','ABS','NCD')", "MEDIUM"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "rpt_g31_part_i.indirect_holding_balance", "REPORT_FIELD", "direct_mapping", "HIGH"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "dm_g31_lookthrough.indirect_balance", "SOURCE_FIELD", "sum(indirect_balance)", "HIGH"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "dm_g31_lookthrough.underlying_balance", "SOURCE_FIELD", "sum(underlying_balance where underlying_asset_type='BOND')", "HIGH"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "ods_invest_position.product_id", "DIMENSION_FIELD", "parent non-underlying product id", "MEDIUM"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "ods_invest_position.asset_type", "FILTER_FIELD", "asset_type in ('FUND','AM_PRODUCT','TRUST_PLAN','SPV')", "MEDIUM"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "crms_counterparty.counterparty_id", "SOURCE_FIELD", "manager or issuer reference", "MEDIUM"),
    ("G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "crms_counterparty.institution_type", "FILTER_FIELD", "institution_type in asset_manager_types", "MEDIUM"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "rpt_g31_part_i.post_lookthrough_balance", "REPORT_FIELD", "direct_mapping", "HIGH"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "dm_g31_position.position_balance", "SOURCE_FIELD", "direct_bond_balance", "HIGH"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "dm_g31_lookthrough.underlying_balance", "SOURCE_FIELD", "underlying_bond_balance", "HIGH"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "dm_g31_lookthrough.indirect_balance", "SOURCE_FIELD", "indirect_bond_balance", "HIGH"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "ods_invest_position.book_balance", "SOURCE_FIELD", "sum direct bond book_balance", "MEDIUM"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "ods_invest_position.asset_type", "FILTER_FIELD", "direct asset_type='BOND' or underlying_asset_type='BOND'", "MEDIUM"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "ods_invest_position.product_id", "DIMENSION_FIELD", "trace parent product", "MEDIUM"),
    ("G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "crms_large_exposure.exposure_amount", "SOURCE_FIELD", "large exposure reconciliation reference", "MEDIUM"),
]


def main() -> None:
    with Session(engine) as session:
        system_by_code = upsert_systems(session)
        field_by_code = upsert_fields(session, system_by_code)
        inserted, skipped, missing_items = upsert_lineage(session, field_by_code)
        session.commit()
    print(
        "seed_g31_lineage_reference completed: "
        f"systems={len(DATA_SYSTEMS)}, fields={len(DATA_FIELDS)}, "
        f"lineage_inserted={inserted}, lineage_existing={skipped}, "
        f"missing_items={missing_items}"
    )


def upsert_systems(session: Session) -> dict[str, DataSystemCatalog]:
    system_by_code: dict[str, DataSystemCatalog] = {}
    for row in DATA_SYSTEMS:
        system = session.exec(
            select(DataSystemCatalog).where(DataSystemCatalog.system_code == row["system_code"])
        ).first()
        if system is None:
            system = DataSystemCatalog(**row)
            session.add(system)
            session.flush()
        else:
            for key, value in row.items():
                setattr(system, key, value)
            session.add(system)
            session.flush()
        system_by_code[system.system_code] = system
    return system_by_code


def upsert_fields(
    session: Session,
    system_by_code: dict[str, DataSystemCatalog],
) -> dict[str, DataFieldCatalog]:
    field_by_code: dict[str, DataFieldCatalog] = {}
    for system_code, field_code, field_name, table_name, column_name, data_type, meaning in DATA_FIELDS:
        system = system_by_code[system_code]
        field = session.exec(
            select(DataFieldCatalog).where(DataFieldCatalog.field_code == field_code)
        ).first()
        payload = {
            "data_system_id": system.id,
            "field_code": field_code,
            "field_name": field_name,
            "table_name": table_name,
            "column_name": column_name,
            "data_type": data_type,
            "business_meaning": meaning,
            "owner_team": system.owner_team,
            "sensitive_level": "INTERNAL",
            "status": "ACTIVE",
        }
        if field is None:
            field = DataFieldCatalog(**payload)
        else:
            for key, value in payload.items():
                setattr(field, key, value)
        session.add(field)
        session.flush()
        field_by_code[field.field_code] = field
    return field_by_code


def upsert_lineage(
    session: Session,
    field_by_code: dict[str, DataFieldCatalog],
) -> tuple[int, int, int]:
    inserted = 0
    skipped = 0
    missing_items = 0
    for item_code, field_code, role, expression, confidence in LINEAGE:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        field = field_by_code[field_code]
        if item is None or item.id is None or field.id is None:
            missing_items += 1
            continue

        existing = session.exec(
            select(ReportingItemLineage).where(
                ReportingItemLineage.reporting_item_id == item.id,
                ReportingItemLineage.data_field_id == field.id,
                ReportingItemLineage.lineage_role == role,
            )
        ).first()
        payload = {
            "reporting_item_id": item.id,
            "data_field_id": field.id,
            "lineage_role": role,
            "transform_expression": expression,
            "confidence_level": confidence,
            "mapping_status": "DRAFT",
            "evidence": "模拟生成的G31血缘参考数据，绑定当前Excel解析item_code",
            "owner_team": field.owner_team,
        }
        if existing is None:
            session.add(ReportingItemLineage(**payload))
            inserted += 1
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            session.add(existing)
            skipped += 1
    return inserted, skipped, missing_items


if __name__ == "__main__":
    main()
