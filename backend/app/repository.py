from __future__ import annotations

from dataclasses import asdict, dataclass

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from .config import Settings, get_settings
from .errors import (
    DatabaseConfigurationRequired,
    DatabaseUnavailable,
    SourceSchemaAmbiguous,
    SourceTableNotFound,
    StagingDiagnosticFailure,
)

SOURCE_TABLE = "staging_company_skill_levels"

_DIAGNOSTIC_GUIDANCE = {
    "malformed_dsn": "Correct the PostgreSQL DSN syntax and verify it contains the intended host, port, database, and user.",
    "dns_failure": "Verify the database hostname and DNS resolution from this machine.",
    "network_failure": "Check network access, firewall rules, VPN, and the database endpoint/port.",
    "tls_ssl_failure": "Check the provider's required SSL mode and certificate settings; keep TLS verification enabled.",
    "authentication_failure": "Verify the dedicated read-only user's username/password and that the account can log in.",
    "timeout": "Check network reachability and whether the database is accepting connections; retry after confirming the endpoint.",
    "database_permission_failure": "Have the database owner review read-only catalog and source-table access for this role; do not broaden the role.",
    "database_unavailable": "Check the database endpoint and network path, then retry the read-only diagnostic.",
}


def _diagnostic_failure_category(exc: psycopg.Error) -> str:
    state = getattr(exc, "sqlstate", None) or ""
    if isinstance(exc, psycopg.errors.InsufficientPrivilege) or state == "42501":
        return "database_permission_failure"
    safe_match_text = str(exc).lower()
    if (
        isinstance(exc, (psycopg.errors.InvalidPassword, psycopg.errors.InvalidAuthorizationSpecification))
        or state.startswith("28")
        or any(term in safe_match_text for term in ("password authentication failed", "authentication failed", "no password supplied"))
    ):
        return "authentication_failure"
    if isinstance(exc, psycopg.ProgrammingError):
        return "malformed_dsn"

    # Inspect driver text only to classify it. It is never included in output.
    if any(term in safe_match_text for term in ("ssl", "tls", "certificate", "cert verify")):
        return "tls_ssl_failure"
    if any(term in safe_match_text for term in ("timeout", "timed out", "deadline")) or state == "57014":
        return "timeout"
    if any(term in safe_match_text for term in ("could not translate host name", "name or service not known", "temporary failure in name resolution", "nodename nor servname", "getaddrinfo failed", "no such host")):
        return "dns_failure"
    if state.startswith("08") or any(term in safe_match_text for term in ("connection refused", "network is unreachable", "no route to host", "server closed the connection")):
        return "network_failure"
    return "database_unavailable"


@dataclass(frozen=True)
class ColumnMetadata:
    column_name: str
    data_type: str
    database_type: str
    nullable: bool
    ordinal_position: int


@dataclass(frozen=True)
class SourceInspection:
    source_table: str
    source_schema: str
    row_count: int
    columns: tuple[ColumnMetadata, ...]

    def as_dict(self) -> dict:
        return {
            "status": "schema_verification_required",
            "competencies_available": False,
            "readiness_scoring_available": False,
            "reason": "The source schema and competency mapping require backend operator review before values can be exposed.",
        }


@dataclass(frozen=True)
class StagingAccessDiagnostic:
    """Local-only database metadata and effective privilege summary; contains no source rows."""

    role_name: str
    source_table: str
    source_schema: str
    relation_kind: str
    columns: tuple[ColumnMetadata, ...]
    role_superuser: bool
    role_create_database: bool
    role_create_role: bool
    role_replication: bool
    role_bypass_rls: bool
    role_can_login: bool
    owns_source_table: bool
    owns_source_schema: bool
    owns_database: bool
    can_select: bool
    can_insert: bool
    can_update: bool
    can_delete: bool
    can_truncate: bool
    can_references: bool
    can_trigger: bool
    schema_usage: bool
    schema_create: bool
    schemas_with_create_privilege: int
    database_create: bool
    database_temporary: bool
    rls_enabled: bool
    rls_forced: bool
    rls_policy_count: int
    other_selectable_relations: int
    other_owned_relations: int
    other_owned_objects: int
    direct_role_memberships: int
    privileged_role_memberships: int

    @property
    def rls_applies_to_direct_table_access(self) -> bool:
        return self.rls_enabled and (
            self.rls_forced or not (self.owns_source_table or self.role_superuser or self.role_bypass_rls)
        )

    @property
    def read_only_candidate(self) -> bool:
        return (
            self.role_can_login
            and self.can_select
            and not any((self.can_insert, self.can_update, self.can_delete, self.can_truncate, self.can_references, self.can_trigger))
            and not any((self.role_superuser, self.role_create_database, self.role_create_role, self.role_replication, self.role_bypass_rls))
            and not self.owns_source_table
            and not self.owns_source_schema
            and not self.owns_database
            and self.schema_usage
            and not self.schema_create
            and self.schemas_with_create_privilege == 0
            and not self.database_create
            and not self.database_temporary
            and self.other_selectable_relations == 0
            and self.other_owned_relations == 0
            and self.other_owned_objects == 0
            and self.direct_role_memberships == 0
            and self.relation_kind in {"r", "p"}
        )

    def as_dict(self) -> dict:
        return {
            "connected_role": self.role_name,
            "source": {
                "schema": self.source_schema,
                "table": self.source_table,
                "relation_kind": self.relation_kind,
                "columns": [asdict(column) for column in self.columns],
            },
            "role_flags": {
                "superuser": self.role_superuser,
                "create_database": self.role_create_database,
                "create_role": self.role_create_role,
                "replication": self.role_replication,
                "bypass_rls": self.role_bypass_rls,
                "can_login": self.role_can_login,
            },
            "effective_privileges": {
                "owns_source_table": self.owns_source_table,
                "owns_source_schema": self.owns_source_schema,
                "owns_database": self.owns_database,
                "select": self.can_select,
                "insert": self.can_insert,
                "update": self.can_update,
                "delete": self.can_delete,
                "truncate": self.can_truncate,
                "references": self.can_references,
                "trigger": self.can_trigger,
                "schema_usage": self.schema_usage,
                "schema_create": self.schema_create,
                "schemas_with_create_privilege": self.schemas_with_create_privilege,
                "database_create": self.database_create,
                "database_temporary_objects": self.database_temporary,
                "other_selectable_relations": self.other_selectable_relations,
                "other_owned_relations": self.other_owned_relations,
                "other_owned_objects": self.other_owned_objects,
                "direct_role_memberships": self.direct_role_memberships,
                "privileged_role_memberships": self.privileged_role_memberships,
            },
            "row_level_security": {
                "enabled": self.rls_enabled,
                "forced": self.rls_forced,
                "applies_to_direct_table_access": self.rls_applies_to_direct_table_access,
                "policy_count": self.rls_policy_count,
                "policy_expressions_reviewed": False,
            },
            "read_only_candidate": self.read_only_candidate,
            "limitations": [
                "Catalog privilege checks do not prove the business meaning of columns.",
                "Other readable relation count is metadata only; review any nonzero count against an approved allowlist.",
                "Owned-object count covers PostgreSQL catalog objects, not external systems or grants outside this database.",
                "Any role membership makes the read-only candidate check fail and needs manual review.",
                "RLS policy expressions and data-level behavior are not evaluated by this diagnostic.",
            ],
        }


class StagingCompetencyRepository:
    """Read-only metadata access pending verification of the staging table contract."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def inspect_source(self) -> SourceInspection:
        dsn = self._settings.readonly_dsn
        if not dsn:
            raise DatabaseConfigurationRequired()

        try:
            with psycopg.connect(
                dsn,
                connect_timeout=5,
                options="-c default_transaction_read_only=on",
                row_factory=dict_row,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        """
                        SELECT table_schema, column_name, data_type, udt_name,
                               is_nullable, ordinal_position
                        FROM information_schema.columns
                        WHERE table_name = %s
                          AND table_schema NOT IN ('pg_catalog', 'information_schema')
                          AND (%s IS NULL OR table_schema = %s)
                        ORDER BY table_schema, ordinal_position
                        """,
                        (SOURCE_TABLE, self._settings.staging_schema, self._settings.staging_schema),
                    )
                    rows = cursor.fetchall()

                    schemas = sorted({row["table_schema"] for row in rows})
                    if not schemas:
                        raise SourceTableNotFound()
                    if len(schemas) != 1:
                        raise SourceSchemaAmbiguous(schemas)

                    schema_name = schemas[0]
                    column_rows = [row for row in rows if row["table_schema"] == schema_name]
                    cursor.execute(
                        sql.SQL("SELECT count(*) AS row_count FROM {}.{}").format(
                            sql.Identifier(schema_name), sql.Identifier(SOURCE_TABLE)
                        )
                    )
                    count_row = cursor.fetchone()

                    columns = tuple(
                        ColumnMetadata(
                            column_name=row["column_name"],
                            data_type=row["data_type"],
                            database_type=row["udt_name"],
                            nullable=row["is_nullable"] == "YES",
                            ordinal_position=row["ordinal_position"],
                        )
                        for row in column_rows
                    )
                    return SourceInspection(
                        source_table=SOURCE_TABLE,
                        source_schema=schema_name,
                        row_count=count_row["row_count"],
                        columns=columns,
                    )
        except (DatabaseConfigurationRequired, SourceSchemaAmbiguous, SourceTableNotFound):
            raise
        except psycopg.Error as exc:
            # Never chain driver details into HTTP output; DSNs can include credentials.
            raise DatabaseUnavailable() from None

    def diagnose_access(self) -> StagingAccessDiagnostic:
        """Inspect only PostgreSQL catalogs and effective grants; never reads staging rows."""
        dsn = self._settings.readonly_dsn
        if not dsn:
            raise DatabaseConfigurationRequired()

        try:
            conninfo_to_dict(dsn)
        except (psycopg.ProgrammingError, ValueError, TypeError):
            raise StagingDiagnosticFailure(
                "malformed_dsn", _DIAGNOSTIC_GUIDANCE["malformed_dsn"]
            ) from None

        try:
            with psycopg.connect(
                dsn,
                connect_timeout=5,
                options="-c default_transaction_read_only=on",
                row_factory=dict_row,
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
                    cursor.execute(
                        """
                        SELECT n.nspname AS table_schema, c.oid AS table_oid,
                               c.relkind, c.relowner, c.relrowsecurity, c.relforcerowsecurity,
                               a.attname AS column_name, format_type(a.atttypid, a.atttypmod) AS data_type,
                               t.typname AS database_type, a.attnotnull AS not_null, a.attnum AS ordinal_position
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
                        LEFT JOIN pg_type t ON t.oid = a.atttypid
                        WHERE c.relname = %s
                          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
                          AND (%s IS NULL OR n.nspname = %s)
                          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                        ORDER BY n.nspname, a.attnum
                        """,
                        (SOURCE_TABLE, self._settings.staging_schema, self._settings.staging_schema),
                    )
                    rows = cursor.fetchall()
                    schemas = sorted({row["table_schema"] for row in rows})
                    if not schemas:
                        raise SourceTableNotFound()
                    if len(schemas) != 1:
                        raise SourceSchemaAmbiguous(schemas)
                    schema_name = schemas[0]
                    source_rows = [row for row in rows if row["table_schema"] == schema_name]
                    table_oid = source_rows[0]["table_oid"]

                    cursor.execute(
                        """
                        SELECT current_user AS role_name, r.rolsuper, r.rolcreatedb, r.rolcreaterole,
                               r.rolreplication, r.rolbypassrls, r.rolcanlogin,
                               has_database_privilege(current_user, current_database(), 'CREATE') AS database_create,
                               (SELECT count(*) FROM pg_auth_members m WHERE m.member = r.oid) AS direct_role_memberships,
                               (SELECT count(*) FROM pg_auth_members m JOIN pg_roles parent ON parent.oid = m.roleid
                                WHERE m.member = r.oid AND (parent.rolsuper OR parent.rolcreatedb OR parent.rolcreaterole OR parent.rolbypassrls)) AS privileged_role_memberships
                        FROM pg_roles r WHERE r.rolname = current_user
                        """
                    )
                    role = cursor.fetchone()
                    if role is None:
                        raise psycopg.OperationalError("Connected role metadata is unavailable.")

                    cursor.execute(
                        """
                        SELECT pg_get_userbyid(c.relowner) = current_user AS owns_source_table,
                               has_table_privilege(current_user, c.oid, 'SELECT') AS can_select,
                               has_table_privilege(current_user, c.oid, 'INSERT') AS can_insert,
                               has_table_privilege(current_user, c.oid, 'UPDATE') AS can_update,
                               has_table_privilege(current_user, c.oid, 'DELETE') AS can_delete,
                               has_table_privilege(current_user, c.oid, 'TRUNCATE') AS can_truncate,
                               has_table_privilege(current_user, c.oid, 'REFERENCES') AS can_references,
                               has_table_privilege(current_user, c.oid, 'TRIGGER') AS can_trigger,
                               has_schema_privilege(current_user, n.oid, 'USAGE') AS schema_usage,
                               has_schema_privilege(current_user, n.oid, 'CREATE') AS schema_create,
                               (SELECT count(*) FROM pg_namespace ns
                                WHERE ns.nspname NOT IN ('pg_catalog','information_schema')
                                  AND has_schema_privilege(current_user, ns.oid, 'CREATE')) AS schemas_with_create_privilege,
                               %s::boolean AS database_create,
                               has_database_privilege(current_user, current_database(), 'TEMPORARY') AS database_temporary,
                               c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS rls_forced,
                               (SELECT count(*) FROM pg_policies p WHERE p.schemaname=n.nspname AND p.tablename=c.relname) AS rls_policy_count,
                               (SELECT count(*) FROM pg_class other JOIN pg_namespace other_ns ON other_ns.oid = other.relnamespace
                                WHERE other.relkind IN ('r','p','v','m','f')
                                  AND other_ns.nspname NOT IN ('pg_catalog','information_schema')
                                  AND other.oid <> c.oid
                                  AND has_table_privilege(current_user, other.oid, 'SELECT')) AS other_selectable_relations,
                               pg_get_userbyid(n.nspowner) = current_user AS owns_source_schema,
                               (SELECT d.datdba = (SELECT oid FROM pg_roles WHERE rolname=current_user)
                                FROM pg_database d WHERE d.datname=current_database()) AS owns_database,
                               (SELECT count(*) FROM pg_class owned JOIN pg_namespace owned_ns ON owned_ns.oid = owned.relnamespace
                                WHERE owned.relkind IN ('r','p','v','m','f')
                                  AND owned_ns.nspname NOT IN ('pg_catalog','information_schema')
                                  AND owned.oid <> c.oid AND owned.relowner = (SELECT oid FROM pg_roles WHERE rolname=current_user)) AS other_owned_relations,
                               ((SELECT count(*) FROM pg_class owned JOIN pg_namespace owned_ns ON owned_ns.oid=owned.relnamespace
                                 WHERE owned_ns.nspname NOT IN ('pg_catalog','information_schema') AND owned.oid<>c.oid
                                   AND owned.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
                                + (SELECT count(*) FROM pg_proc p JOIN pg_namespace pn ON pn.oid=p.pronamespace
                                   WHERE pn.nspname NOT IN ('pg_catalog','information_schema')
                                     AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
                                + (SELECT count(*) FROM pg_type ty JOIN pg_namespace tn ON tn.oid=ty.typnamespace
                                   WHERE tn.nspname NOT IN ('pg_catalog','information_schema') AND ty.typtype <> 'p'
                                     AND (ty.typrelid = 0 OR ty.typrelid <> c.oid)
                                     AND ty.typowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
                                + (SELECT count(*) FROM pg_namespace ns WHERE ns.nspname NOT IN ('pg_catalog','information_schema')
                                   AND ns.nspowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))
                                + (SELECT count(*) FROM pg_database d WHERE d.datname<>current_database()
                                   AND d.datdba=(SELECT oid FROM pg_roles WHERE rolname=current_user))) AS other_owned_objects
                        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE c.oid = %s::oid
                        """,
                        (role["database_create"], table_oid),
                    )
                    privileges = cursor.fetchone()
                    if privileges is None:
                        raise SourceTableNotFound()

                    columns = tuple(
                        ColumnMetadata(
                            column_name=row["column_name"],
                            data_type=row["data_type"],
                            database_type=row["database_type"],
                            nullable=not row["not_null"],
                            ordinal_position=row["ordinal_position"],
                        )
                        for row in source_rows
                        if row["column_name"] is not None
                    )
                    return StagingAccessDiagnostic(
                        role_name=role["role_name"],
                        source_table=SOURCE_TABLE,
                        source_schema=schema_name,
                        relation_kind=source_rows[0]["relkind"],
                        columns=columns,
                        role_superuser=role["rolsuper"],
                        role_create_database=role["rolcreatedb"],
                        role_create_role=role["rolcreaterole"],
                        role_replication=role["rolreplication"],
                        role_bypass_rls=role["rolbypassrls"],
                        role_can_login=role["rolcanlogin"],
                        owns_source_table=privileges["owns_source_table"],
                        owns_source_schema=privileges["owns_source_schema"],
                        owns_database=privileges["owns_database"],
                        can_select=privileges["can_select"],
                        can_insert=privileges["can_insert"],
                        can_update=privileges["can_update"],
                        can_delete=privileges["can_delete"],
                        can_truncate=privileges["can_truncate"],
                        can_references=privileges["can_references"],
                        can_trigger=privileges["can_trigger"],
                        schema_usage=privileges["schema_usage"],
                        schema_create=privileges["schema_create"],
                        schemas_with_create_privilege=privileges["schemas_with_create_privilege"],
                        database_create=privileges["database_create"],
                        database_temporary=privileges["database_temporary"],
                        rls_enabled=privileges["rls_enabled"],
                        rls_forced=privileges["rls_forced"],
                        rls_policy_count=privileges["rls_policy_count"],
                        other_selectable_relations=privileges["other_selectable_relations"],
                        other_owned_relations=privileges["other_owned_relations"],
                        other_owned_objects=privileges["other_owned_objects"],
                        direct_role_memberships=role["direct_role_memberships"],
                        privileged_role_memberships=role["privileged_role_memberships"],
                    )
        except (DatabaseConfigurationRequired, SourceSchemaAmbiguous, SourceTableNotFound):
            raise
        except psycopg.Error as exc:
            # Driver exceptions may include DSNs, SQL, or database identifiers.
            category = _diagnostic_failure_category(exc)
            raise StagingDiagnosticFailure(category, _DIAGNOSTIC_GUIDANCE[category]) from None


def get_repository() -> StagingCompetencyRepository:
    return StagingCompetencyRepository()
