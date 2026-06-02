"""Seed reference lineage for G01_IV internet personal deposit indicators.

The mappings are simulated but realistic demo data. They cover the four
internet-deposit focus indicators imported from the G01_IV template and are
idempotent so the script can be rerun after catalog ingestion.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine
from app.models.db_models import (
    DataFieldCatalog,
    DataSystemCatalog,
    RegReportingItem,
    ReportingItemLineage,
)


DATA_SYSTEMS = [
    {
        "system_code": "RPT_1104",
        "system_name": "1104报送集市",
        "system_type": "REPORTING",
        "owner_team": "监管报送团队",
        "description": "1104监管报送最终加工和出表层",
    },
    {
        "system_code": "DM_DEPOSIT",
        "system_name": "存款业务数据主题层",
        "system_type": "DM",
        "owner_team": "存款业务数据团队",
        "description": "存款账户、余额、客户和渠道主题数据",
    },
    {
        "system_code": "ODS_DEPOSIT",
        "system_name": "存款账户ODS",
        "system_type": "ODS",
        "owner_team": "核心系统数据团队",
        "description": "核心存款账户和余额明细落地层",
    },
    {
        "system_code": "CBS",
        "system_name": "核心银行系统",
        "system_type": "SOURCE",
        "owner_team": "核心系统团队",
        "description": "个人存款账户源系统",
    },
]


DATA_FIELDS = [
    ("RPT_1104", "rpt_g01_iv.internet_personal_time_deposit", "互联网个人定期存款", "rpt_g01_iv", "internet_personal_time_deposit", "DECIMAL", "通过互联网吸收的个人定期存款最终报送字段"),
    ("RPT_1104", "rpt_g01_iv.internet_personal_demand_deposit", "互联网个人活期存款", "rpt_g01_iv", "internet_personal_demand_deposit", "DECIMAL", "通过互联网吸收的个人活期存款最终报送字段"),
    ("RPT_1104", "rpt_g01_iv.third_party_personal_time_deposit", "第三方平台个人定期存款", "rpt_g01_iv", "third_party_personal_time_deposit", "DECIMAL", "通过第三方互联网平台吸收的个人定期存款最终报送字段"),
    ("RPT_1104", "rpt_g01_iv.third_party_personal_demand_deposit", "第三方平台个人活期存款", "rpt_g01_iv", "third_party_personal_demand_deposit", "DECIMAL", "通过第三方互联网平台吸收的个人活期存款最终报送字段"),
    ("DM_DEPOSIT", "dm_deposit_account.deposit_balance", "存款账户余额", "dm_deposit_account", "deposit_balance", "DECIMAL", "个人存款账户期末余额"),
    ("ODS_DEPOSIT", "ods_deposit_account.account_balance", "核心存款账户余额", "ods_deposit_account", "account_balance", "DECIMAL", "核心系统存款账户期末余额"),
    ("ODS_DEPOSIT", "ods_deposit_account.customer_type", "客户类型", "ods_deposit_account", "customer_type", "VARCHAR", "个人、企业等客户分类"),
    ("ODS_DEPOSIT", "ods_deposit_account.deposit_type", "存款类型", "ods_deposit_account", "deposit_type", "VARCHAR", "活期、定期等存款产品分类"),
    ("ODS_DEPOSIT", "ods_deposit_account.acquisition_channel", "开户获客渠道", "ods_deposit_account", "acquisition_channel", "VARCHAR", "网点、互联网、第三方互联网平台等渠道"),
    ("ODS_DEPOSIT", "ods_deposit_account.third_party_platform_flag", "第三方平台标识", "ods_deposit_account", "third_party_platform_flag", "VARCHAR", "是否通过第三方互联网平台引流或合作获客"),
    ("CBS", "core_deposit_account.account_id", "存款账号", "core_deposit_account", "account_id", "VARCHAR", "核心系统个人存款账户唯一标识"),
]


# The second candidate for THIRD_PARTY_INTERNET_DEMAND_DEPOSIT is retained for
# compatibility with the currently imported 251 template, whose row code was
# parsed as 11.a.1 even though the business label is the 11.a.2 demand-deposit
# indicator. A corrected future import will bind the first candidate instead.
FOCUS_ITEM_CODES = {
    "INTERNET_TIME_DEPOSIT": [
        "G01_IV.PART_IV.11_1通过互联网吸收的个人定期存款.B_其中_储蓄存款",
    ],
    "INTERNET_DEMAND_DEPOSIT": [
        "G01_IV.PART_IV.11_2通过互联网吸收的个人活期存款.B_其中_储蓄存款",
    ],
    "THIRD_PARTY_INTERNET_TIME_DEPOSIT": [
        "G01_IV.PART_IV.11_a_1通过第三方互联网平台吸收的个人定期存款.B_其中_储蓄存款",
    ],
    "THIRD_PARTY_INTERNET_DEMAND_DEPOSIT": [
        "G01_IV.PART_IV.11_a_2通过第三方互联网平台吸收的个人活期存款.B_其中_储蓄存款",
        "G01_IV.PART_IV.11_a_1通过第三方互联网平台吸收的个人活期存款.B_其中_储蓄存款",
    ],
}


def _rows(
    focus_key: str,
    report_field: str,
    deposit_type: str,
    *,
    third_party: bool = False,
) -> list[tuple[str, str, str, str, str]]:
    rows = [
        (focus_key, report_field, "REPORT_FIELD", "direct_mapping", "HIGH"),
        (focus_key, "dm_deposit_account.deposit_balance", "SOURCE_FIELD", "sum(deposit_balance)", "HIGH"),
        (focus_key, "ods_deposit_account.account_balance", "SOURCE_FIELD", "sum(account_balance)", "HIGH"),
        (focus_key, "core_deposit_account.account_id", "DIMENSION_FIELD", "group by account_id", "MEDIUM"),
        (focus_key, "ods_deposit_account.customer_type", "FILTER_FIELD", "customer_type = 'PERSONAL'", "HIGH"),
        (focus_key, "ods_deposit_account.deposit_type", "FILTER_FIELD", f"deposit_type = '{deposit_type}'", "HIGH"),
        (focus_key, "ods_deposit_account.acquisition_channel", "FILTER_FIELD", "acquisition_channel = 'INTERNET'", "HIGH"),
    ]
    if third_party:
        rows.append(
            (
                focus_key,
                "ods_deposit_account.third_party_platform_flag",
                "FILTER_FIELD",
                "third_party_platform_flag = 'Y'",
                "HIGH",
            )
        )
    return rows


LINEAGE = [
    *_rows("INTERNET_TIME_DEPOSIT", "rpt_g01_iv.internet_personal_time_deposit", "TIME"),
    *_rows("INTERNET_DEMAND_DEPOSIT", "rpt_g01_iv.internet_personal_demand_deposit", "DEMAND"),
    *_rows(
        "THIRD_PARTY_INTERNET_TIME_DEPOSIT",
        "rpt_g01_iv.third_party_personal_time_deposit",
        "TIME",
        third_party=True,
    ),
    *_rows(
        "THIRD_PARTY_INTERNET_DEMAND_DEPOSIT",
        "rpt_g01_iv.third_party_personal_demand_deposit",
        "DEMAND",
        third_party=True,
    ),
]


def main() -> None:
    with Session(engine) as session:
        system_by_code = upsert_systems(session)
        field_by_code = upsert_fields(session, system_by_code)
        inserted, existing, missing_items = upsert_lineage(session, field_by_code)
        session.commit()
    print(
        "seed_g01_iv_lineage_reference completed: "
        f"systems={len(DATA_SYSTEMS)}, fields={len(DATA_FIELDS)}, "
        f"lineage_inserted={inserted}, lineage_existing={existing}, "
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
    existing_count = 0
    missing_items = 0
    for focus_key, field_code, role, expression, confidence in LINEAGE:
        item = _find_focus_item(session, focus_key)
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
            "mapping_status": "SEED_CONFIRMED",
            "evidence": "模拟生成的G01_IV互联网个人存款血缘参考数据",
            "owner_team": field.owner_team,
        }
        if existing is None:
            session.add(ReportingItemLineage(**payload))
            inserted += 1
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            session.add(existing)
            existing_count += 1
    return inserted, existing_count, missing_items


def _find_focus_item(session: Session, focus_key: str) -> RegReportingItem | None:
    for item_code in FOCUS_ITEM_CODES[focus_key]:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        if item is not None:
            return item
    return None


if __name__ == "__main__":
    main()

