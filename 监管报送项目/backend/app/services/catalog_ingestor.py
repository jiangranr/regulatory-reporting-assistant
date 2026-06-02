"""catalog_ingestor.py

编排层：协调 zip_scanner / excel_parser / doc_parser，
管理事务写库并更新 RegCatalogBatch / RegCatalogBatchItem 进度。
"""
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlmodel import Session, select

from app.core.database import engine
from app.models.db_models import (
    RegCatalogBatch,
    RegCatalogBatchItem,
    RegReportingDimension,
    RegReportingDimensionMember,
    RegReportingInstruction,
    RegReportingItem,
    RegReportingItemDimension,
    RegReportingObject,
    RegReportingSection,
    RegReportingSystem,
    RegReportingTemplate,
    RegReportingTemplateCell,
    RegReportingVersion,
)
from app.services import doc_parser, excel_parser, zip_scanner


# ──────────────────────────────────────────────────────────────────────────────
# 公共函数
# ──────────────────────────────────────────────────────────────────────────────

def create_batch(session: Session, zip_filename: str, source_doc_ref: str) -> RegCatalogBatch:
    """创建 PENDING 状态的 batch 记录，立即 commit，返回带 id 的对象。"""
    batch_code = f"BATCH-{uuid.uuid4().hex[:12].upper()}"
    batch = RegCatalogBatch(
        batch_code=batch_code,
        source_zip_filename=zip_filename,
        source_document_ref=source_doc_ref,
        status="PENDING",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


# ──────────────────────────────────────────────────────────────────────────────
# 私有辅助函数
# ──────────────────────────────────────────────────────────────────────────────

def _section_code_for_object_code(object_code: str) -> str:
    """根据报表代码后缀推断章节；无后缀的常规报表默认使用 PART_I。"""
    match = re.search(r"_(I|II|III|IV|V|VI|VII|VIII|IX|X)$", object_code.upper())
    return f"PART_{match.group(1)}" if match else "PART_I"


def _get_or_create_system(session: Session) -> RegReportingSystem:
    """获取或创建 system_code='1104' 的记录。"""
    system = session.exec(
        select(RegReportingSystem).where(RegReportingSystem.system_code == "1104")
    ).first()
    if not system:
        system = RegReportingSystem(
            system_code="1104",
            system_name="1104报表体系",
            regulator="中国人民银行",
            description="金融机构监管数据报送体系（1104）",
        )
        session.add(system)
        session.flush()  # 获取 id，不提交事务
    return system


def _get_or_create_version(
    session: Session, system_id: int, version_label: str
) -> RegReportingVersion:
    """获取或创建 version_code=version_label 的记录。"""
    version = session.exec(
        select(RegReportingVersion).where(
            RegReportingVersion.reporting_system_id == system_id,
            RegReportingVersion.version_code == version_label,
        )
    ).first()
    if not version:
        version = RegReportingVersion(
            reporting_system_id=system_id,
            version_code=version_label,
            version_name=f"1104报表 {version_label} 版",
        )
        session.add(version)
        session.flush()
    return version


def _upsert_reporting_object(
    session: Session,
    object_code: str,
    system_id: int,
    version_id: int,
    change_type: str,
    table_category: str,
    version_label: str,
    batch_item_id: int,
) -> RegReportingObject:
    """更新或创建 reporting object。"""
    rep_obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == object_code)
    ).first()
    if rep_obj:
        rep_obj.reporting_system_id = system_id
        rep_obj.reporting_version_id = version_id
        rep_obj.change_type = change_type
        rep_obj.table_category = table_category
        rep_obj.current_version_label = version_label
        rep_obj.latest_batch_item_id = batch_item_id
        session.add(rep_obj)
        session.flush()
    else:
        rep_obj = RegReportingObject(
            reporting_system_id=system_id,
            reporting_version_id=version_id,
            object_code=object_code,
            object_name=object_code,  # 初始名称用 code，后续可以更新
            change_type=change_type,
            table_category=table_category,
            current_version_label=version_label,
            latest_batch_item_id=batch_item_id,
        )
        session.add(rep_obj)
        session.flush()
    return rep_obj


def _write_excel_results(
    session: Session,
    parse_result: excel_parser.ExcelParseResult,
    object_id: int,
    batch_item_id: int,
    object_code: str,
    version_label: str,
    change_type: str = "NEW",
    section_code: str = "PART_I",
) -> int:
    """
    写 template、template_cells、dimensions、dimension_members、items、item_dimensions。
    返回写入的 item 数量。
    """
    # 1. 查或建 RegReportingSection（用 reporting_object_id 过滤，不传 object_code）
    section = session.exec(
        select(RegReportingSection).where(
            RegReportingSection.reporting_object_id == object_id,
            RegReportingSection.section_code == section_code,
        )
    ).first()
    if not section:
        section = RegReportingSection(
            reporting_object_id=object_id,
            section_code=section_code,
            section_name=section_code.replace("PART_", "第 ") + " 部分",
        )
        session.add(section)
        session.flush()

    # 2. 查或建 RegReportingTemplate
    template_code = f"{object_code}.{section_code}.{version_label}"
    template = session.exec(
        select(RegReportingTemplate).where(
            RegReportingTemplate.template_code == template_code
        )
    ).first()
    if not template:
        template = RegReportingTemplate(
            reporting_object_id=object_id,
            batch_item_id=batch_item_id,
            template_code=template_code,
            template_name=f"{object_code} {section_code} {version_label}",
            version_label=version_label,
        )
        session.add(template)
        session.flush()
    else:
        template.batch_item_id = batch_item_id
        session.add(template)
        session.flush()

    # 3. 批量写 RegReportingTemplateCell（先删旧的，再写新的）
    if parse_result.template_cells:
        session.exec(
            delete(RegReportingTemplateCell).where(
                RegReportingTemplateCell.template_id == template.id
            )
        )
        cells = [
            RegReportingTemplateCell(
                template_id=template.id,
                sheet_name=c.get("sheet_name", ""),
                row_index=c.get("row_index", 0),
                col_index=c.get("col_index", 0),
                excel_ref=c.get("excel_ref", ""),
                raw_text=c.get("raw_text", ""),
                cell_type=c.get("cell_type", ""),
                style_json=c.get("style_json", "{}"),
                merge_json=c.get("merge_json", "{}"),
            )
            for c in parse_result.template_cells
        ]
        session.add_all(cells)
        session.flush()

    # 4. 查或建 ROW 维度和 COL 维度
    row_dim_code = f"{object_code}.{section_code}.ROW"
    col_dim_code = f"{object_code}.{section_code}.COL"

    row_dim = session.exec(
        select(RegReportingDimension).where(
            RegReportingDimension.dimension_code == row_dim_code
        )
    ).first()
    if not row_dim:
        row_dim = RegReportingDimension(
            reporting_object_id=object_id,
            dimension_code=row_dim_code,
            dimension_name=f"{object_code} 行维度",
            axis="ROW",
        )
        session.add(row_dim)
        session.flush()

    col_dim = session.exec(
        select(RegReportingDimension).where(
            RegReportingDimension.dimension_code == col_dim_code
        )
    ).first()
    if not col_dim:
        col_dim = RegReportingDimension(
            reporting_object_id=object_id,
            dimension_code=col_dim_code,
            dimension_name=f"{object_code} 列维度",
            axis="COLUMN",
        )
        session.add(col_dim)
        session.flush()

    # 5. 逐一查或建 RegReportingDimensionMember（按 member_code 去重），维护 member_id_map
    member_id_map: dict[str, int] = {}
    for m in parse_result.dimension_members:
        member_code = m["member_code"]
        existing_member = session.exec(
            select(RegReportingDimensionMember).where(
                RegReportingDimensionMember.member_code == member_code
            )
        ).first()
        if existing_member:
            member_id_map[member_code] = existing_member.id  # type: ignore[assignment]
        else:
            axis = m.get("axis", "ROW")
            dim_id = row_dim.id if axis == "ROW" else col_dim.id
            new_member = RegReportingDimensionMember(
                dimension_id=dim_id,
                member_code=member_code,
                member_name=m.get("member_name", member_code),
                display_order=m.get("display_order", 0),
                source_cell_ref=m.get("source_cell_ref", ""),
            )
            session.add(new_member)
            session.flush()
            member_id_map[member_code] = new_member.id  # type: ignore[assignment]

    # 6. 逐一查或建 RegReportingItem（按 item_code 去重，已存在则 skip）
    items_written = 0
    item_id_map: dict[str, int] = {}

    for item in parse_result.items:
        item_code = item["item_code"]
        existing_item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        if existing_item:
            item_id_map[item_code] = existing_item.id  # type: ignore[assignment]
            continue

        new_item = RegReportingItem(
            reporting_object_id=object_id,
            reporting_section_id=section.id,
            batch_item_id=batch_item_id,
            item_code=item_code,
            item_name=item.get("item_name", item_code),
            item_type=item.get("item_type", "MEASURE"),
            row_label=item.get("row_label", ""),
            column_label=item.get("column_label", ""),
            source_cell_ref=item.get("source_cell_ref", ""),
            cell_role=item.get("cell_role", ""),
            is_fillable=item.get("is_fillable", True),
            is_derived=item.get("is_derived", False),
            data_type=item.get("data_type", "DECIMAL"),
            # NEW 报表：全部指标视为新增；MODIFIED 报表：等待扫描引擎精确打标
            change_status="NEW" if change_type == "NEW" else "UNKNOWN",
        )
        session.add(new_item)
        session.flush()
        item_id_map[item_code] = new_item.id  # type: ignore[assignment]
        items_written += 1

    # 7. 每个 item 创建对应的 RegReportingItemDimension（ROW + COLUMN 各一条）
    existing_dimension_keys = {
        (entry.reporting_item_id, entry.dimension_id, entry.member_id)
        for entry in session.exec(
            select(RegReportingItemDimension).where(
                RegReportingItemDimension.reporting_item_id.in_(item_id_map.values())
            )
        ).all()
    }
    for id_entry in parse_result.item_dimensions:
        item_code = id_entry["item_code"]
        item_id = item_id_map.get(item_code)
        if item_id is None:
            continue  # 该 item 已存在，跳过

        row_member_code = id_entry.get("row_member_code", "")
        col_member_code = id_entry.get("col_member_code", "")

        row_member_id = member_id_map.get(row_member_code)
        col_member_id = member_id_map.get(col_member_code)

        row_dimension_key = (item_id, row_dim.id, row_member_id)
        if row_member_id and row_dim.id and row_dimension_key not in existing_dimension_keys:
            session.add(RegReportingItemDimension(
                reporting_item_id=item_id,
                dimension_id=row_dim.id,  # type: ignore[arg-type]
                member_id=row_member_id,
                axis="ROW",
            ))
            existing_dimension_keys.add(row_dimension_key)

        col_dimension_key = (item_id, col_dim.id, col_member_id)
        if col_member_id and col_dim.id and col_dimension_key not in existing_dimension_keys:
            session.add(RegReportingItemDimension(
                reporting_item_id=item_id,
                dimension_id=col_dim.id,  # type: ignore[arg-type]
                member_id=col_member_id,
                axis="COLUMN",
            ))
            existing_dimension_keys.add(col_dimension_key)

    session.commit()
    return items_written


# ──────────────────────────────────────────────────────────────────────────────
# 主后台任务
# ──────────────────────────────────────────────────────────────────────────────

async def process_catalog_zip(
    batch_id: int,
    zip_path: Path,
    extract_to: Path,
    object_codes: list[str] | None = None,
) -> None:
    """
    整体流程：扫描 → 创建 batch_items → 逐表解析写库 → 更新进度。
    供 FastAPI BackgroundTasks 调用（async）。
    object_codes: 报表代码白名单（如 ["G31"]），None 表示全部处理。
    """
    # ── Step 1: 把 batch.status 设为 "PROCESSING" ──────────────────────────
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if not batch:
            return
        batch.status = "PROCESSING"
        session.add(batch)
        session.commit()

    # ── Step 2: 扫描 zip ────────────────────────────────────────────────────
    try:
        version_label, file_sets = zip_scanner.scan_zip(zip_path, extract_to)
        # 应用报表代码白名单过滤
        if object_codes:
            upper_codes = {c.upper() for c in object_codes}
            file_sets = [fs for fs in file_sets if fs.object_code.upper() in upper_codes]
    except Exception:
        with Session(engine) as session:
            batch = session.get(RegCatalogBatch, batch_id)
            if batch:
                batch.status = "PARTIAL_FAIL"
                batch.finished_at = datetime.utcnow()
                session.add(batch)
                session.commit()
        return

    # ── Step 3: 批量创建 batch_items，获取 system/version ──────────────────
    batch_items: list[RegCatalogBatchItem] = []
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if not batch:
            return
        batch.version_label = version_label
        batch.total_count = len(file_sets)
        session.add(batch)

        system = _get_or_create_system(session)
        version = _get_or_create_version(session, system.id, version_label)  # type: ignore[arg-type]

        for fs in file_sets:
            item = RegCatalogBatchItem(
                batch_id=batch_id,
                object_code=fs.object_code,
                change_type=fs.change_type,
                table_category=fs.table_category,
                excel_filename=str(fs.excel_path.name) if fs.excel_path else "",
                doc_filename=str(fs.doc_path.name) if fs.doc_path else "",
                parse_status="PENDING",
            )
            session.add(item)
            batch_items.append(item)

        session.commit()

        # refresh 每个 item 以获得 id
        for item in batch_items:
            session.refresh(item)

        system_id: int = system.id  # type: ignore[assignment]
        version_id: int = version.id  # type: ignore[assignment]

    # ── Step 4: 逐表处理 ───────────────────────────────────────────────────
    for fs, batch_item in zip(file_sets, batch_items):
        item_id = batch_item.id

        # 4a: 把 batch_item.parse_status 设 "PARSING"
        with Session(engine) as session:
            item = session.get(RegCatalogBatchItem, item_id)
            if not item:
                continue
            item.parse_status = "PARSING"
            session.add(item)
            session.commit()

        try:
            # 4b: 解析 Excel（change_type != "INSTRUCTION_ONLY" 时）
            parse_result: excel_parser.ExcelParseResult | None = None
            if fs.change_type != "INSTRUCTION_ONLY" and fs.excel_path:
                section_code = _section_code_for_object_code(fs.object_code)
                parse_result = excel_parser.parse_excel(
                    fs.excel_path, fs.object_code, section_code=section_code
                )

            # 4c: 解析 Doc + 生成 change_summary
            full_text = ""
            change_summary = ""
            if fs.doc_path:
                full_text = doc_parser.extract_doc_text(fs.doc_path)
                change_summary = await doc_parser.generate_change_summary(
                    full_text, fs.object_code
                )

            # 4d: 写库
            items_count = 0
            with Session(engine) as session:
                rep_obj = _upsert_reporting_object(
                    session,
                    object_code=fs.object_code,
                    system_id=system_id,
                    version_id=version_id,
                    change_type=fs.change_type,
                    table_category=fs.table_category,
                    version_label=fs.version_label or version_label,
                    batch_item_id=item_id,  # type: ignore[arg-type]
                )

                # 写 Instruction
                if fs.doc_path:
                    existing_instr = session.exec(
                        select(RegReportingInstruction).where(
                            RegReportingInstruction.reporting_object_id == rep_obj.id
                        )
                    ).first()
                    if not existing_instr:
                        session.add(RegReportingInstruction(
                            reporting_object_id=rep_obj.id,
                            instruction_code=f"{fs.object_code}.INSTRUCTION.{fs.version_label or version_label}",
                            instruction_text=full_text,
                            source_reference=str(fs.doc_path.name),
                        ))

                # 写 Excel 解析结果
                if parse_result is not None:
                    items_count = _write_excel_results(
                        session,
                        parse_result=parse_result,
                        object_id=rep_obj.id,  # type: ignore[arg-type]
                        batch_item_id=item_id,  # type: ignore[arg-type]
                        object_code=fs.object_code,
                        version_label=fs.version_label or version_label,
                        change_type=fs.change_type,
                        section_code=_section_code_for_object_code(fs.object_code),
                    )
                else:
                    session.commit()

            # 4e: 更新 batch_item 状态为 DONE
            with Session(engine) as session:
                item = session.get(RegCatalogBatchItem, item_id)
                if item:
                    item.parse_status = "DONE"
                    item.change_summary = change_summary
                    item.items_count = items_count
                    item.finished_at = datetime.utcnow()
                    session.add(item)
                    session.commit()

            # 4f: 更新 batch.done_count
            with Session(engine) as session:
                batch = session.get(RegCatalogBatch, batch_id)
                if batch:
                    batch.done_count = (batch.done_count or 0) + 1
                    session.add(batch)
                    session.commit()

        except Exception as exc:
            # 4g: 失败处理
            error_msg = str(exc)[:500]
            with Session(engine) as session:
                item = session.get(RegCatalogBatchItem, item_id)
                if item:
                    item.parse_status = "FAILED"
                    item.parse_error = error_msg
                    item.finished_at = datetime.utcnow()
                    session.add(item)
                    session.commit()

            with Session(engine) as session:
                batch = session.get(RegCatalogBatch, batch_id)
                if batch:
                    batch.fail_count = (batch.fail_count or 0) + 1
                    session.add(batch)
                    session.commit()

    # ── Step 5: 最终更新 batch 状态 ─────────────────────────────────────────
    with Session(engine) as session:
        batch = session.get(RegCatalogBatch, batch_id)
        if batch:
            batch.status = "DONE" if (batch.fail_count or 0) == 0 else "PARTIAL_FAIL"
            batch.finished_at = datetime.utcnow()
            session.add(batch)
            session.commit()

    # ── Step 6: 清理临时目录 ─────────────────────────────────────────────────
    try:
        if extract_to.exists():
            shutil.rmtree(extract_to)
        zip_path.unlink(missing_ok=True)
    except Exception:
        pass  # 清理失败不影响主流程
