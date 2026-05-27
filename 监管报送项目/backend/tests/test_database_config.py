from app.core.database import engine_kwargs_for_url, reg_document_parse_column_ddls
from app.models.db_models import RegDocument, TicketDraft
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable


def test_sqlite_engine_uses_check_same_thread_false():
    assert engine_kwargs_for_url("sqlite:///./data/app.db") == {
        "connect_args": {"check_same_thread": False}
    }


def test_mysql_engine_uses_pool_pre_ping():
    assert engine_kwargs_for_url("mysql+pymysql://reg_user:reg_pass_123@localhost/reg_reporting") == {
        "pool_pre_ping": True
    }


def test_mysql_schema_uses_text_for_long_document_and_ticket_fields():
    document_ddl = str(CreateTable(RegDocument.__table__).compile(dialect=mysql.dialect()))
    ticket_ddl = str(CreateTable(TicketDraft.__table__).compile(dialect=mysql.dialect()))

    assert "parsed_text TEXT" in document_ddl
    assert "text_excerpt TEXT" in document_ddl
    assert "content TEXT" in ticket_ddl


def test_mysql_reg_document_parse_migration_does_not_default_text_columns():
    columns = dict(reg_document_parse_column_ddls("mysql"))

    assert columns["parse_error_message"] == "TEXT"


def test_ticket_draft_has_structured_governance_fields_for_mysql():
    ticket_ddl = str(CreateTable(TicketDraft.__table__).compile(dialect=mysql.dialect()))
    assert "summary TEXT" in ticket_ddl
    assert "responsible_system VARCHAR(80)" in ticket_ddl
    assert "affected_systems TEXT" in ticket_ddl
    assert "affected_assets TEXT" in ticket_ddl
    assert "must_do TEXT" in ticket_ddl
    assert "must_confirm TEXT" in ticket_ddl
    assert "output_artifacts TEXT" in ticket_ddl
    assert "acceptance_criteria_structured TEXT" in ticket_ddl
    assert "blockers TEXT" in ticket_ddl
    assert "evidence_refs TEXT" in ticket_ddl
    assert "historical_cases TEXT" in ticket_ddl
    assert "quality_score INTEGER" in ticket_ddl
    assert "quality_flags TEXT" in ticket_ddl
