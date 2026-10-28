from __future__ import annotations

from dataclasses import asdict, dataclass

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from .config import Settings, get_settings
from .errors import (
    DatabaseConfigurationRequired,
    DatabaseUnavailable,
    SourceSchemaAmbiguous,
    SourceTableNotFound,
)

SOURCE_TABLE = "staging_company_skill_levels"


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
            "source_table": self.source_table,
            "source_schema": self.source_schema,
            "row_count": self.row_count,
            "columns": [asdict(column) for column in self.columns],
            "competencies_available": False,
            "readiness_scoring_available": False,
            "reason": "The source columns and category mapping require review before competency values can be exposed.",
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


def get_repository() -> StagingCompetencyRepository:
    return StagingCompetencyRepository()
