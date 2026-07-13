from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from src.services.app_storage import AppStorage


def _parse_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


@dataclass
class UserPreference:
    preference_key: str
    preference_value: str
    updated_at: datetime


class PreferenceService:
    def __init__(self, storage: Optional[AppStorage] = None):
        self.storage = storage
        self._preferences: Dict[str, UserPreference] = {}

    def set(self, key: str, value: str) -> UserPreference:
        preference = UserPreference(key, value, datetime.utcnow())
        if self.storage:
            self.storage.execute(
                """
                INSERT INTO user_preferences (preference_key, preference_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(preference_key) DO UPDATE SET
                    preference_value = excluded.preference_value,
                    updated_at = excluded.updated_at
                """,
                (key, value, preference.updated_at.isoformat()),
            )
        else:
            self._preferences[key] = preference
        return preference

    def get(self, key: str) -> str:
        if self.storage:
            row = self.storage.fetchone(
                "SELECT preference_value FROM user_preferences WHERE preference_key = ?",
                (key,),
            )
            return row["preference_value"] if row else ""
        preference = self._preferences.get(key)
        return preference.preference_value if preference else ""

    def all(self) -> List[UserPreference]:
        if self.storage:
            rows = self.storage.fetchall("SELECT * FROM user_preferences ORDER BY preference_key")
            return [
                UserPreference(
                    preference_key=row["preference_key"],
                    preference_value=row["preference_value"],
                    updated_at=_parse_datetime(row["updated_at"]),
                )
                for row in rows
            ]
        return list(self._preferences.values())
