"""字段级 G31 修订对照表 mock 常量模块。

8 条记录覆盖 NEW / MODIFY / DELETE 三种 change_type 和 6+ 种 change_dimension。
本模块不再写 DB（之前依赖的 RegulatoryRevision 表已删）。

用途：
  - export_g31_revisions_to_xlsx.py 导出 Excel
  - 单元测试构造 mock 输入

按 field_code 反查 cell 的辅助函数 expand_cells_for_field 仍保留，供调用方在需要时
通过 reg_reporting_items 表算 affected_cells。
"""
from __future__ import annotations

from sqlmodel import Session, select

from app.models.db_models import RegReportingItem


REGIME = {
    "regime_version": "1104-2026Q1-v2",
    "reporting_system_code": "1104",
    "version_name": "2026 年第 14 号公告·1104 资金同业指标口径修订",
    "effective_date": "2026-06-30",
    "publish_date": "2026-03-15",
    "source_zip_name": "1104-2026Q1-v2.zip",
    "affected_report_codes": ["G31", "G24"],
    "status": "DRAFT",
    "notes": "mock 数据，演示字段级修订对照表",
}


# 8 条 G31 字段维度修订
REVISIONS = [
    {
        "revision_id": "REV-1104-2026Q1-G31-001",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "modified_duration",
        "field_name": "修正久期",
        "change_type": "NEW",
        "change_dimensions": ["口径", "数据类型", "校验规则"],
        "change_summary": "新增 C 列：按账面余额加权计算 Macaulay 久期，单位'年'，取值范围 0–30。",
        "before_value": {},
        "after_value": {
            "口径": "对每只债券计算 Macaulay 久期后按账面余额加权",
            "数据类型": "DECIMAL(10,4)",
            "单位": "年",
            "校验规则": "≥0 且 ≤30",
        },
        "regulation_evidence": "2026 年第 14 号公告 §3.2：新增 C 列修正久期，用于量化债券市场价值波动风险，仅适用于债券类投资。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.2",
        "confidence_level": "HIGH",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-002",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "indirect_holding_balance",
        "field_name": "因持有非底层资产间接持有期末余额",
        "change_type": "MODIFY",
        "change_dimensions": ["口径", "校验规则"],
        "change_summary": "穿透口径扩展：新增资管产品、信托计划、SPV 计入间接持有；校验规则保持 A+D=E。",
        "before_value": {
            "口径": "穿透统计仅含直接持有 ABS",
            "校验规则": "A + D = E",
        },
        "after_value": {
            "口径": "穿透统计含 ABS + 资管产品 + 信托计划 + SPV",
            "校验规则": "A + D = E（保持不变，仅口径扩展）",
        },
        "regulation_evidence": "2026 年第 14 号公告 §3.4：调整 D 列穿透统计口径，新增资管产品和 SPV 的间接持有计入。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.4",
        "confidence_level": "HIGH",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-003",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "post_lookthrough_balance",
        "field_name": "穿透后期末余额",
        "change_type": "MODIFY",
        "change_dimensions": ["口径", "单位"],
        "change_summary": "单位从「元」改为「万元」，且要求多层穿透至最终底层资产。",
        "before_value": {"口径": "穿透 1 层", "单位": "元"},
        "after_value": {"口径": "穿透至底层资产（多层穿透）", "单位": "万元"},
        "regulation_evidence": "2026 年第 14 号公告 §3.5：E 列单位调整为万元，并要求多层穿透至最终底层资产。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.5",
        "confidence_level": "HIGH",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-004",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "investment_income_ytd",
        "field_name": "投资收入年初至报告期末数",
        "change_type": "MODIFY",
        "change_dimensions": ["口径", "数据来源系统"],
        "change_summary": "口径从「已实现收益」扩展到「已实现收益 + 公允价值变动」，需新增估值系统作为数据源。",
        "before_value": {"口径": "含已实现收益", "数据来源系统": "投资管理系统"},
        "after_value": {
            "口径": "含已实现收益 + 公允价值变动",
            "数据来源系统": "投资管理系统 + 估值系统",
        },
        "regulation_evidence": "2026 年第 14 号公告 §3.3：B 列投资收入口径扩展，需纳入估值变动损益。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.3",
        "confidence_level": "MEDIUM",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-005",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "pre_lookthrough_balance",
        "field_name": "穿透前期末余额",
        "change_type": "MODIFY",
        "change_dimensions": ["填报说明"],
        "change_summary": "填报说明明确：账面价值口径含已计提应收利息。",
        "before_value": {"填报说明": "按账面价值口径"},
        "after_value": {"填报说明": "按账面价值口径，含已计提应收利息"},
        "regulation_evidence": "2026 年第 14 号公告 §3.1：A 列填报说明明确包含应收利息。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.1",
        "confidence_level": "HIGH",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-006",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "issuer_type",
        "field_name": "发行人类型",
        "change_type": "MODIFY",
        "change_dimensions": ["枚举值"],
        "change_summary": "枚举值细化：境外机构拆为「境外金融机构 / 境外非金融企业」；新增国际组织、中央政府、地方政府。",
        "before_value": {
            "枚举值": ["境内银行", "境内非银金融机构", "境内非金融企业", "境外机构", "其他"],
        },
        "after_value": {
            "枚举值": [
                "境内银行", "境内非银金融机构", "境内非金融企业",
                "境外金融机构", "境外非金融企业", "国际组织",
                "中央政府", "地方政府", "其他",
            ],
        },
        "regulation_evidence": "2026 年第 14 号公告 §3.6：发行人类型枚举细化，区分境外金融机构与非金融企业。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.6",
        "confidence_level": "HIGH",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-007",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "bill_investment_balance",
        "field_name": "票据投资余额",
        "change_type": "NEW",
        "change_dimensions": ["口径", "归集范围"],
        "change_summary": "新增字段：银行承兑汇票 + 商业承兑汇票（不含贴现），不再计入债券投资余额，单独列示。",
        "before_value": {},
        "after_value": {
            "口径": "银行承兑汇票 + 商业承兑汇票，不含贴现",
            "归集范围": "持有至到期的票据",
        },
        "regulation_evidence": "2026 年第 14 号公告 §3.7：新增票据投资单列，不纳入债券投资余额。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.7",
        "confidence_level": "MEDIUM",
    },
    {
        "revision_id": "REV-1104-2026Q1-G31-008",
        "report_code": "G31",
        "section_code": "PART_I",
        "field_code": "preferred_stock_balance",
        "field_name": "优先股投资余额",
        "change_type": "DELETE",
        "change_dimensions": ["归集范围"],
        "change_summary": "从 G31 移出：优先股不再计入债券投资余额，迁移至权益类投资明细表。",
        "before_value": {"归集范围": "纳入债券投资余额"},
        "after_value": {"归集范围": "迁移至权益类投资明细表"},
        "regulation_evidence": "2026 年第 14 号公告 §3.8：优先股不再计入 G31 债券投资余额，移至股权投资表。",
        "evidence_source_ref": "1104-2026Q1-v2/filing.pdf#§3.8",
        "confidence_level": "HIGH",
    },
]


def expand_cells_for_field(session: Session, report_code: str, field_code: str) -> list[str]:
    """按 field_code 关键字查 reg_reporting_items.column_label / item_name 命中的 cell。

    导出 Excel / 自动展开 affected_cells 时使用。
    """
    keyword_map = {
        "modified_duration": "修正久期",
        "indirect_holding_balance": "因持有非底层",
        "post_lookthrough_balance": "穿透后",
        "pre_lookthrough_balance": "穿透前",
        "investment_income_ytd": "投资收入",
        "issuer_type": "发行人",
        "bill_investment_balance": "票据",
        "preferred_stock_balance": "优先股",
    }
    kw = keyword_map.get(field_code, field_code.split("_")[0])
    rows = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code.like(f"{report_code}.%"))
    ).all()
    return [
        r.item_code for r in rows
        if (r.column_label and kw in r.column_label) or (r.item_name and kw in r.item_name)
    ]
