"""影响范围复核 baseline 按真实 system_code 分桶的单元测试。

旧实现把所有非 REPORT_FIELD 的字段一刀切到 SOURCE_SYSTEM 桶，把所有
REPORT/DERIVED/MAPPING 一刀切到 DATA_MART_ETL 桶。这丢失了：
  - 同样是"source"，估值系统 (VALUATION) 和投资 ODS 应该分别成桶；
  - 同样是"report mart"，1104 报送集市和 DM 主题层是不同 owner_team，
    应分别成单。

这里的测试驱动新逻辑：build_baseline 完全依赖
impact.impacted_source_field_details[].system_code/system_name 来分桶。
"""
from app.models.enums import RiskLevel
from app.models.schemas import ReportingImpactItemRead
from app.services.impact_review_service import (
    build_baseline_from_impacts,
    selected_fields_by_system,
)


def _modified_duration_impact() -> ReportingImpactItemRead:
    """C·修正久期 的影响项，含 6 条 source-level + 1 条 report-level lineage。

    跨 4 个真实系统：RPT_1104 / DM_INVESTMENT / VALUATION / ODS_INVEST。
    """
    return ReportingImpactItemRead(
        reporting_item_code="G31.PART_I.1_0.C_修正久期",
        impact_type="INDICATOR_SCOPE",
        impacted_reporting_field="rpt_g31_part_i.modified_duration",
        impacted_source_fields=[
            "dm_g31_risk.modified_duration",
            "valuation_bond_metric.modified_duration",
            "valuation_bond_price.full_price",
            "ods_invest_position.book_balance",
            "ods_invest_position.security_id",
            "ods_invest_position.asset_type",
        ],
        impacted_lineage_roles=[
            "SOURCE_FIELD",
            "SOURCE_FIELD",
            "SOURCE_FIELD",
            "SOURCE_FIELD",
            "DIMENSION_FIELD",
            "FILTER_FIELD",
        ],
        impacted_source_field_details=[
            {
                "code": "rpt_g31_part_i.modified_duration",
                "name": "G31修正久期",
                "role": "REPORT_FIELD",
                "system_code": "RPT_1104",
                "system_name": "1104报送集市",
                "system_type": "REPORTING",
                "owner_team": "监管报送团队",
            },
            {
                "code": "dm_g31_risk.modified_duration",
                "name": "修正久期",
                "role": "SOURCE_FIELD",
                "system_code": "DM_INVESTMENT",
                "system_name": "投资业务数据主题层",
                "system_type": "DM",
                "owner_team": "金融市场数据团队",
            },
            {
                "code": "valuation_bond_metric.modified_duration",
                "name": "债券修正久期",
                "role": "SOURCE_FIELD",
                "system_code": "VALUATION",
                "system_name": "估值计量系统",
                "system_type": "SOURCE",
                "owner_team": "估值核算团队",
            },
            {
                "code": "valuation_bond_price.full_price",
                "name": "债券全价",
                "role": "SOURCE_FIELD",
                "system_code": "VALUATION",
                "system_name": "估值计量系统",
                "system_type": "SOURCE",
                "owner_team": "估值核算团队",
            },
            {
                "code": "ods_invest_position.book_balance",
                "name": "投资账面余额",
                "role": "SOURCE_FIELD",
                "system_code": "ODS_INVEST",
                "system_name": "投资交易ODS",
                "system_type": "ODS",
                "owner_team": "投资系统团队",
            },
            {
                "code": "ods_invest_position.security_id",
                "name": "证券代码",
                "role": "DIMENSION_FIELD",
                "system_code": "ODS_INVEST",
                "system_name": "投资交易ODS",
                "system_type": "ODS",
                "owner_team": "投资系统团队",
            },
            {
                "code": "ods_invest_position.asset_type",
                "name": "投资资产类型",
                "role": "FILTER_FIELD",
                "system_code": "ODS_INVEST",
                "system_name": "投资交易ODS",
                "system_type": "ODS",
                "owner_team": "投资系统团队",
            },
        ],
        impact_reason="C·修正久期发生 INDICATOR_ADD",
        recommended_action="复核报送字段、主题指标、估值源",
        risk_level=RiskLevel.MEDIUM,
    )


def test_baseline_buckets_by_real_system_code():
    """每个真实 system_code 应该独立成桶，不再塌成 DATA_MART_ETL/SOURCE_SYSTEM。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    assert baseline["version"] == "v1"
    assert len(baseline["items"]) == 1

    item = baseline["items"][0]
    bucket_codes = {system["responsible_system"] for system in item["systems"]}
    assert bucket_codes == {"RPT_1104", "DM_INVESTMENT", "VALUATION", "ODS_INVEST"}


def test_baseline_bucket_label_uses_system_name():
    """每个桶的显示名应该是 system_name，而不是抽象团队角色名。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    labels_by_code = {
        system["responsible_system"]: system["responsible_system_zh"]
        for system in baseline["items"][0]["systems"]
    }
    assert labels_by_code == {
        "RPT_1104": "1104报送集市",
        "DM_INVESTMENT": "投资业务数据主题层",
        "VALUATION": "估值计量系统",
        "ODS_INVEST": "投资交易ODS",
    }


def test_baseline_report_field_lands_in_rpt_1104_bucket():
    """REPORT_FIELD (rpt_g31_part_i.modified_duration) 应该落进 RPT_1104 桶，
    而不是和 DM 字段混在一起。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    rpt_bucket = next(
        system
        for system in baseline["items"][0]["systems"]
        if system["responsible_system"] == "RPT_1104"
    )
    rpt_codes = [field["field_code"] for field in rpt_bucket["fields"]]
    assert rpt_codes == ["rpt_g31_part_i.modified_duration"]
    assert rpt_bucket["fields"][0]["lineage_role"] == "REPORT_FIELD"
    assert rpt_bucket["fields"][0]["is_required"] is True


def test_baseline_valuation_bucket_has_two_source_fields():
    """估值系统该有 2 条 SOURCE_FIELD（modified_duration + full_price）。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    valuation_bucket = next(
        system
        for system in baseline["items"][0]["systems"]
        if system["responsible_system"] == "VALUATION"
    )
    valuation_codes = {field["field_code"] for field in valuation_bucket["fields"]}
    assert valuation_codes == {
        "valuation_bond_metric.modified_duration",
        "valuation_bond_price.full_price",
    }


def test_baseline_ods_bucket_preserves_lineage_roles():
    """ODS 桶里 3 条字段保留各自的 role（SOURCE/DIMENSION/FILTER），
    而不是被统一打成 SOURCE_FIELD。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    ods_bucket = next(
        system
        for system in baseline["items"][0]["systems"]
        if system["responsible_system"] == "ODS_INVEST"
    )
    roles_by_code = {field["field_code"]: field["lineage_role"] for field in ods_bucket["fields"]}
    assert roles_by_code == {
        "ods_invest_position.book_balance": "SOURCE_FIELD",
        "ods_invest_position.security_id": "DIMENSION_FIELD",
        "ods_invest_position.asset_type": "FILTER_FIELD",
    }


def test_baseline_bucket_carries_system_metadata():
    """桶里要带 system_type 和 owner_team，下游 routes_tasks 用它们推 action_type 和 owner。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    by_code = {system["responsible_system"]: system for system in baseline["items"][0]["systems"]}
    assert by_code["VALUATION"]["system_type"] == "SOURCE"
    assert by_code["VALUATION"]["owner_team"] == "估值核算团队"
    assert by_code["DM_INVESTMENT"]["system_type"] == "DM"
    assert by_code["RPT_1104"]["system_type"] == "REPORTING"


def test_selected_fields_by_system_groups_by_system_code():
    """confirm 阶段拉出来的分组也按 system_code，要带上 system_type/owner_team 给工单。"""
    baseline = build_baseline_from_impacts([_modified_duration_impact()])
    grouped = selected_fields_by_system(baseline)
    assert set(grouped.keys()) == {"RPT_1104", "DM_INVESTMENT", "VALUATION", "ODS_INVEST"}
    valuation_group = grouped["VALUATION"]
    assert valuation_group["responsible_system"] == "VALUATION"
    assert valuation_group["responsible_system_zh"] == "估值计量系统"
    assert valuation_group["system_type"] == "SOURCE"
    assert valuation_group["owner_team"] == "估值核算团队"
    assert len(valuation_group["items"]) == 1
    assert len(valuation_group["items"][0]["fields"]) == 2


def test_baseline_falls_back_when_details_missing_system_code():
    """旧 impact 记录（没跑过新影响分析）detail 里没有 system_code，
    应该走 UNKNOWN 桶而不是崩溃，方便用户对相关 task reset_to_baseline。"""
    legacy_impact = ReportingImpactItemRead(
        reporting_item_code="G99.LEGACY",
        impact_type="INDICATOR_SCOPE",
        impacted_reporting_field="rpt_g99.legacy_field",
        impacted_source_fields=["src.legacy_field"],
        impacted_lineage_roles=["SOURCE_FIELD"],
        impacted_source_field_details=[],  # 旧数据：明细缺失
        impact_reason="",
        recommended_action="",
        risk_level=RiskLevel.LOW,
    )
    baseline = build_baseline_from_impacts([legacy_impact])
    item = baseline["items"][0]
    bucket_codes = {system["responsible_system"] for system in item["systems"]}
    assert bucket_codes == {"UNKNOWN"}
    unknown = item["systems"][0]
    assert unknown["responsible_system_zh"] == "系统待确认"
    field_codes = {field["field_code"] for field in unknown["fields"]}
    assert field_codes == {"rpt_g99.legacy_field", "src.legacy_field"}
