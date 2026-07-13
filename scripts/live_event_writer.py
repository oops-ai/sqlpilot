#!/usr/bin/env python3
"""
Insert synthetic live events into the demo PostgreSQL database.

The imported Olist database gets a small `demo_live_events` table and trigger.
Each insert will emit a NOTIFY event that the existing SSE stream can observe.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict


DEFAULT_DSN = os.getenv("DEMO_LIVE_DATABASE_URL") or os.getenv("DATABASE_URL") or "postgresql://postgres@127.0.0.1:5432/ai_sql_copilot_demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write synthetic live demo events.")
    parser.add_argument("--dsn", default=DEFAULT_DSN, help="PostgreSQL DSN for the demo data database.")
    parser.add_argument("--count", type=int, default=1, help="Number of events to insert.")
    parser.add_argument("--interval-seconds", type=float, default=0.0, help="Sleep between inserts.")
    parser.add_argument("--watch", action="store_true", help="Keep inserting events forever.")
    return parser.parse_args()


def create_table(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS demo_live_events (
                id BIGSERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value NUMERIC NOT NULL,
                payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS demo_live_events_created_at_idx ON demo_live_events (created_at DESC)"
        )


def ensure_triggers(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE OR REPLACE FUNCTION notify_ai_sql_copilot_change()
            RETURNS TRIGGER AS $$
            DECLARE
                payload JSONB;
            BEGIN
                payload = jsonb_build_object(
                    'table', TG_TABLE_NAME,
                    'operation', TG_OP,
                    'record', to_jsonb(COALESCE(NEW, OLD)),
                    'changed_at', NOW()
                );

                PERFORM pg_notify('ai_sql_copilot_changes', payload::TEXT);
                RETURN COALESCE(NEW, OLD);
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        cursor.execute("DROP TRIGGER IF EXISTS notify_demo_live_events_change ON demo_live_events")
        cursor.execute(
            """
            CREATE TRIGGER notify_demo_live_events_change
            AFTER INSERT OR UPDATE OR DELETE ON demo_live_events
            FOR EACH ROW EXECUTE FUNCTION notify_ai_sql_copilot_change()
            """
        )


def build_event(index: int) -> Dict[str, object]:
    source = random.choice(["olist_orders", "olist_order_items", "olist_order_payments", "olist_order_reviews"])
    event_type = random.choice(["insert", "update", "metric"])
    metric_name = random.choice(["order_volume", "avg_basket_size", "review_score", "payment_value"])
    metric_value = round(random.uniform(1, 1000), 2)
    return {
        "event_type": event_type,
        "source": source,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "payload": {
            "sequence": index,
            "note": f"{metric_name} refreshed at {datetime.now(timezone.utc).isoformat()}",
        },
    }


def insert_event(connection, payload: Dict[str, object]) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO demo_live_events (event_type, source, metric_name, metric_value, payload)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                payload["event_type"],
                payload["source"],
                payload["metric_name"],
                payload["metric_value"],
                json.dumps(payload["payload"]),
            ),
        )


def main() -> None:
    args = parse_args()
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment issue
        raise SystemExit("psycopg is required. Install dependencies first.") from exc

    connection = psycopg.connect(args.dsn)
    try:
        with connection.transaction():
            create_table(connection)
            ensure_triggers(connection)

        iteration = 0
        while True:
            iteration += 1
            with connection.transaction():
                insert_event(connection, build_event(iteration))
            print(f"Inserted demo_live_events row #{iteration}")
            if not args.watch and iteration >= args.count:
                break
            if args.interval_seconds > 0:
                time.sleep(args.interval_seconds)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
