from sqlalchemy import create_engine, text

from scripts.migrate_sqlite_to_mysql import migrate_tables


def test_migrate_tables_preserves_ids_and_replaces_target_rows(tmp_path):
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url)

    for engine in (source_engine, target_engine):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "create table reg_documents ("
                    "id integer primary key, "
                    "filename text not null, "
                    "title text not null"
                    ")"
                )
            )

    with source_engine.begin() as connection:
        connection.execute(
            text("insert into reg_documents (id, filename, title) values (7, 'notice.txt', '公告')")
        )
    with target_engine.begin() as connection:
        connection.execute(
            text("insert into reg_documents (id, filename, title) values (1, 'old.txt', '旧数据')")
        )

    counts = migrate_tables(source_url, target_url, ["reg_documents"])

    with target_engine.connect() as connection:
        rows = connection.execute(
            text("select id, filename, title from reg_documents order by id")
        ).mappings().all()

    assert counts == {"reg_documents": 1}
    assert [dict(row) for row in rows] == [
        {"id": 7, "filename": "notice.txt", "title": "公告"}
    ]
