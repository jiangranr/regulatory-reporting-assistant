"""
G31 指标变更状态精准打标脚本 (251 版 → 基于业务知识注释)

背景：
  catalog_ingestor 只要是新入库的 item 就统一打 change_status="NEW"，
  不代表指标在此版本真的是新增的。本脚本用已知的版本变更知识做精准覆盖：

  列 C（修正久期）:     NEW      —— 2025年251版新增，用于量化债券市场价值波动风险
  列 D（间接持有余额）:  MODIFIED —— 原有但穿透统计口径在251版有调整
  列 E（穿透后余额）:    MODIFIED —— 原有但穿透统计口径在251版有调整
  列 A（穿透前余额）:    UNCHANGED
  列 B（投资收入）:      UNCHANGED
  噪声行/列:            is_fillable=False（不计入变更分析）

数据来源：
  《关于做好 2025 年银行业非现场监管报表填报工作的通知》金发〔2024〕39号
  附件4：报表表样和填报说明汇总 / G31(251).xls
  公开行业解读资料（2025年1104修订）

可重复运行：幂等，不删除数据。
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine
from app.models.db_models import RegReportingItem, RegReportingObject

# ── 列识别规则 ────────────────────────────────────────────────────────────────
# item_code 后缀  →  (change_status, is_meaningful)
_COL_RULES: list[tuple[str, str, bool]] = [
    # 已确认新增列
    ("C_修正久期",                       "NEW",       True),
    # 已确认原有、但251版口径有调整
    ("D_因持有非底层资产而间接持有",        "MODIFIED",  True),
    ("穿透后_期末余额",                    "MODIFIED",  True),
    # 原有列、无变化
    ("A_穿透前_期末余额",                  "UNCHANGED", True),
    ("B_投资收入_年初至报告期末数",         "UNCHANGED", True),
]

# column_label 包含这些关键字的 → 视为噪声（非数据格）
_NOISE_COLUMN_FRAGMENTS = [
    "填报机构",
    "报表日期",
    "COL_",
    "版本号",
    "填表人",
    "复核人",
    "无数据",
    "紫色底",
]


def _classify_item(item: RegReportingItem) -> tuple[str | None, bool]:
    """返回 (change_status, is_meaningful)；None 表示不做修改。"""
    code = item.item_code or ""
    col_label = item.column_label or ""

    # 噪声检测
    if any(frag in col_label for frag in _NOISE_COLUMN_FRAGMENTS):
        return None, False  # change_status 不变，但标记为非可填写

    if any(col_label == frag for frag in ("COL_1", "COL_8")):
        return None, False

    # 按 item_code 后缀匹配
    for suffix, status, meaningful in _COL_RULES:
        if suffix in code:
            return status, meaningful

    return None, True  # 未命中规则，保持原值


def main() -> None:
    with Session(engine) as session:
        obj = session.exec(
            select(RegReportingObject).where(RegReportingObject.object_code == "G31")
        ).first()
        if obj is None:
            print("未找到 G31 报表对象，请先运行 reporting_seed 或 catalog 导入。")
            return

        items = session.exec(
            select(RegReportingItem).where(
                RegReportingItem.reporting_object_id == obj.id
            )
        ).all()

        stats: dict[str, int] = {
            "NEW": 0, "MODIFIED": 0, "UNCHANGED": 0,
            "noise_hidden": 0, "skipped": 0,
        }

        for item in items:
            new_status, is_meaningful = _classify_item(item)

            changed = False

            if not is_meaningful and item.is_fillable:
                item.is_fillable = False
                stats["noise_hidden"] += 1
                changed = True

            if new_status is not None and item.change_status != new_status:
                item.change_status = new_status
                stats[new_status] = stats.get(new_status, 0) + 1
                changed = True
            elif new_status is None and is_meaningful:
                stats["skipped"] += 1

            if changed:
                session.add(item)

        session.commit()

    print("G31 change_status 打标完成：")
    print(f"  NEW      (修正久期列，2025新增)     : {stats['NEW']}")
    print(f"  MODIFIED (穿透D/E列，口径调整)      : {stats['MODIFIED']}")
    print(f"  UNCHANGED (A/B列，无变化)           : {stats['UNCHANGED']}")
    print(f"  噪声格标记为不可填写                 : {stats['noise_hidden']}")
    print(f"  未命中规则跳过                       : {stats['skipped']}")


if __name__ == "__main__":
    main()
