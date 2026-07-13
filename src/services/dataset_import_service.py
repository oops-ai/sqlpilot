from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass
class ImportedDataset:
    connection_id: str
    table_name: str
    row_count: int
    column_count: int
    columns: List[str]
    source_type: str
    schema: Dict[str, Any]


class DatasetImportService:
    def __init__(self, connection_service, schema_service, preference_service=None):
        self.connection_service = connection_service
        self.schema_service = schema_service
        self.preference_service = preference_service

    def import_dataset(
        self,
        connection_id: str,
        *,
        csv_text: str = "",
        source_url: str = "",
        file_name: str = "",
        table_name: str = "",
        replace: bool = False,
    ) -> ImportedDataset:
        if not csv_text and not source_url:
            raise ValueError("Provide either csv_text or source_url.")

        if source_url:
            source_text = self._fetch_url(source_url)
            source_type = "url"
            source_label = source_url
        else:
            source_text = csv_text
            source_type = "csv"
            source_label = file_name or table_name or "uploaded_csv"

        normalized_source = source_text.lstrip("\ufeff").strip()
        if not normalized_source:
            raise ValueError("CSV content is empty.")

        rows, headers = self._read_csv(normalized_source)
        if not headers:
            raise ValueError("CSV header row is missing.")

        target_table = self._build_table_name(table_name or source_label, explicit=bool(table_name))
        inferred_columns = self._infer_columns(headers, rows)

        connection = self.connection_service.connect(connection_id)
        try:
            try:
                self._create_table(connection, target_table, inferred_columns, replace=replace)
                self._insert_rows(connection, target_table, inferred_columns, rows)
                connection.commit()
            except Exception:
                rollback = getattr(connection, "rollback", None)
                if rollback:
                    rollback()
                raise
        finally:
            close = getattr(connection, "close", None)
            if close:
                close()

        schema = self.schema_service.refresh(connection_id)
        if self.preference_service:
            self.preference_service.set("recent_imported_table", target_table)
        if getattr(self.connection_service, "storage", None):
            self.connection_service.storage.register_imported_dataset(connection_id, target_table, source_type)
        return ImportedDataset(
            connection_id=connection_id,
            table_name=target_table,
            row_count=len(rows),
            column_count=len(inferred_columns),
            columns=[column_name for column_name, _ in inferred_columns],
            source_type=source_type,
            schema=schema.to_dict(),
        )

    def _fetch_url(self, source_url: str) -> str:
        try:
            with urlopen(source_url, timeout=30.0) as response:  # nosec B310 - user supplied import source
                content_type = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(content_type, errors="replace")
        except OSError as exc:
            raise ValueError(f"Could not fetch CSV from URL: {exc}") from exc

    def _read_csv(self, csv_text: str) -> Tuple[List[Dict[str, str]], List[str]]:
        reader = csv.DictReader(io.StringIO(csv_text))
        headers = self._unique_identifiers([self._normalize_identifier(name) for name in (reader.fieldnames or [])])
        rows: List[Dict[str, str]] = []
        for raw_row in reader:
            row: Dict[str, str] = {}
            for index, header in enumerate(headers):
                original_key = reader.fieldnames[index]
                value = raw_row.get(original_key, "")
                row[header] = "" if value is None else str(value).strip()
            if any(value for value in row.values()):
                rows.append(row)
        return rows, headers

    def _infer_columns(self, headers: Sequence[str], rows: Sequence[Dict[str, str]]) -> List[Tuple[str, str]]:
        columns: List[Tuple[str, str]] = []
        for header in headers:
            values = [row.get(header, "") for row in rows]
            columns.append((header, self._infer_type(header, values)))
        return columns

    def _infer_type(self, header: str, values: Iterable[str]) -> str:
        non_empty = [value for value in values if value not in {"", None}]
        if not non_empty:
            return "TEXT"
        if header == "id" or header.endswith("_id"):
            return "TEXT"

        if self._all_match(non_empty, self._is_integer):
            return "INTEGER"
        if self._all_match(non_empty, self._is_numeric):
            return "NUMERIC"
        if self._all_match(non_empty, self._is_boolean):
            return "BOOLEAN"
        if self._all_match(non_empty, self._is_timestamp):
            return "TIMESTAMP"
        return "TEXT"

    def _all_match(self, values: Sequence[str], predicate) -> bool:
        return all(predicate(value) for value in values)

    def _is_integer(self, value: str) -> bool:
        try:
            int(value)
            return True
        except (TypeError, ValueError):
            return False

    def _is_numeric(self, value: str) -> bool:
        try:
            Decimal(value)
            return True
        except (InvalidOperation, TypeError, ValueError):
            return False

    def _is_boolean(self, value: str) -> bool:
        return value.strip().lower() in {"true", "false", "t", "f", "yes", "no"}

    def _is_timestamp(self, value: str) -> bool:
        normalized = value.strip().replace("Z", "+00:00")
        try:
            datetime.fromisoformat(normalized)
            return True
        except ValueError:
            return False

    def _create_table(self, connection, table_name: str, columns: Sequence[Tuple[str, str]], *, replace: bool) -> None:
        quoted_table = self._quote_identifier(table_name)
        column_sql = ", ".join(f"{self._quote_identifier(name)} {sql_type}" for name, sql_type in columns)
        with connection.cursor() as cursor:
            if replace:
                cursor.execute(f'DROP TABLE IF EXISTS {quoted_table}')
            cursor.execute(f"CREATE TABLE IF NOT EXISTS {quoted_table} ({column_sql})")

    def _insert_rows(self, connection, table_name: str, columns: Sequence[Tuple[str, str]], rows: Sequence[Dict[str, str]]) -> None:
        if not rows:
            return

        quoted_table = self._quote_identifier(table_name)
        column_names = [name for name, _ in columns]
        placeholders = ", ".join(["%s"] * len(column_names))
        quoted_columns = ", ".join(self._quote_identifier(name) for name in column_names)
        sql = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"
        values = [tuple(self._coerce_value(row.get(name, ""), sql_type) for name, sql_type in columns) for row in rows]
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)

    def _coerce_value(self, value: str, sql_type: str) -> Any:
        if value in {"", None}:
            return None
        if sql_type == "INTEGER":
            return int(value)
        if sql_type == "NUMERIC":
            return Decimal(value)
        if sql_type == "BOOLEAN":
            return value.strip().lower() in {"true", "t", "yes", "1"}
        return value

    def _build_table_name(self, source_name: str, explicit: bool = False) -> str:
        raw_source = str(source_name)
        if "://" in raw_source:
            parsed = urlparse(raw_source)
            stem = Path(parsed.path).stem or "imported_dataset"
        else:
            stem = Path(raw_source).stem or "imported_dataset"
        normalized = self._normalize_identifier(stem)
        if not normalized:
            normalized = "imported_dataset"
        if not explicit and not normalized.startswith("imported_"):
            normalized = f"imported_{normalized}"
        return normalized[:63]

    def _normalize_identifier(self, value: str) -> str:
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
        if not normalized:
            return ""
        if normalized[0].isdigit():
            normalized = f"_{normalized}"
        return normalized

    def _quote_identifier(self, value: str) -> str:
        return '"' + value.replace('"', '""') + '"'

    def _unique_identifiers(self, values: Sequence[str]) -> List[str]:
        seen: Dict[str, int] = {}
        unique: List[str] = []
        for value in values:
            base = value or "column"
            count = seen.get(base, 0)
            seen[base] = count + 1
            unique.append(base if count == 0 else f"{base}_{count + 1}")
        return unique

    def cleanup_imported_datasets(self, connection_id: Optional[str] = None) -> List[str]:
        if not getattr(self.connection_service, "storage", None):
            return []

        records = self.connection_service.storage.list_imported_datasets(connection_id)
        dropped_tables: List[str] = []
        grouped: Dict[str, List[str]] = {}
        for record in records:
            grouped.setdefault(record["connection_id"], []).append(record["table_name"])

        for current_connection_id, table_names in grouped.items():
            connection = self.connection_service.connect(current_connection_id)
            try:
                with connection.cursor() as cursor:
                    for table_name in table_names:
                        cursor.execute(f'DROP TABLE IF EXISTS {self._quote_identifier(table_name)}')
                        dropped_tables.append(table_name)
                connection.commit()
            except Exception:
                rollback = getattr(connection, "rollback", None)
                if rollback:
                    rollback()
                raise
            finally:
                close = getattr(connection, "close", None)
                if close:
                    close()

        self.connection_service.storage.clear_imported_datasets(connection_id)
        if self.preference_service and (connection_id is None or connection_id):
            self.preference_service.set("recent_imported_table", "")
        return dropped_tables


def to_dict(imported: ImportedDataset) -> Dict[str, Any]:
    return asdict(imported)
