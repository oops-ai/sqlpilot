#!/usr/bin/env python3
"""
Seed a public-demo connection profile into the app metadata database.

Usage:
  python3 scripts/seed_public_demo.py --app-dsn postgresql://... \
    --name "Olist Demo" --host <host> --database <db> --username <user>
"""

from __future__ import annotations

import argparse
import os

from src.services.app_storage import AppStorage
from src.services.connection_service import ConnectionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a public demo connection profile.")
    parser.add_argument("--app-dsn", required=True, help="PostgreSQL DSN for the app metadata database.")
    parser.add_argument("--name", required=True, help="Display name for the connection.")
    parser.add_argument("--host", required=True, help="Target Postgres host.")
    parser.add_argument("--database", required=True, help="Target database name.")
    parser.add_argument("--username", required=True, help="Target database username.")
    parser.add_argument("--port", type=int, default=5432, help="Target database port.")
    parser.add_argument(
        "--password-env-var",
        default="",
        help="Environment variable name containing the target database password.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    storage = AppStorage(args.app_dsn)
    connections = ConnectionService(storage)

    existing = next((connection for connection in connections.list() if connection.name == args.name), None)
    if existing:
        print(f"Connection profile already exists: {existing.name} ({existing.id})")
        return

    created = connections.create(
        name=args.name,
        host=args.host,
        port=args.port,
        database_name=args.database,
        username=args.username,
        password_env_var=args.password_env_var or None,
    )
    print(f"Created connection profile: {created.name} ({created.id})")


if __name__ == "__main__":
    main()
