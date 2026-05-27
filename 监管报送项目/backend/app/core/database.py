from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import inspect, text

from app.core.config import get_settings


settings = get_settings()


def engine_kwargs_for_url(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if database_url.startswith(("mysql", "mariadb")):
        return {"pool_pre_ping": True}
    return {}


engine = create_engine(settings.database_url, **engine_kwargs_for_url(settings.database_url))


def init_db() -> None:
    if settings.database_url.startswith("sqlite:///./"):
        db_path = Path(settings.database_url.replace("sqlite:///./", "./"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)
    _ensure_reg_document_parse_columns()
    _ensure_document_task_profile_columns()
    _ensure_reg_reporting_object_columns()
    _ensure_reg_reporting_item_columns()
    _ensure_reg_reporting_item_dimension_columns()
    _ensure_reg_reporting_impact_columns()
    _ensure_ticket_draft_columns()
    _ensure_reg_reporting_change_candidate_columns()


def _ensure_reg_document_parse_columns() -> None:
    inspector = inspect(engine)
    if "reg_documents" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("reg_documents")}
    columns = dict(reg_document_parse_column_ddls(engine.dialect.name))
    missing = [(name, ddl) for name, ddl in columns.items() if name not in existing]
    with engine.begin() as connection:
        for name, ddl in missing:
            connection.execute(text(f"ALTER TABLE reg_documents ADD COLUMN {name} {ddl}"))
        connection.execute(
            text("UPDATE reg_documents SET parse_error_message = '' WHERE parse_error_message IS NULL")
        )


def reg_document_parse_column_ddls(dialect_name: str) -> list[tuple[str, str]]:
    text_column = "TEXT" if dialect_name in {"mysql", "mariadb"} else "TEXT DEFAULT ''"
    return [
        ("parse_status", "VARCHAR(20) DEFAULT 'UPLOADED'"),
        ("parser", "VARCHAR(255) DEFAULT ''"),
        ("char_count", "INTEGER DEFAULT 0"),
        ("paragraph_count", "INTEGER DEFAULT 0"),
        ("table_count", "INTEGER DEFAULT 0"),
        ("parse_quality", "VARCHAR(255) DEFAULT 'UNKNOWN'"),
        ("parse_error_message", text_column),
    ]


def _ensure_document_task_profile_columns() -> None:
    inspector = inspect(engine)
    if "document_task_profiles" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("document_task_profiles")}
    columns = document_task_profile_column_ddls()
    missing = [(name, ddl, default) for name, ddl, default in columns if name not in existing]
    with engine.begin() as connection:
        for name, ddl, default in missing:
            connection.execute(text(f"ALTER TABLE document_task_profiles ADD COLUMN {name} {ddl}"))
            if default is not None:
                connection.execute(
                    text(f"UPDATE document_task_profiles SET `{name}` = :val WHERE `{name}` IS NULL"),
                    {"val": default},
                )
        if "task_type" in existing or any(name == "task_type" for name, _, _ in missing):
            connection.execute(
                text("UPDATE document_task_profiles SET task_type = 'MANUAL_REVIEW' WHERE task_type IS NULL")
            )


def document_task_profile_column_ddls() -> list[tuple[str, str, str | None]]:
    # MySQL TEXT 列不支持 ALTER TABLE 中的 DEFAULT，需分两步：先 ADD COLUMN，再 UPDATE
    return [
        ("task_type", "VARCHAR(255)", "MANUAL_REVIEW"),
        ("requires_business_object_match", "BOOLEAN", "0"),
        ("affected_table_codes", "TEXT", "[]"),
        ("change_signals", "TEXT", "[]"),
        ("in_scope_tables", "TEXT", "[]"),
        ("out_of_scope_tables", "TEXT", "[]"),
    ]


def _ensure_reg_reporting_object_columns() -> None:
    """补充 Task 1 扩展的 reg_reporting_objects 新列（处理旧 DB 不含新列的情况）。"""
    inspector = inspect(engine)
    if "reg_reporting_objects" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("reg_reporting_objects")}
    new_cols = [
        ("change_type", "VARCHAR(30) DEFAULT ''"),
        ("table_category", "VARCHAR(50) DEFAULT ''"),
        ("current_version_label", "VARCHAR(20) DEFAULT ''"),
        ("latest_batch_item_id", "INTEGER DEFAULT NULL"),
    ]
    with engine.begin() as connection:
        for name, ddl in new_cols:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE reg_reporting_objects ADD COLUMN {name} {ddl}"))


def _ensure_reg_reporting_item_dimension_columns() -> None:
    """补充 reg_reporting_item_dimensions 的 created_at 列（旧表建立时未含此列）。"""
    inspector = inspect(engine)
    if "reg_reporting_item_dimensions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("reg_reporting_item_dimensions")}
    if "created_at" not in existing:
        with engine.begin() as connection:
            connection.execute(text(
                "ALTER TABLE reg_reporting_item_dimensions ADD COLUMN created_at DATETIME DEFAULT NULL"
            ))


def _ensure_reg_reporting_item_columns() -> None:
    """补充 Task 1 扩展的 reg_reporting_items 新列（处理旧 DB 不含新列的情况）。"""
    inspector = inspect(engine)
    if "reg_reporting_items" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("reg_reporting_items")}
    new_cols = [
        ("batch_item_id", "INTEGER DEFAULT NULL"),
        ("change_status", "VARCHAR(20) DEFAULT ''"),
        ("source_cell_ref", "VARCHAR(20) DEFAULT ''"),
        ("cell_role", "VARCHAR(20) DEFAULT ''"),
        ("is_fillable", "BOOLEAN DEFAULT 1"),
        ("is_derived", "BOOLEAN DEFAULT 0"),
        ("data_type", "VARCHAR(20) DEFAULT 'DECIMAL'"),
    ]
    with engine.begin() as connection:
        for name, ddl in new_cols:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE reg_reporting_items ADD COLUMN {name} {ddl}"))


def _ensure_reg_reporting_impact_columns() -> None:
    """补充影响项的工单范围输出列（旧库兼容）。

    MySQL 不允许 TEXT 列在 ALTER TABLE 中带 DEFAULT，需先 ADD COLUMN，再 UPDATE 设默认值。
    """
    inspector = inspect(engine)
    if "reg_reporting_impact_items" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("reg_reporting_impact_items")}
    new_cols = [
        ("ticket_parent_type", "VARCHAR(50) DEFAULT ''", None),
        ("required_sub_ticket_types", "TEXT", "[]"),
        ("conditional_sub_ticket_types", "TEXT", "[]"),
        ("sub_ticket_triggers", "TEXT", "{}"),
    ]
    with engine.begin() as connection:
        for name, ddl, default in new_cols:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE reg_reporting_impact_items ADD COLUMN {name} {ddl}"))
                if default is not None:
                    connection.execute(
                        text(f"UPDATE reg_reporting_impact_items SET `{name}` = :val WHERE `{name}` IS NULL"),
                        {"val": default},
                    )


def _ensure_ticket_draft_columns() -> None:
    """补充 ticket_drafts 的母子单结构列（旧库兼容）。"""
    inspector = inspect(engine)
    if "ticket_drafts" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("ticket_drafts")}
    new_cols = [
        ("parent_ticket_id", "INTEGER DEFAULT NULL"),
        ("ticket_role", "VARCHAR(20) DEFAULT 'PARENT'"),
        ("change_ticket_type", "VARCHAR(50) DEFAULT ''"),
        ("action_ticket_type", "VARCHAR(50) DEFAULT ''"),
        ("severity_level", "VARCHAR(10) DEFAULT ''"),
        ("severity_score", "INTEGER DEFAULT 0"),
        ("severity_signals", "TEXT"),
        ("severity_forced_reason", "VARCHAR(255) DEFAULT ''"),
        ("severity_overridden_by", "VARCHAR(100) DEFAULT ''"),
        ("owner_role", "VARCHAR(50) DEFAULT ''"),
        ("executor_role", "VARCHAR(50) DEFAULT ''"),
        ("depends_on_lineage", "BOOLEAN DEFAULT 0"),
        ("business_signoff_required", "BOOLEAN DEFAULT 0"),
        ("closure_review_required", "BOOLEAN DEFAULT 0"),
        ("related_impact_codes", "TEXT"),
        ("summary", "TEXT"),
        ("responsible_system", "VARCHAR(80) DEFAULT ''"),
        ("affected_systems", "TEXT"),
        ("affected_assets", "TEXT"),
        ("must_do", "TEXT"),
        ("must_confirm", "TEXT"),
        ("output_artifacts", "TEXT"),
        ("acceptance_criteria_structured", "TEXT"),
        ("blockers", "TEXT"),
        ("evidence_refs", "TEXT"),
        ("historical_cases", "TEXT"),
        ("quality_score", "INTEGER DEFAULT 0"),
        ("quality_flags", "TEXT"),
        ("status", "VARCHAR(20) DEFAULT 'DRAFT'"),
    ]
    with engine.begin() as connection:
        for name, ddl in new_cols:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE ticket_drafts ADD COLUMN {name} {ddl}"))
        # TEXT 列在 MySQL 不支持 ALTER 时直接 DEFAULT，补默认值
        connection.execute(text("UPDATE ticket_drafts SET severity_signals = '[]' WHERE severity_signals IS NULL"))
        connection.execute(text("UPDATE ticket_drafts SET related_impact_codes = '[]' WHERE related_impact_codes IS NULL"))
        json_defaults = {
            "affected_systems": "[]",
            "affected_assets": "{}",
            "must_do": "[]",
            "must_confirm": "[]",
            "output_artifacts": "[]",
            "acceptance_criteria_structured": "[]",
            "blockers": "[]",
            "evidence_refs": "[]",
            "historical_cases": "[]",
            "quality_flags": "[]",
        }
        for column_name, default_value in json_defaults.items():
            connection.execute(
                text(f"UPDATE ticket_drafts SET `{column_name}` = :val WHERE `{column_name}` IS NULL"),
                {"val": default_value},
            )
        connection.execute(text("UPDATE ticket_drafts SET summary = '' WHERE summary IS NULL"))
        connection.execute(text("UPDATE ticket_drafts SET responsible_system = '' WHERE responsible_system IS NULL"))


def _ensure_reg_reporting_change_candidate_columns() -> None:
    """补 reg_reporting_change_candidates 表的修订对照表 v2 增量列。

    这 6 列来自字段级修订对照表（RevisionEntry v2），由 item_change_scanner
    在创建 candidate 时填入，工单生成器后续可读取。
    """
    inspector = inspect(engine)
    if "reg_reporting_change_candidates" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("reg_reporting_change_candidates")}
    new_cols = [
        ("revision_id", "VARCHAR(64) DEFAULT ''", None),
        ("field_code", "VARCHAR(128) DEFAULT ''", None),
        ("change_dimensions", "TEXT", "[]"),
        ("change_summary", "TEXT", ""),
        ("before_after_snapshot", "TEXT", "{}"),
        ("affected_cells", "TEXT", "[]"),
    ]
    with engine.begin() as connection:
        for name, ddl, default in new_cols:
            if name not in existing:
                connection.execute(text(f"ALTER TABLE reg_reporting_change_candidates ADD COLUMN {name} {ddl}"))
                if default is not None:
                    connection.execute(
                        text(f"UPDATE reg_reporting_change_candidates SET `{name}` = :val WHERE `{name}` IS NULL"),
                        {"val": default},
                    )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
