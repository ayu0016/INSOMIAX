from __future__ import annotations

from unittest.mock import MagicMock, patch

import psycopg
import pytest

from app.config import Settings
from app.errors import DatabaseConfigurationRequired, DatabaseUnavailable, SourceSchemaAmbiguous, SourceTableNotFound
from app.repository import StagingCompetencyRepository


def settings(dsn: str | None) -> Settings:
    return Settings(dsn, None, None, None, ())


def test_missing_dsn_fails_before_connecting():
    repository = StagingCompetencyRepository(settings(None))
    with patch("app.repository.psycopg.connect") as connect:
        with pytest.raises(DatabaseConfigurationRequired):
            repository.inspect_source()
        connect.assert_not_called()


def test_connection_error_is_sanitized():
    repository = StagingCompetencyRepository(settings("postgresql://secret-value"))
    with patch("app.repository.psycopg.connect", side_effect=psycopg.OperationalError("dsn secret-value")):
        with pytest.raises(DatabaseUnavailable) as caught:
            repository.inspect_source()
    assert "secret-value" not in str(caught.value)
    assert "secret-value" not in caught.value.message


def test_schema_discovery_uses_table_metadata_and_count_without_selecting_rows():
    repository = StagingCompetencyRepository(settings("postgresql://readonly"))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        {
            "table_schema": "public",
            "column_name": "company_key",
            "data_type": "text",
            "udt_name": "text",
            "is_nullable": "NO",
            "ordinal_position": 1,
        },
        {
            "table_schema": "public",
            "column_name": "value",
            "data_type": "numeric",
            "udt_name": "numeric",
            "is_nullable": "YES",
            "ordinal_position": 2,
        },
    ]
    cursor.fetchone.return_value = {"row_count": 7}

    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        result = repository.inspect_source()

    assert result.source_schema == "public"
    assert result.row_count == 7
    assert [column.column_name for column in result.columns] == ["company_key", "value"]
    statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert any("information_schema.columns" in statement for statement in statements)
    assert any("count(*)" in statement for statement in statements)
    assert all("SELECT *" not in statement.upper() for statement in statements)


def test_repository_enforces_read_only_transaction():
    repository = StagingCompetencyRepository(settings("postgresql://readonly"))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{
        "table_schema": "public", "column_name": "id", "data_type": "uuid",
        "udt_name": "uuid", "is_nullable": "NO", "ordinal_position": 1,
    }]
    cursor.fetchone.return_value = {"row_count": 1}
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        repository.inspect_source()

    statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert "SET TRANSACTION READ ONLY" in statements
    assert "-c default_transaction_read_only=on" == connect.call_args.kwargs["options"]


def test_missing_source_table_is_reported_without_selecting_data():
    repository = StagingCompetencyRepository(settings("postgresql://readonly"))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        with pytest.raises(SourceTableNotFound):
            repository.inspect_source()
    assert len(cursor.execute.call_args_list) == 2  # read-only transaction + metadata lookup


def test_ambiguous_schema_requires_explicit_configuration():
    repository = StagingCompetencyRepository(settings("postgresql://readonly"))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [
        {"table_schema": "public", "column_name": "a", "data_type": "text", "udt_name": "text", "is_nullable": "NO", "ordinal_position": 1},
        {"table_schema": "private", "column_name": "b", "data_type": "text", "udt_name": "text", "is_nullable": "NO", "ordinal_position": 1},
    ]
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        with pytest.raises(SourceSchemaAmbiguous) as caught:
            repository.inspect_source()
    assert caught.value.details["available_schemas"] == ["private", "public"]
    assert len(cursor.execute.call_args_list) == 2
