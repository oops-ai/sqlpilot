#!/bin/sh
set -eu

PSQL="/Applications/Postgres.app/Contents/Versions/18/bin/psql"
DATABASE="${1:-ai_sql_copilot}"

if [ ! -x "$PSQL" ]; then
  echo "psql not found at $PSQL"
  exit 1
fi

for migration in migrations/*.sql; do
  echo "Applying $migration"
  "$PSQL" -h 127.0.0.1 -p 5432 -U schava -d "$DATABASE" -f "$migration"
done
