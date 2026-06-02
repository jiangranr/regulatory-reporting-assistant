"""路线 A 一键引导脚本：让 G31 D 列血缘图从真实库读出来。

执行步骤：
  1. init_db()                              建/补全所有表（含三张血缘表）
  2. _upsert_seed_catalog(build_1104_seed_catalog())
                                            灌 1104 基础目录（含 G31 报表对象 + PART_I section）
  3. _ensure_g31_detail_items(session)      补齐 5 个 G31 PART_I.1_0.* 详细 item（A/B/C/D/E）
                                            —— 这些原本来源于 Excel 解析，bootstrap 里用代码兜底
  4. seed_g31_lineage_reference.main()      灌 G31 参考血缘
  5. seed_g01_iv_lineage_reference.main()   对已导入的 G01_IV 重点指标灌参考血缘
  6. 打印 G31 D 列实际命中情况

幂等：可重复运行。
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.core.database import engine, init_db
from app.models.db_models import (
    DataFieldCatalog,
    DataSystemCatalog,
    RegReportingItem,
    RegReportingObject,
    RegReportingSection,
    ReportingItemLineage,
)
from app.api.routes_reporting import _upsert_seed_catalog
from app.services.reporting_seed import build_1104_seed_catalog
from scripts import seed_g01_iv_lineage_reference as g01_seed
from scripts import seed_g31_lineage_reference as g31_seed


# 5 个 G31 详细 item，对应报表第 1 行 A/B/C/D/E 列
# item_code 与 seed_g31_lineage_reference.LINEAGE 里的 item_code 完全一致
G31_DETAIL_ITEMS = [
    {
        "item_code": "G31.PART_I.1_0.A_穿透前_期末余额",
        "item_name": "1 行·A 列 · 穿透前·期末余额",
        "row_label": "1.债券投资合计",
        "column_label": "A·穿透前·期末余额",
        "source_cell_ref": "C5",
    },
    {
        "item_code": "G31.PART_I.1_0.B_投资收入_年初至报告期末数",
        "item_name": "1 行·B 列 · 投资收入·年初至报告期末数",
        "row_label": "1.债券投资合计",
        "column_label": "B·投资收入·年初至报告期末数",
        "source_cell_ref": "D5",
    },
    {
        "item_code": "G31.PART_I.1_0.C_修正久期",
        "item_name": "1 行·C 列 · 修正久期",
        "row_label": "1.债券投资合计",
        "column_label": "C·修正久期",
        "source_cell_ref": "E5",
    },
    {
        "item_code": "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额",
        "item_name": "1 行·D 列 · 因持有非底层资产而间接持有·期末余额",
        "row_label": "1.债券投资合计",
        "column_label": "D·因持有非底层资产而间接持有·期末余额",
        "source_cell_ref": "F5",
    },
    {
        "item_code": "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额",
        "item_name": "1 行·E 列 · 穿透后·期末余额（单位：万元）",
        "row_label": "1.债券投资合计",
        "column_label": "E·穿透后·期末余额",
        "source_cell_ref": "G5",
    },
]


def _ensure_g31_detail_items(session: Session) -> tuple[int, int]:
    """补齐 5 个 G31 详细 item。返回 (inserted, existing)。"""
    obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == "G31")
    ).first()
    if obj is None or obj.id is None:
        raise RuntimeError("缺少 G31 报送对象，请先确认 build_1104_seed_catalog 已运行。")

    section = session.exec(
        select(RegReportingSection).where(
            RegReportingSection.reporting_object_id == obj.id,
            RegReportingSection.section_code == "PART_I",
        )
    ).first()
    if section is None or section.id is None:
        raise RuntimeError("缺少 G31 PART_I section。")

    inserted = 0
    existing = 0
    for row in G31_DETAIL_ITEMS:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == row["item_code"])
        ).first()
        payload = {
            "reporting_object_id": obj.id,
            "reporting_section_id": section.id,
            "item_code": row["item_code"],
            "item_name": row["item_name"],
            "item_type": "INDICATOR",
            "row_label": row["row_label"],
            "column_label": row["column_label"],
            "measure_type": "余额",
            "unit": "万元",
            "status": "ACTIVE",
            "change_status": "UNCHANGED",
            "source_cell_ref": row["source_cell_ref"],
            "cell_role": "FILLABLE",
            "is_fillable": True,
            "is_derived": False,
            "data_type": "DECIMAL",
        }
        if item is None:
            session.add(RegReportingItem(**payload))
            inserted += 1
        else:
            for k, v in payload.items():
                setattr(item, k, v)
            session.add(item)
            existing += 1
    session.flush()
    return inserted, existing


def _print_d_column_lineage(session: Session) -> None:
    d_code = "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额"
    item = session.exec(
        select(RegReportingItem).where(RegReportingItem.item_code == d_code)
    ).first()
    if item is None or item.id is None:
        print(f"[verify] 未找到 D 列 item: {d_code}")
        return

    rows = session.exec(
        select(ReportingItemLineage, DataFieldCatalog, DataSystemCatalog)
        .where(ReportingItemLineage.reporting_item_id == item.id)
        .join(DataFieldCatalog, DataFieldCatalog.id == ReportingItemLineage.data_field_id)
        .join(DataSystemCatalog, DataSystemCatalog.id == DataFieldCatalog.data_system_id)
    ).all()

    print(f"\n[verify] D 列 ({d_code}) 实际命中血缘 {len(rows)} 条：")
    for lineage, field, system in rows:
        print(
            f"  [{lineage.lineage_role:<16}] "
            f"{system.system_code:<14} {field.table_name}.{field.column_name:<28} "
            f"-> {field.field_name}   "
            f"({lineage.transform_expression})"
        )


def main() -> None:
    print("[1/5] init_db: 建表 / 补列 ...")
    init_db()

    print("[2/5] 灌 1104 基础目录 ...")
    with Session(engine) as session:
        catalog = build_1104_seed_catalog()
        _upsert_seed_catalog(session, catalog)
        session.commit()

    print("[3/5] 补齐 5 个 G31 详细 item ...")
    with Session(engine) as session:
        inserted, existing = _ensure_g31_detail_items(session)
        session.commit()
        print(f"        新增 {inserted} 条，更新 {existing} 条")

    print("[4/5] 灌 G31 字段目录 + 血缘 ...")
    g31_seed.main()

    print("[5/5] 灌 G01_IV 互联网个人存款重点指标参考血缘 ...")
    g01_seed.main()

    with Session(engine) as session:
        _print_d_column_lineage(session)


if __name__ == "__main__":
    main()
