from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    data_type: str = "unknown"
    sensitive: bool = False
    nullable: bool = True


@dataclass(frozen=True)
class ForeignKeyInfo:
    column: str
    references_table: str
    references_column: str


@dataclass(frozen=True)
class IndexInfo:
    name: str
    columns: List[str]
    unique: bool = False


@dataclass
class TableInfo:
    name: str
    columns: List[ColumnInfo] = field(default_factory=list)
    primary_key: Optional[str] = None
    foreign_keys: List[ForeignKeyInfo] = field(default_factory=list)
    indexes: List[IndexInfo] = field(default_factory=list)

    def column_names(self) -> List[str]:
        return [column.name for column in self.columns]


@dataclass
class DatabaseSchema:
    tables: Dict[str, TableInfo] = field(default_factory=dict)

    @classmethod
    def from_tables(cls, tables: Iterable[TableInfo]) -> "DatabaseSchema":
        return cls({table.name: table for table in tables})

    def get_table(self, name: str) -> Optional[TableInfo]:
        return self.tables.get(name)

    def table_names(self) -> List[str]:
        return list(self.tables.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {"tables": {name: asdict(table) for name, table in self.tables.items()}}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "DatabaseSchema":
        tables = []
        for table_name, table_payload in payload.get("tables", {}).items():
            columns = [ColumnInfo(**column) for column in table_payload.get("columns", [])]
            foreign_keys = [ForeignKeyInfo(**fk) for fk in table_payload.get("foreign_keys", [])]
            indexes = [IndexInfo(**index) for index in table_payload.get("indexes", [])]
            tables.append(
                TableInfo(
                    name=table_payload.get("name", table_name),
                    columns=columns,
                    primary_key=table_payload.get("primary_key"),
                    foreign_keys=foreign_keys,
                    indexes=indexes,
                )
            )
        return cls.from_tables(tables)

    def find_table_for_request(self, request: str, preferred_table_name: Optional[str] = None) -> Optional[TableInfo]:
        normalized = request.lower()
        for table in self.tables.values():
            table_tokens = {table.name.lower(), table.name.lower().rstrip("s")}
            if any(token and token in normalized for token in table_tokens):
                return table
        if preferred_table_name:
            preferred = self.get_table(preferred_table_name)
            if preferred:
                return preferred
        return next(iter(self.tables.values()), None)

    def find_join(self, left_table: str, right_table: str) -> Optional[str]:
        left = self.get_table(left_table)
        right = self.get_table(right_table)
        if not left or not right:
            return None

        for fk in left.foreign_keys:
            if fk.references_table == right.name:
                return f"{left.name}.{fk.column} = {right.name}.{fk.references_column}"

        for fk in right.foreign_keys:
            if fk.references_table == left.name:
                return f"{right.name}.{fk.column} = {left.name}.{fk.references_column}"

        left_columns = set(left.column_names())
        right_columns = set(right.column_names())
        for column in sorted(left_columns & right_columns):
            if column.endswith("_id") or column == "id":
                return f"{left.name}.{column} = {right.name}.{column}"

        return None


SENSITIVE_COLUMN_NAMES = {
    "email",
    "phone",
    "address",
    "ssn",
    "password",
    "token",
    "api_key",
    "credit_card",
    "salary",
    "date_of_birth",
}


def mark_sensitive_columns(table: TableInfo) -> TableInfo:
    columns = [
        ColumnInfo(
            name=column.name,
            data_type=column.data_type,
            sensitive=column.sensitive or column.name.lower() in SENSITIVE_COLUMN_NAMES,
            nullable=column.nullable,
        )
        for column in table.columns
    ]
    return TableInfo(
        name=table.name,
        columns=columns,
        primary_key=table.primary_key,
        foreign_keys=table.foreign_keys,
        indexes=table.indexes,
    )


class PostgresSchemaLoader:
    def load(self, connection: Any) -> DatabaseSchema:
        columns_by_table: Dict[str, List[ColumnInfo]] = {}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
                """
            )
            for table_name, column_name, data_type, is_nullable in cursor.fetchall():
                columns_by_table.setdefault(table_name, []).append(
                    ColumnInfo(
                        name=column_name,
                        data_type=data_type,
                        nullable=is_nullable == "YES",
                    )
                )

            cursor.execute(
                """
                SELECT tc.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = 'public'
                """
            )
            primary_keys = {table: column for table, column in cursor.fetchall()}

            cursor.execute(
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
                """
            )
            fks_by_table: Dict[str, List[ForeignKeyInfo]] = {}
            for table, column, ref_table, ref_column in cursor.fetchall():
                fks_by_table.setdefault(table, []).append(ForeignKeyInfo(column, ref_table, ref_column))

            cursor.execute(
                """
                SELECT
                    t.relname AS table_name,
                    i.relname AS index_name,
                    ix.indisunique AS is_unique,
                    array_agg(a.attname ORDER BY array_position(ix.indkey, a.attnum)) AS columns
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = 'public'
                GROUP BY t.relname, i.relname, ix.indisunique
                """
            )
            indexes_by_table: Dict[str, List[IndexInfo]] = {}
            for table, index_name, unique, index_columns in cursor.fetchall():
                indexes_by_table.setdefault(table, []).append(IndexInfo(index_name, list(index_columns), unique))

        tables = []
        for table_name, columns in columns_by_table.items():
            table = TableInfo(
                name=table_name,
                columns=columns,
                primary_key=primary_keys.get(table_name),
                foreign_keys=fks_by_table.get(table_name, []),
                indexes=indexes_by_table.get(table_name, []),
            )
            tables.append(mark_sensitive_columns(table))
        return DatabaseSchema.from_tables(tables)
