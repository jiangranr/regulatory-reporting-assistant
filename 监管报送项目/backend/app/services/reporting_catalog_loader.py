"""DB-backed adapter that produces a ReportingSeedCatalog from the live MySQL tables.

This module is the read path used by impact analysis. The write path (bootstrap)
still uses build_1104_seed_catalog() from reporting_seed.py.

Why a loader, not a query: the downstream consumers (signals_to_changes,
analyze_reporting_impacts) already speak `list[dict]` from the in-memory seed,
and tests construct that shape directly. Preserving the shape keeps the blast
radius minimal and tests unchanged.

Only the two fields actually consumed by impact analysis are populated with real
data (`reporting_items`, `lineage`). Everything else is left as empty arrays —
if a future consumer needs them, fill them in here, not in callers.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from app.models.db_models import (
    DataFieldCatalog,
    RegReportingItem,
    ReportingItemLineage,
)
from app.services.reporting_seed import ReportingSeedCatalog


logger = logging.getLogger(__name__)


def load_catalog_from_db(session: Session) -> ReportingSeedCatalog:
    """Assemble a ReportingSeedCatalog from the live database.

    Returns an empty-but-valid catalog when the tables are unpopulated; callers
    will end up with no impacts, which surfaces a missing bootstrap clearly.
    """
    items = session.exec(
        select(RegReportingItem).where(RegReportingItem.status == "ACTIVE")
    ).all()
    reporting_items = [
        {
            "item_code": item.item_code,
            "item_name": item.item_name,
            # Keep object/section codes available so downstream filters work.
            # item_code prefix already encodes object_code (e.g. "G31.PART_I...").
            "object_code": item.item_code.split(".")[0] if item.item_code else "",
            "item_type": item.item_type or "INDICATOR",
            # row_label/column_label are critical for matching cell-level signals
            # like "债券投资合计 × D_因持有非底层" against item cells.
            "row_label": item.row_label or "",
            "column_label": item.column_label or "",
            "status": item.status or "ACTIVE",
        }
        for item in items
    ]

    # Three-way join: lineage → item.item_code, field.field_code, role
    lineage_rows = session.exec(
        select(ReportingItemLineage, RegReportingItem, DataFieldCatalog)
        .join(RegReportingItem, RegReportingItem.id == ReportingItemLineage.reporting_item_id)
        .join(DataFieldCatalog, DataFieldCatalog.id == ReportingItemLineage.data_field_id)
    ).all()
    lineage = [
        {
            "reporting_item_code": item.item_code,
            "data_field_code": field.field_code,
            "data_field_name": field.field_name,
            "lineage_role": ril.lineage_role,
            # extra context that analyzer might want later; safe to ignore
            "transform_logic": ril.transform_expression or "",
            "confidence_level": ril.confidence_level or "MEDIUM",
            "review_status": ril.mapping_status or "DRAFT",
        }
        for (ril, item, field) in lineage_rows
    ]

    if not reporting_items or not lineage:
        logger.warning(
            "reporting catalog from DB is empty (items=%d, lineage=%d); "
            "did you run `uv run python -m scripts.bootstrap_route_a`?",
            len(reporting_items),
            len(lineage),
        )

    return ReportingSeedCatalog(
        reporting_systems=[],
        reporting_versions=[],
        reporting_objects=[],
        reporting_sections=[],
        reporting_items=reporting_items,
        reporting_instructions=[],
        reporting_rules=[],
        data_systems=[],
        data_fields=[],
        data_field_code_values=[],
        business_concept_value_mappings=[],
        measure_field_mappings=[],
        lineage=lineage,
    )
