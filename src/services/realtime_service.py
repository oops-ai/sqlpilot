import json
from typing import Iterator

from src.services.connection_service import ConnectionService


class RealtimeService:
    channel = "ai_sql_copilot_changes"

    def __init__(self, connection_service: ConnectionService):
        self.connection_service = connection_service

    def stream_database_events(self, connection_id: str) -> Iterator[str]:
        connection = self.connection_service.connect(connection_id)
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(f"LISTEN {self.channel}")
            yield self._event("connected", {"channel": self.channel})

            while True:
                received = False
                for notify in connection.notifies(timeout=10, stop_after=1):
                    received = True
                    yield self._event("database_change", self._payload(notify.payload))
                if not received:
                    yield self._event("heartbeat", {"channel": self.channel})
        finally:
            connection.close()

    def _event(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"

    def _payload(self, value: str) -> dict:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"message": value}
