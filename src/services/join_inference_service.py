from dataclasses import dataclass
from typing import List

from src.database.schema_loader import DatabaseSchema


@dataclass(frozen=True)
class JoinCandidate:
    left_table: str
    right_table: str
    condition: str
    confidence: str
    reason: str


class JoinInferenceService:
    common_key_suffixes = ("_id",)

    def infer(self, schema: DatabaseSchema, left_table: str, right_table: str) -> List[JoinCandidate]:
        left = schema.get_table(left_table)
        right = schema.get_table(right_table)
        if not left or not right:
            return []

        candidates: List[JoinCandidate] = []

        for fk in left.foreign_keys:
            if fk.references_table == right.name:
                candidates.append(
                    JoinCandidate(
                        left_table=left.name,
                        right_table=right.name,
                        condition=f"{left.name}.{fk.column} = {right.name}.{fk.references_column}",
                        confidence="high",
                        reason="Explicit foreign key relationship.",
                    )
                )

        for fk in right.foreign_keys:
            if fk.references_table == left.name:
                candidates.append(
                    JoinCandidate(
                        left_table=left.name,
                        right_table=right.name,
                        condition=f"{right.name}.{fk.column} = {left.name}.{fk.references_column}",
                        confidence="high",
                        reason="Explicit foreign key relationship.",
                    )
                )

        left_columns = set(left.column_names())
        right_columns = set(right.column_names())
        for column in sorted(left_columns & right_columns):
            if column == "id":
                continue
            if column.endswith(self.common_key_suffixes):
                candidates.append(
                    JoinCandidate(
                        left_table=left.name,
                        right_table=right.name,
                        condition=f"{left.name}.{column} = {right.name}.{column}",
                        confidence="medium",
                        reason="Matching identifier column name.",
                    )
                )

        if left.primary_key:
            expected = f"{left.name.rstrip('s')}_id"
            if expected in right_columns:
                candidates.append(
                    JoinCandidate(
                        left_table=left.name,
                        right_table=right.name,
                        condition=f"{right.name}.{expected} = {left.name}.{left.primary_key}",
                        confidence="medium",
                        reason="Common foreign-key naming pattern.",
                    )
                )

        if right.primary_key:
            expected = f"{right.name.rstrip('s')}_id"
            if expected in left_columns:
                candidates.append(
                    JoinCandidate(
                        left_table=left.name,
                        right_table=right.name,
                        condition=f"{left.name}.{expected} = {right.name}.{right.primary_key}",
                        confidence="medium",
                        reason="Common foreign-key naming pattern.",
                    )
                )

        return self._dedupe(candidates)

    def _dedupe(self, candidates: List[JoinCandidate]) -> List[JoinCandidate]:
        seen = set()
        unique = []
        for candidate in candidates:
            key = candidate.condition
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique
