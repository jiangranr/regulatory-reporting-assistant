from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.db_models import (
    BusinessConceptValueMapping,
    DataFieldCatalog,
    DataFieldCodeValue,
    DataSystemCatalog,
    MeasureFieldMapping,
    RegReportingInstruction,
    RegReportingItem,
    RegReportingObject,
    RegReportingRule,
    RegReportingSection,
    RegReportingSystem,
    RegReportingVersion,
    ReportingItemLineage,
)
from app.models.schemas import (
    ReportingItemRead,
    ReportingLineageFieldRead,
    ReportingLineageResponse,
    ReportingObjectRead,
    ReportingSeedResponse,
)
from app.services.concept_seed import seed_concepts_and_rule_cards
from app.services.embedding_indexer import build_instruction_index
from app.services.reporting_item_scope import is_analysis_item
from app.services.reporting_seed import ReportingSeedCatalog, build_1104_seed_catalog
from app.services.source_recommender import build_field_embeddings, recommend_source

# G31 详细 item（A/B/C/D/E 列），bootstrap-all 时用于补齐 DB
_G31_DETAIL_ITEMS = [
    {"item_code": "G31.PART_I.1_0.A_穿透前_期末余额",          "item_name": "1 行·A 列 · 穿透前·期末余额",                           "row_label": "1.债券投资合计", "column_label": "A·穿透前·期末余额",                     "source_cell_ref": "C5"},
    {"item_code": "G31.PART_I.1_0.B_投资收入_年初至报告期末数", "item_name": "1 行·B 列 · 投资收入·年初至报告期末数",                 "row_label": "1.债券投资合计", "column_label": "B·投资收入·年初至报告期末数",           "source_cell_ref": "D5"},
    {"item_code": "G31.PART_I.1_0.C_修正久期",                  "item_name": "1 行·C 列 · 修正久期",                                  "row_label": "1.债券投资合计", "column_label": "C·修正久期",                             "source_cell_ref": "E5"},
    {"item_code": "G31.PART_I.1_0.D_因持有非底层资产而间接持有_期末余额", "item_name": "1 行·D 列 · 因持有非底层资产而间接持有·期末余额", "row_label": "1.债券投资合计", "column_label": "D·因持有非底层资产而间接持有·期末余额", "source_cell_ref": "F5"},
    {"item_code": "G31.PART_I.1_0.单位_万元_E_穿透后_期末余额", "item_name": "1 行·E 列 · 穿透后·期末余额（单位：万元）",             "row_label": "1.债券投资合计", "column_label": "E·穿透后·期末余额",                     "source_cell_ref": "G5"},
]


def _ensure_g31_detail_items(session: Session) -> tuple[int, int]:
    """补齐 G31 详细 item（A-E 列）。返回 (inserted, updated)。"""
    obj = session.exec(
        select(RegReportingObject).where(RegReportingObject.object_code == "G31")
    ).first()
    if obj is None or obj.id is None:
        return 0, 0

    section = session.exec(
        select(RegReportingSection).where(
            RegReportingSection.reporting_object_id == obj.id,
            RegReportingSection.section_code == "PART_I",
        )
    ).first()
    if section is None or section.id is None:
        return 0, 0

    inserted = updated = 0
    for row in _G31_DETAIL_ITEMS:
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
            updated += 1
    session.flush()
    return inserted, updated

router = APIRouter(prefix="/api/reporting", tags=["reporting-catalog"])


@router.post("/seed-1104", response_model=ReportingSeedResponse)
def seed_1104_catalog(session: Session = Depends(get_session)) -> ReportingSeedResponse:
    catalog = build_1104_seed_catalog()
    _upsert_seed_catalog(session, catalog)
    session.commit()
    # 1104 报表目录灌完后顺带灌概念库和规则卡片（依赖报送项 code 必须先在库）
    concept_stats = seed_concepts_and_rule_cards(session)
    return ReportingSeedResponse(
        reporting_systems=len(catalog.reporting_systems),
        reporting_versions=len(catalog.reporting_versions),
        reporting_objects=len(catalog.reporting_objects),
        reporting_sections=len(catalog.reporting_sections),
        reporting_items=len(catalog.reporting_items),
        data_fields=len(catalog.data_fields),
        lineage=len(catalog.lineage),
        concepts=concept_stats["concepts_added"],
        rule_cards=concept_stats["rule_cards_added"],
    )


@router.post("/bootstrap-all")
def bootstrap_all(session: Session = Depends(get_session)) -> dict:
    """一键全量引导：基础目录 + G31 详细 item + G31 详细血缘 + 概念库。

    幂等，可重复运行。执行顺序：
    1. 灌 1104 基础目录（含 G24/G21/G25/G27/G31 基础血缘）
    2. 补齐 G31 A-E 列 item（Excel 解析产出的详细指标）
    3. 灌 G31 详细血缘（7 系统 / 26 字段 / 36 条血缘，mapping_status=SEED_CONFIRMED）
    4. 灌概念库 + 规则卡片
    """
    from scripts import seed_g31_lineage_reference as g31_seed

    # Step 1: 基础目录（含血缘写入 ReportingItemLineage）
    catalog = build_1104_seed_catalog()
    _upsert_seed_catalog(session, catalog)
    session.flush()

    # Step 2: G31 详细 item
    g31_items_inserted, g31_items_updated = _ensure_g31_detail_items(session)
    session.flush()

    # Step 3: G31 详细血缘
    system_by_code = g31_seed.upsert_systems(session)
    field_by_code = g31_seed.upsert_fields(session, system_by_code)
    # 详细血缘写入时统一设 SEED_CONFIRMED
    for item_code, field_code, role, expression, confidence in g31_seed.LINEAGE:
        item = session.exec(
            select(RegReportingItem).where(RegReportingItem.item_code == item_code)
        ).first()
        field = field_by_code.get(field_code)
        if item is None or item.id is None or field is None or field.id is None:
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
            "evidence": "G31 参考血缘种子数据",
            "owner_team": field.owner_team,
        }
        if existing is None:
            session.add(ReportingItemLineage(**payload))
        else:
            for k, v in payload.items():
                setattr(existing, k, v)
            session.add(existing)
    session.flush()

    # Step 4: 概念库
    concept_stats = seed_concepts_and_rule_cards(session)

    session.commit()
    return {
        "status": "ok",
        "basic_lineage": len(catalog.lineage),
        "g31_items_inserted": g31_items_inserted,
        "g31_items_updated": g31_items_updated,
        "g31_systems": len(g31_seed.DATA_SYSTEMS),
        "g31_fields": len(g31_seed.DATA_FIELDS),
        "g31_lineage": len(g31_seed.LINEAGE),
        "concepts_added": concept_stats["concepts_added"],
        "rule_cards_added": concept_stats["rule_cards_added"],
    }


@router.post("/build-instruction-index")
def build_instruction_index_endpoint(
    force_rebuild: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    """解析 G01/G31 填报说明 .doc 文件，切片后建 embedding 索引。

    force_rebuild=true 时清空现有记录重建。
    首次调用或文件更新后调用一次即可，不需要每次启动都调用。
    """
    return build_instruction_index(session, force_rebuild=force_rebuild)


@router.post("/build-field-embeddings")
def build_field_embeddings_endpoint(
    force_rebuild: bool = False,
    session: Session = Depends(get_session),
) -> dict:
    """为 DataFieldCatalog 所有字段构建 embedding 索引（供推荐引擎使用）。

    首次调用或字段目录更新后调用一次即可。
    """
    return build_field_embeddings(session, force_rebuild=force_rebuild)


@router.post("/recommend-source")
def recommend_source_endpoint(
    item_code: str,
    item_name: str,
    definition: str,
    session: Session = Depends(get_session),
) -> dict:
    """为新增指标推荐数据来源字段（关键词+语义+LLM 推理）。"""
    result = recommend_source(item_code, item_name, definition, session)
    return {
        "item_code": result.item_code,
        "item_name": result.item_name,
        "candidates": [
            {
                "field_code": c.field_code,
                "field_name": c.field_name,
                "table_name": c.table_name,
                "system_code": c.system_code,
                "system_name": c.system_name,
                "business_meaning": c.business_meaning,
                "reasoning": c.reasoning,
                "match_method": c.match_method,
            }
            for c in result.candidates
        ],
        "unresolved": result.unresolved,
        "escalate_to_human": result.escalate_to_human,
    }


@router.get("/objects", response_model=list[ReportingObjectRead])
def list_reporting_objects(
    reporting_system_code: str = "1104",
    session: Session = Depends(get_session),
) -> list[RegReportingObject]:
    system = _get_system(session, reporting_system_code)
    return session.exec(
        select(RegReportingObject)
        .where(RegReportingObject.reporting_system_id == system.id)
        .order_by(RegReportingObject.object_code)
    ).all()


@router.get("/items", response_model=list[ReportingItemRead])
def list_reporting_items(
    reporting_system_code: str = "1104",
    object_code: str | None = None,
    include_structural: bool = False,
    session: Session = Depends(get_session),
) -> list[RegReportingItem]:
    system = _get_system(session, reporting_system_code)
    object_ids = [
        item.id
        for item in session.exec(
            select(RegReportingObject).where(RegReportingObject.reporting_system_id == system.id)
        ).all()
        if item.id is not None and (object_code is None or item.object_code == object_code)
    ]
    if not object_ids:
        return []
    items = session.exec(
        select(RegReportingItem)
        .where(RegReportingItem.reporting_object_id.in_(object_ids))
        .order_by(RegReportingItem.item_code)
    ).all()
    if include_structural:
        return items
    return [item for item in items if is_analysis_item(item)]


@router.get("/items/{item_code}/lineage", response_model=ReportingLineageResponse)
def get_reporting_item_lineage(
    item_code: str,
    session: Session = Depends(get_session),
) -> ReportingLineageResponse:
    item = session.exec(select(RegReportingItem).where(RegReportingItem.item_code == item_code)).first()
    if item is None or item.id is None:
        raise HTTPException(status_code=404, detail="reporting item not found")

    lineage_rows = session.exec(
        select(ReportingItemLineage).where(ReportingItemLineage.reporting_item_id == item.id)
    ).all()
    field_reads: list[ReportingLineageFieldRead] = []
    for lineage in lineage_rows:
        field = session.get(DataFieldCatalog, lineage.data_field_id)
        if field is None:
            continue
        field_reads.append(
            ReportingLineageFieldRead(
                field_code=field.field_code,
                field_name=field.field_name,
                table_name=field.table_name,
                column_name=field.column_name,
                data_type=field.data_type,
                business_meaning=field.business_meaning,
                owner_team=field.owner_team,
                lineage_role=lineage.lineage_role,
                transform_expression=lineage.transform_expression,
                confidence_level=lineage.confidence_level,
                mapping_status=lineage.mapping_status,
            )
        )
    return ReportingLineageResponse(item=ReportingItemRead.model_validate(item), fields=field_reads)


def _upsert_seed_catalog(session: Session, catalog: ReportingSeedCatalog) -> None:
    system_by_code: dict[str, RegReportingSystem] = {}
    for row in catalog.reporting_systems:
        system = _one_by(session, RegReportingSystem, RegReportingSystem.system_code, row["system_code"])
        if system is None:
            system = RegReportingSystem(**row)
            session.add(system)
            session.flush()
        else:
            _assign(system, row)
        system_by_code[system.system_code] = system

    version_by_code: dict[str, RegReportingVersion] = {}
    for row in catalog.reporting_versions:
        system = system_by_code[row["reporting_system_code"]]
        version = session.exec(
            select(RegReportingVersion).where(
                RegReportingVersion.reporting_system_id == system.id,
                RegReportingVersion.version_code == row["version_code"],
            )
        ).first()
        payload = {
            "reporting_system_id": system.id,
            "version_code": row["version_code"],
            "version_name": row["version_name"],
            "effective_date": str(row.get("effective_year", "")),
            "status": row.get("status", "ACTIVE"),
        }
        if version is None:
            version = RegReportingVersion(**payload)
            session.add(version)
            session.flush()
        else:
            _assign(version, payload)
        version_by_code[version.version_code] = version

    system = system_by_code["1104"]
    version = version_by_code["2025_251"]
    object_by_code: dict[str, RegReportingObject] = {}
    for row in catalog.reporting_objects:
        reporting_object = session.exec(
            select(RegReportingObject).where(
                RegReportingObject.reporting_version_id == version.id,
                RegReportingObject.object_code == row["object_code"],
            )
        ).first()
        payload = {
            "reporting_system_id": system.id,
            "reporting_version_id": version.id,
            "object_code": row["object_code"],
            "object_name": row["object_name"],
            "object_category": row["category"],
            "report_frequency": row["frequency"],
            "submit_deadline": _submit_deadline(row["object_code"]),
            "status": row.get("status", "ACTIVE"),
        }
        if reporting_object is None:
            reporting_object = RegReportingObject(**payload)
            session.add(reporting_object)
            session.flush()
        else:
            _assign(reporting_object, payload)
        object_by_code[reporting_object.object_code] = reporting_object

    section_by_key: dict[tuple[str, str], RegReportingSection] = {}
    for row in catalog.reporting_sections:
        reporting_object = object_by_code[row["object_code"]]
        section = session.exec(
            select(RegReportingSection).where(
                RegReportingSection.reporting_object_id == reporting_object.id,
                RegReportingSection.section_code == row["section_code"],
            )
        ).first()
        payload = {
            "reporting_object_id": reporting_object.id,
            "section_code": row["section_code"],
            "section_name": row["section_name"],
            "display_order": int(row["order_no"]),
            "status": row.get("status", "ACTIVE"),
        }
        if section is None:
            section = RegReportingSection(**payload)
            session.add(section)
            session.flush()
        else:
            _assign(section, payload)
        section_by_key[(row["object_code"], row["section_code"])] = section

    item_by_code: dict[str, RegReportingItem] = {}
    for row in catalog.reporting_items:
        reporting_object = object_by_code[row["object_code"]]
        section = section_by_key[(row["object_code"], row["section_code"])]
        item = _one_by(session, RegReportingItem, RegReportingItem.item_code, row["item_code"])
        payload = {
            "reporting_object_id": reporting_object.id,
            "reporting_section_id": section.id,
            "item_code": row["item_code"],
            "item_name": row["item_name"],
            "item_type": row["item_type"],
            "row_label": row["row_label"],
            "column_label": row["column_label"],
            "measure_type": row["measure_type"],
            "unit": row["unit"],
            "status": row.get("status", "ACTIVE"),
        }
        if item is None:
            item = RegReportingItem(**payload)
            session.add(item)
            session.flush()
        else:
            _assign(item, payload)
        item_by_code[item.item_code] = item

    for row in catalog.reporting_instructions:
        item = item_by_code[row["item_code"]]
        _replace_instruction(session, object_by_code, item, row)

    for row in catalog.reporting_rules:
        item = item_by_code[row["item_code"]]
        rule = _one_by(session, RegReportingRule, RegReportingRule.rule_code, row["rule_code"])
        payload = {
            "reporting_item_id": item.id,
            "rule_code": row["rule_code"],
            "rule_name": row["rule_name"],
            "rule_type": row["rule_type"],
            "rule_expression": row["rule_expression"],
            "status": row.get("status", "ACTIVE"),
        }
        if rule is None:
            session.add(RegReportingRule(**payload))
        else:
            _assign(rule, payload)

    data_system_by_code: dict[str, DataSystemCatalog] = {}
    for row in catalog.data_systems:
        data_system = _one_by(session, DataSystemCatalog, DataSystemCatalog.system_code, row["system_code"])
        if data_system is None:
            data_system = DataSystemCatalog(**row)
            session.add(data_system)
            session.flush()
        else:
            _assign(data_system, row)
        data_system_by_code[data_system.system_code] = data_system

    field_by_code: dict[str, DataFieldCatalog] = {}
    for row in catalog.data_fields:
        data_system = data_system_by_code[row["system_code"]]
        field = _one_by(session, DataFieldCatalog, DataFieldCatalog.field_code, row["field_code"])
        payload = {
            "data_system_id": data_system.id,
            "field_code": row["field_code"],
            "field_name": row["field_name"],
            "table_name": row["table_name"],
            "column_name": row["column_name"],
            "data_type": row["data_type"],
            "business_meaning": row["business_meaning"],
            "owner_team": row["owner_team"],
            "status": row.get("status", "ACTIVE"),
        }
        if field is None:
            field = DataFieldCatalog(**payload)
            session.add(field)
            session.flush()
        else:
            _assign(field, payload)
        field_by_code[field.field_code] = field

    for row in catalog.data_field_code_values:
        code_value = session.exec(
            select(DataFieldCodeValue).where(
                DataFieldCodeValue.field_code == row["field_code"],
                DataFieldCodeValue.value_code == row["value_code"],
            )
        ).first()
        if code_value is None:
            session.add(DataFieldCodeValue(**row))
        else:
            _assign(code_value, row)

    for row in catalog.business_concept_value_mappings:
        concept_mapping = session.exec(
            select(BusinessConceptValueMapping).where(
                BusinessConceptValueMapping.concept_code == row["concept_code"],
                BusinessConceptValueMapping.field_code == row["field_code"],
                BusinessConceptValueMapping.value_code == row["value_code"],
            )
        ).first()
        if concept_mapping is None:
            session.add(BusinessConceptValueMapping(**row))
        else:
            _assign(concept_mapping, row)

    for row in catalog.measure_field_mappings:
        measure_mapping = session.exec(
            select(MeasureFieldMapping).where(
                MeasureFieldMapping.measure_concept_code == row["measure_concept_code"],
                MeasureFieldMapping.reporting_object_code == row["reporting_object_code"],
                MeasureFieldMapping.field_code == row["field_code"],
            )
        ).first()
        if measure_mapping is None:
            session.add(MeasureFieldMapping(**row))
        else:
            _assign(measure_mapping, row)

    for row in catalog.lineage:
        item = item_by_code[row["reporting_item_code"]]
        field = field_by_code[row["data_field_code"]]
        lineage = session.exec(
            select(ReportingItemLineage).where(
                ReportingItemLineage.reporting_item_id == item.id,
                ReportingItemLineage.data_field_id == field.id,
                ReportingItemLineage.lineage_role == row["lineage_role"],
            )
        ).first()
        payload = {
            "reporting_item_id": item.id,
            "data_field_id": field.id,
            "lineage_role": row["lineage_role"],
            "transform_expression": row["transform_logic"],
            "confidence_level": row["confidence_level"],
            "mapping_status": "SEED_CONFIRMED",
            "evidence": row["evidence_ref"],
        }
        if lineage is None:
            session.add(ReportingItemLineage(**payload))
        else:
            _assign(lineage, payload)


def _get_system(session: Session, code: str) -> RegReportingSystem:
    system = _one_by(session, RegReportingSystem, RegReportingSystem.system_code, code)
    if system is None:
        raise HTTPException(status_code=404, detail="reporting system not found")
    return system


def _one_by(session: Session, model, column, value):
    return session.exec(select(model).where(column == value)).first()


def _assign(model, values: dict) -> None:
    for key, value in values.items():
        setattr(model, key, value)


def _replace_instruction(
    session: Session,
    object_by_code: dict[str, RegReportingObject],
    item: RegReportingItem,
    row: dict[str, str],
) -> None:
    existing = session.exec(
        select(RegReportingInstruction).where(
            RegReportingInstruction.reporting_item_id == item.id,
            RegReportingInstruction.instruction_code == row["item_code"],
        )
    ).first()
    object_code = row["item_code"].split(".", 1)[0]
    payload = {
        "reporting_item_id": item.id,
        "reporting_object_id": object_by_code[object_code].id,
        "instruction_code": row["item_code"],
        "instruction_text": row["instruction_text"],
        "source_reference": row["source_location"],
        "status": row.get("status", "ACTIVE"),
    }
    if existing is None:
        session.add(RegReportingInstruction(**payload))
    else:
        _assign(existing, payload)


def _submit_deadline(object_code: str) -> str:
    return {"G21": "月后13日", "G24": "季后18日", "G25": "月后13日", "G27": "季后18日", "G31": "季后13日"}.get(
        object_code, ""
    )
