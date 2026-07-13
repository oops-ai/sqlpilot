#!/usr/bin/env python3
"""
Import the Kaggle Olist ecommerce dataset into PostgreSQL.

Usage:
  python3 scripts/import_olist_dataset.py --source /path/to/brazilian-ecommerce.zip
  python3 scripts/import_olist_dataset.py --source /path/to/extracted_folder --replace

The script expects the standard Olist CSV filenames and loads them into
`olist_*` tables with real keys, timestamps, and numeric columns.
"""

from __future__ import annotations

import argparse
import csv
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_DSN = os.getenv("OLIST_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql://postgres@127.0.0.1:5432/ai_sql_copilot"


@dataclass(frozen=True)
class TableSpec:
    name: str
    source_file: str
    columns: Sequence[Tuple[str, str]]
    primary_key: Optional[Sequence[str]] = None
    create_foreign_keys: Sequence[str] = ()
    indexes: Sequence[str] = ()


TABLES: Sequence[TableSpec] = (
    TableSpec(
        name="olist_customers",
        source_file="olist_customers_dataset.csv",
        columns=(
            ("customer_id", "TEXT"),
            ("customer_unique_id", "TEXT"),
            ("customer_zip_code_prefix", "INTEGER"),
            ("customer_city", "TEXT"),
            ("customer_state", "TEXT"),
        ),
        primary_key=("customer_id",),
        indexes=("customer_zip_code_prefix",),
    ),
    TableSpec(
        name="olist_geolocation",
        source_file="olist_geolocation_dataset.csv",
        columns=(
            ("geolocation_zip_code_prefix", "INTEGER"),
            ("geolocation_lat", "NUMERIC"),
            ("geolocation_lng", "NUMERIC"),
            ("geolocation_city", "TEXT"),
            ("geolocation_state", "TEXT"),
        ),
        indexes=("geolocation_zip_code_prefix", "geolocation_state"),
    ),
    TableSpec(
        name="olist_orders",
        source_file="olist_orders_dataset.csv",
        columns=(
            ("order_id", "TEXT"),
            ("customer_id", "TEXT"),
            ("order_status", "TEXT"),
            ("order_purchase_timestamp", "TIMESTAMP"),
            ("order_approved_at", "TIMESTAMP"),
            ("order_delivered_carrier_date", "TIMESTAMP"),
            ("order_delivered_customer_date", "TIMESTAMP"),
            ("order_estimated_delivery_date", "TIMESTAMP"),
        ),
        primary_key=("order_id",),
        create_foreign_keys=(
            "ALTER TABLE olist_orders ADD CONSTRAINT olist_orders_customer_fk FOREIGN KEY (customer_id) REFERENCES olist_customers(customer_id)",
        ),
        indexes=("customer_id", "order_purchase_timestamp", "order_status"),
    ),
    TableSpec(
        name="olist_products",
        source_file="olist_products_dataset.csv",
        columns=(
            ("product_id", "TEXT"),
            ("product_category_name", "TEXT"),
            ("product_name_lenght", "INTEGER"),
            ("product_description_lenght", "INTEGER"),
            ("product_photos_qty", "INTEGER"),
            ("product_weight_g", "INTEGER"),
            ("product_length_cm", "INTEGER"),
            ("product_height_cm", "INTEGER"),
            ("product_width_cm", "INTEGER"),
        ),
        primary_key=("product_id",),
        indexes=("product_category_name",),
    ),
    TableSpec(
        name="olist_sellers",
        source_file="olist_sellers_dataset.csv",
        columns=(
            ("seller_id", "TEXT"),
            ("seller_zip_code_prefix", "INTEGER"),
            ("seller_city", "TEXT"),
            ("seller_state", "TEXT"),
        ),
        primary_key=("seller_id",),
        indexes=("seller_zip_code_prefix", "seller_state"),
    ),
    TableSpec(
        name="olist_order_items",
        source_file="olist_order_items_dataset.csv",
        columns=(
            ("order_id", "TEXT"),
            ("order_item_id", "INTEGER"),
            ("product_id", "TEXT"),
            ("seller_id", "TEXT"),
            ("shipping_limit_date", "TIMESTAMP"),
            ("price", "NUMERIC"),
            ("freight_value", "NUMERIC"),
        ),
        primary_key=("order_id", "order_item_id"),
        create_foreign_keys=(
            "ALTER TABLE olist_order_items ADD CONSTRAINT olist_order_items_order_fk FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)",
            "ALTER TABLE olist_order_items ADD CONSTRAINT olist_order_items_product_fk FOREIGN KEY (product_id) REFERENCES olist_products(product_id)",
            "ALTER TABLE olist_order_items ADD CONSTRAINT olist_order_items_seller_fk FOREIGN KEY (seller_id) REFERENCES olist_sellers(seller_id)",
        ),
        indexes=("order_id", "product_id", "seller_id"),
    ),
    TableSpec(
        name="olist_order_payments",
        source_file="olist_order_payments_dataset.csv",
        columns=(
            ("order_id", "TEXT"),
            ("payment_sequential", "INTEGER"),
            ("payment_type", "TEXT"),
            ("payment_installments", "INTEGER"),
            ("payment_value", "NUMERIC"),
        ),
        primary_key=("order_id", "payment_sequential"),
        create_foreign_keys=(
            "ALTER TABLE olist_order_payments ADD CONSTRAINT olist_order_payments_order_fk FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)",
        ),
        indexes=("order_id", "payment_type"),
    ),
    TableSpec(
        name="olist_order_reviews",
        source_file="olist_order_reviews_dataset.csv",
        columns=(
            ("review_id", "TEXT"),
            ("order_id", "TEXT"),
            ("review_score", "INTEGER"),
            ("review_comment_title", "TEXT"),
            ("review_comment_message", "TEXT"),
            ("review_creation_date", "TIMESTAMP"),
            ("review_answer_timestamp", "TIMESTAMP"),
        ),
        primary_key=("review_id",),
        create_foreign_keys=(
            "ALTER TABLE olist_order_reviews ADD CONSTRAINT olist_order_reviews_order_fk FOREIGN KEY (order_id) REFERENCES olist_orders(order_id)",
        ),
        indexes=("order_id", "review_score"),
    ),
    TableSpec(
        name="olist_product_category_translations",
        source_file="product_category_name_translation.csv",
        columns=(
            ("product_category_name", "TEXT"),
            ("product_category_name_english", "TEXT"),
        ),
        primary_key=("product_category_name",),
        indexes=("product_category_name_english",),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import the Kaggle Olist dataset into PostgreSQL.")
    parser.add_argument("--source", required=True, help="Path to the Kaggle zip file or extracted dataset folder.")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL DSN for the target database.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Truncate existing Olist tables before loading new rows.",
    )
    return parser.parse_args()


def resolve_dataset_root(source: Path) -> Path:
    if source.is_dir():
        return source

    if source.is_file() and source.suffix.lower() == ".zip":
        temp_dir = Path(tempfile.mkdtemp(prefix="olist_dataset_"))
        with zipfile.ZipFile(source) as archive:
            archive.extractall(temp_dir)
        return temp_dir

    raise SystemExit(f"Unsupported source path: {source}")


def find_csv_file(root: Path, filename: str) -> Path:
    matches = list(root.rglob(filename))
    if not matches:
        raise SystemExit(f"Could not find {filename} under {root}")
    return matches[0]


def create_tables(connection) -> None:
    with connection.cursor() as cursor:
        for spec in TABLES:
            column_sql = ",\n                ".join(f"{name} {column_type}" for name, column_type in spec.columns)
            pk_sql = ""
            if spec.primary_key:
                pk_columns = ", ".join(spec.primary_key)
                pk_sql = f",\n                PRIMARY KEY ({pk_columns})"
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {spec.name} (
                    {column_sql}
                    {pk_sql}
                )
                """
            )

        for spec in TABLES:
            for index_column in spec.indexes:
                index_name = f"{spec.name}_{index_column}_idx"
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {spec.name} ({index_column})"
                )


def truncate_tables(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            TRUNCATE TABLE
                olist_order_reviews,
                olist_order_payments,
                olist_order_items,
                olist_orders,
                olist_sellers,
                olist_products,
                olist_customers,
                olist_geolocation,
                olist_product_category_translations
            CASCADE
            """
        )


def ensure_foreign_keys(connection) -> None:
    with connection.cursor() as cursor:
        for spec in TABLES:
            for statement in spec.create_foreign_keys:
                constraint_name = statement.split("CONSTRAINT", 1)[1].split()[0] if "CONSTRAINT" in statement else None
                if constraint_name:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = %s
                        """,
                        (constraint_name,),
                    )
                    if cursor.fetchone():
                        continue
                cursor.execute(statement)


def load_table(connection, spec: TableSpec, csv_path: Path) -> int:
    with connection.cursor() as cursor:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            expected = [column for column, _ in spec.columns]
            if reader.fieldnames != expected:
                missing = [column for column in expected if column not in (reader.fieldnames or [])]
                if missing:
                    raise SystemExit(
                        f"{csv_path.name} does not match expected columns for {spec.name}: {missing}"
                    )

            inserted = 0
            with cursor.copy(
                f"COPY {spec.name} ({', '.join(expected)}) FROM STDIN"
            ) as copy:
                for row in reader:
                    copy.write_row([row[column] or None for column in expected])
                    inserted += 1
            return inserted


def main() -> None:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    dataset_root = resolve_dataset_root(source)

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment issue
        raise SystemExit("psycopg is required. Install dependencies first.") from exc

    connection = psycopg.connect(args.dsn)
    try:
        with connection.transaction():
            create_tables(connection)
            if args.replace:
                truncate_tables(connection)

            loaded_counts = {}
            for spec in TABLES:
                csv_path = find_csv_file(dataset_root, spec.source_file)
                loaded_counts[spec.name] = load_table(connection, spec, csv_path)

            ensure_foreign_keys(connection)
            with connection.cursor() as cursor:
                for spec in TABLES:
                    cursor.execute(f"ANALYZE {spec.name}")

        print("Loaded Olist dataset:")
        for table_name, count in loaded_counts.items():
            print(f"  {table_name}: {count} rows")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
