from __future__ import annotations

from unittest.mock import MagicMock, patch

import psycopg
import pytest

from app.config import Settings
from app.errors import DatabaseConfigurationRequired, SourceSchemaAmbiguous, StagingDiagnosticFailure
from app.repository import StagingCompetencyRepository


def repository(dsn: str | None = "postgresql://readonly", schema: str | None = None) -> StagingCompetencyRepository:
    return StagingCompetencyRepository(Settings(dsn, None, None, schema, ()))


def catalog_row(schema: str = "private_source") -> dict:
    return {
        "table_schema": schema,
        "table_oid": 41,
        "relkind": "r",
        "relowner": 99,
        "relrowsecurity": True,
        "relforcerowsecurity": True,
        "column_name": "competency_code",
        "data_type": "text",
        "database_type": "text",
        "not_null": True,
        "ordinal_position": 1,
    }


def role_row() -> dict:
    return {
        "role_name": "radix_reader",
        "rolsuper": False,
        "rolcreatedb": False,
        "rolcreaterole": False,
        "rolreplication": False,
        "rolbypassrls": False,
        "rolcanlogin": True,
        "database_create": False,
        "direct_role_memberships": 0,
        "privileged_role_memberships": 0,
    }


def privilege_row(**updates) -> dict:
    values = {
        "owns_source_table": False,
        "can_select": True,
        "can_insert": False,
        "can_update": False,
        "can_delete": False,
        "can_truncate": False,
        "can_references": False,
        "can_trigger": False,
        "schema_usage": True,
        "schema_create": False,
        "schemas_with_create_privilege": 0,
        "database_create": False,
        "database_temporary": False,
        "owns_source_schema": False,
        "owns_database": False,
        "other_selectable_relations": 0,
        "other_owned_relations": 0,
        "other_owned_objects": 0,
        "rls_enabled": True,
        "rls_forced": True,
        "rls_policy_count": 1,
    }
    values.update(updates)
    return values


def mocked_connection(rows=None, role=None, privileges=None):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [catalog_row()] if rows is None else rows
    cursor.fetchone.side_effect = [role or role_row(), privileges or privilege_row()]
    return connection, cursor


def test_diagnostic_reports_schema_columns_role_grants_and_rls_without_source_rows():
    repo = repository(schema="private_source")
    connection, cursor = mocked_connection()
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        result = repo.diagnose_access()

    assert result.source_schema == "private_source"
    assert result.role_name == "radix_reader"
    assert result.can_select is True
    assert result.can_insert is False
    assert result.rls_applies_to_direct_table_access is True
    assert result.read_only_candidate is True
    statements = [str(call.args[0]) for call in cursor.execute.call_args_list]
    assert statements[0] == "SET TRANSACTION READ ONLY"
    assert all("FROM private_source.staging_company_skill_levels" not in statement for statement in statements)
    assert all("SELECT *" not in statement.upper() for statement in statements)
    assert connect.call_args.kwargs["options"] == "-c default_transaction_read_only=on"


def test_diagnostic_requires_dsn_before_connecting():
    with patch("app.repository.psycopg.connect") as connect:
        with pytest.raises(DatabaseConfigurationRequired):
            repository(dsn=None).diagnose_access()
    connect.assert_not_called()


def test_diagnostic_requires_unambiguous_schema():
    rows = [catalog_row("private_source"), catalog_row("staging_copy")]
    connection, _ = mocked_connection(rows=rows)
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        with pytest.raises(SourceSchemaAmbiguous):
            repository().diagnose_access()


def test_effective_write_or_unrelated_read_grants_fail_read_only_assessment():
    connection, _ = mocked_connection(privileges=privilege_row(can_update=True, other_selectable_relations=2))
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        result = repository().diagnose_access()
    assert result.can_update is True
    assert result.other_selectable_relations == 2
    assert result.read_only_candidate is False


def test_missing_source_select_permission_fails_read_only_assessment():
    connection, _ = mocked_connection(privileges=privilege_row(can_select=False))
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        result = repository().diagnose_access()
    assert result.can_select is False
    assert result.read_only_candidate is False


def test_direct_admin_membership_and_object_ownership_fail_read_only_assessment():
    role = role_row() | {"direct_role_memberships": 1, "privileged_role_memberships": 1}
    permissions = privilege_row(other_owned_objects=1)
    connection, _ = mocked_connection(role=role, privileges=permissions)
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        result = repository().diagnose_access()
    assert result.direct_role_memberships == 1
    assert result.other_owned_objects == 1
    assert result.read_only_candidate is False


def test_catalog_permission_error_has_safe_permission_guidance():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, psycopg.errors.InsufficientPrivilege("dsn=private password=secret")]
    with patch("app.repository.psycopg.connect") as connect:
        connect.return_value.__enter__.return_value = connection
        with pytest.raises(StagingDiagnosticFailure) as caught:
            repository().diagnose_access()
    assert caught.value.category == "database_permission_failure"
    assert "database owner" in caught.value.next_step
    assert "secret" not in str(caught.value)
    assert "dsn" not in str(caught.value).lower()


@pytest.mark.parametrize(("exception", "category"), [
    (psycopg.OperationalError("could not translate host name 'secret-host'"), "dns_failure"),
    (psycopg.OperationalError("getaddrinfo failed for secret-host"), "dns_failure"),
    (psycopg.OperationalError("connection refused; password=secret"), "network_failure"),
    (psycopg.OperationalError("SSL certificate verify failed; password=secret"), "tls_ssl_failure"),
    (psycopg.OperationalError("connection timeout expired; password=secret"), "timeout"),
    (psycopg.OperationalError("password authentication failed for user secret; password=secret"), "authentication_failure"),
    (psycopg.OperationalError("password=secret"), "database_unavailable"),
])
def test_connection_error_category_and_guidance_are_sanitized(exception, category):
    with patch("app.repository.psycopg.connect", side_effect=exception):
        with pytest.raises(StagingDiagnosticFailure) as caught:
            repository().diagnose_access()
    assert caught.value.category == category
    assert caught.value.next_step
    assert "secret" not in str(caught.value)
    assert "password=secret" not in str(caught.value).lower()


def test_malformed_dsn_is_reported_before_connecting_without_echoing_it():
    private_dsn = "not-a-valid-dsn password=secret"
    with patch("app.repository.psycopg.connect") as connect:
        with pytest.raises(StagingDiagnosticFailure) as caught:
            repository(dsn=private_dsn).diagnose_access()
    connect.assert_not_called()
    assert caught.value.category == "malformed_dsn"
    assert "secret" not in str(caught.value)
    assert "password" not in str(caught.value).lower()
