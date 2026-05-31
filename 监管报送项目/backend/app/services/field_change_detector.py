"""field_change_detector.py

字段目录版本对比服务。

生产环境：从监管系统拉取新版字段目录，与 DB 中现有指标做 diff。
Demo 环境：使用内置 mock 新版字段目录，模拟真实变更场景。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.db_models import RegReportingItem, ReportingItemLineage


# ──────────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FieldChange:
    reporting_object_code: str
    reporting_item_code: str
    item_name: str
    change_type: str              # ADDED / DELETED / MODIFIED
    before_snapshot: dict
    after_snapshot: dict
    library_hit: bool = False     # 是否命中 reporting_item_lineage（检测后填充）


# ──────────────────────────────────────────────────────────────────────────────
# Demo 用 mock 新版字段目录
# ──────────────────────────────────────────────────────────────────────────────

# 格式：{item_code: {name, definition, unit, frequency}}
_MOCK_NEW_VERSION: dict[str, dict] = {
    # G31 现有指标（保留，definition 有细微变化）
    "G31.PART_I.BOND_INVESTMENT_BALANCE": {
        "name": "债券投资余额",
        "definition": (
            "填报机构持有的全部债券投资期末账面余额。"
            "本期起，委托管理债券需在第II部分单独填报，"
            "不再并入本行合计，口径较上期收窄。"
        ),
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G31",
    },
    # G31 本期新增：绿色债券投资余额（无历史血缘）
    "G31.PART_I.GREEN_BOND_BALANCE": {
        "name": "绿色债券投资余额",
        "definition": (
            "填报机构持有的、经监管认定符合绿色金融标准的债券投资期末余额。"
            "包括绿色金融债、绿色公司债、绿色资产支持证券等。"
        ),
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G31",
    },
    # G31 本期新增：ESG 私募基金投资余额（无历史血缘）
    "G31.PART_II.PRIVATE_FUND_ESG_BALANCE": {
        "name": "ESG 策略私募基金投资余额",
        "definition": (
            "填报机构持有的、采用 ESG（环境、社会、治理）投资策略的私募基金期末余额，"
            "含股权型、混合型和债券型私募 ESG 基金。"
        ),
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G31",
    },
}

# 当前版本（DB 中已有的指标，作为"before"基准）
_CURRENT_VERSION_ITEMS = {
    "G31.PART_I.BOND_INVESTMENT_BALANCE": {
        "name": "债券投资余额",
        "definition": "填报机构持有的全部债券投资（含自主管理和委托管理）期末账面余额。",
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G31",
    },
    # G24/G21/G25/G27 现有项目（新版中保持不变，不产生 diff）
    "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100": {
        "name": "最大百家金融机构同业融入余额",
        "definition": "向最大百家金融机构同业融入资金的期末余额。",
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G24",
    },
    "G21.MAIN.LIQUIDITY_GAP_30D": {
        "name": "30 日内流动性期限缺口",
        "definition": "未来 30 日内的流动性期限缺口金额（负数为缺口）。",
        "unit": "万元",
        "frequency": "月报",
        "object_code": "G21",
    },
    "G25.PART_I.HQLA_BALANCE": {
        "name": "合格优质流动性资产余额",
        "definition": "符合监管要求的优质流动性资产期末余额，按 L1/L2A/L2B 分类填报。",
        "unit": "万元",
        "frequency": "月报",
        "object_code": "G25",
    },
    "G25.PART_I.NET_CASH_OUTFLOW_30D": {
        "name": "未来 30 日现金净流出量",
        "definition": "压力情景下未来 30 日内的净现金流出金额，用于计算流动性覆盖率分母。",
        "unit": "万元",
        "frequency": "月报",
        "object_code": "G25",
    },
    "G27.MAIN.INTERBANK_DEPOSIT_BALANCE": {
        "name": "同业存放余额",
        "definition": "其他金融机构存放在本机构的同业存款期末余额。",
        "unit": "万元",
        "frequency": "季报",
        "object_code": "G27",
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# 核心函数
# ──────────────────────────────────────────────────────────────────────────────

def detect_field_changes(
    object_codes: list[str] | None = None,
) -> list[FieldChange]:
    """对比当前版本与 mock 新版，生成变更清单。

    Args:
        object_codes: 限定检测的报表范围，None 表示全部。

    Returns:
        FieldChange 列表（尚未填充 library_hit，由调用方补充）。
    """
    changes: list[FieldChange] = []

    current = _CURRENT_VERSION_ITEMS
    new_version = _MOCK_NEW_VERSION

    # 过滤报表范围
    if object_codes:
        upper = {c.upper() for c in object_codes}
        current = {k: v for k, v in current.items() if v.get("object_code", "").upper() in upper}
        new_version = {k: v for k, v in new_version.items() if v.get("object_code", "").upper() in upper}

    current_codes = set(current.keys())
    new_codes = set(new_version.keys())

    # 新增
    for code in new_codes - current_codes:
        item = new_version[code]
        changes.append(FieldChange(
            reporting_object_code=item.get("object_code", code.split(".")[0]),
            reporting_item_code=code,
            item_name=item.get("name", ""),
            change_type="ADDED",
            before_snapshot={},
            after_snapshot=item,
        ))

    # 删除
    for code in current_codes - new_codes:
        item = current[code]
        changes.append(FieldChange(
            reporting_object_code=item.get("object_code", code.split(".")[0]),
            reporting_item_code=code,
            item_name=item.get("name", ""),
            change_type="DELETED",
            before_snapshot=item,
            after_snapshot={},
        ))

    # 修改（definition 发生变化）
    for code in current_codes & new_codes:
        old = current[code]
        new = new_version[code]
        if old.get("definition", "") != new.get("definition", ""):
            changes.append(FieldChange(
                reporting_object_code=old.get("object_code", code.split(".")[0]),
                reporting_item_code=code,
                item_name=new.get("name", old.get("name", "")),
                change_type="MODIFIED",
                before_snapshot=old,
                after_snapshot=new,
            ))

    return changes


def enrich_with_library_hit(changes: list[FieldChange], session: Session) -> list[FieldChange]:
    """为每条变更记录填充 library_hit（是否在 ReportingItemLineage 中存在记录）。

    命中 = item_code 在 reg_reporting_items 中存在，且该 item 有至少一条 lineage 记录。
    """
    for change in changes:
        item = session.exec(
            select(RegReportingItem).where(
                RegReportingItem.item_code == change.reporting_item_code
            )
        ).first()
        if item and item.id:
            lineage_exists = session.exec(
                select(ReportingItemLineage).where(
                    ReportingItemLineage.reporting_item_id == item.id
                )
            ).first()
            change.library_hit = lineage_exists is not None
        else:
            change.library_hit = False

    return changes
