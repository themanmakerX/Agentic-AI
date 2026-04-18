"""Graph domain models."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(slots=True)
class BuildSummary:
    root: str
    database: str
    files_scanned: int
    files_changed: int
    nodes_indexed: int
    edges_indexed: int
    mode: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        import json

        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


@dataclass(slots=True)
class ImpactResult:
    changed_paths: list[str]
    impacted_paths: list[str]
    tests: list[str]
    confidence: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ReviewContext:
    target_paths: list[str]
    relevant_paths: list[str]
    summary: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

