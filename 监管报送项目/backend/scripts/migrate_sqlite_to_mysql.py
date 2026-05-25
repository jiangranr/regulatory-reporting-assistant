from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import MetaData, Table, create_engine, delete, select
from sqlmodel import SQLModel

from app.core.database import engine_kwargs_for_url
from app.models import db_models  # noqa: F401


TABLE_ORDER = [
    "reg_documents",
    "reg_tasks",
    "rule_extract_results",
    "impact_analysis_results",
    "ticket_drafts",
    "audit_logs",
    "reg_clauses",
    "reg_semantic_items",
    "business_object_dict",
    "business_object_system_mappings",
    "metadata_fields",
    "object_field_mappings",
    "validation_rules",
    "rule_cards",
    "review_records",
]


def migrate_tables(source_url: str, target_url: str, table_names: Sequence[str]) -> dict[str, int]:
    source_engine = create_engine(source_url, **engine_kwargs_for_url(source_url))
    target_engine = create_engine(target_url, **engine_kwargs_for_url(target_url))

    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_engine, only=list(table_names))
    target_metadata.reflect(bind=target_engine, only=list(table_names))

    migrated: dict[str, int] = {}
    for table_name in table_names:
        source_table = Table(table_name, source_metadata)
        target_table = Table(table_name, target_metadata)
        with source_engine.connect() as source_connection:
            rows = [
                dict(row)
                for row in source_connection.execute(select(source_table)).mappings().all()
            ]

        with target_engine.begin() as target_connection:
            target_connection.execute(delete(target_table))
            if rows:
                target_connection.execute(target_table.insert(), rows)

        migrated[table_name] = len(rows)

    return migrated


def create_target_schema(target_url: str) -> None:
    target_engine = create_engine(target_url, **engine_kwargs_for_url(target_url))
    SQLModel.metadata.create_all(target_engine)


def main() -> None:
    source_url = "sqlite:///./data/app.db"
    target_url = "mysql+pymysql://reg_user:reg_pass_123@localhost:3306/reg_reporting?charset=utf8mb4"
    create_target_schema(target_url)
    migrated = migrate_tables(source_url, target_url, TABLE_ORDER)
    for table_name, count in migrated.items():
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
