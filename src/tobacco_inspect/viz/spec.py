"""ChartSpec: the declarative recipe behind every built chart (JSON in, figure out)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

AGGS = ("count", "sum", "mean", "median", "share")
FIELDS = ("x", "y", "color", "size", "facet")
MAX_FACETS = 6


class SpecError(ValueError):
    """A chart spec that cannot be drawn; `problems` holds one readable message per issue."""

    def __init__(self, problems: list[str] | str):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("; ".join(self.problems))


@dataclass
class ChartSpec:
    dataset: str
    kind: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    size: str | None = None
    facet: str | None = None
    agg: str = "mean"
    sort: str = "none"  # none | asc | desc
    top_n: int | None = None
    # {"col": c, "values": [...]} for categories or {"col": c, "min": a, "max": b} for numbers
    filters: list[dict[str, Any]] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    text: dict[str, str] = field(default_factory=dict)  # title / subtitle / source overrides

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)

    @classmethod
    def from_json(cls, raw: str | dict[str, Any]) -> ChartSpec:
        d = json.loads(raw) if isinstance(raw, str) else dict(raw)
        unknown = set(d) - set(cls.__dataclass_fields__)
        if unknown:
            raise SpecError(f"unknown spec keys: {sorted(unknown)}")
        for key in ("dataset", "kind"):
            if key not in d:
                raise SpecError(f"spec is missing '{key}'")
        return cls(**d)

    def opt(self, name: str, default: Any = None) -> Any:
        return self.options.get(name, default)
