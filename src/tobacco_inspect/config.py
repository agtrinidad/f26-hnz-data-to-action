"""Load and validate the YAML config (config/default.yaml).

All paths in the config are relative to the repository root, so the project runs
unchanged on any machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "default.yaml"
SOLVERS = {"gurobi", "appsi_highs"}


class ConfigError(ValueError):
    """Raised when the config file is missing values or has invalid ones."""


@dataclass(frozen=True)
class Capacity:
    teams: int
    hours_per_day: float
    weekdays_only: bool
    horizon_weeks: int
    weekly_mileage_cap: float
    budget_inspections: int
    service_minutes: float
    cycle_weeks: int = 4

    @property
    def days(self) -> int:
        per_week = 5 if self.weekdays_only else 7
        return per_week * self.horizon_weeks

    @property
    def daily_budget_minutes(self) -> float:
        return self.hours_per_day * 60.0

    @property
    def cycles(self) -> int:
        """Planning cycles (e.g. months) inside the horizon."""
        return max(1, self.horizon_weeks // self.cycle_weeks)

    @property
    def cycle_budget(self) -> int:
        """Inspections per cycle: the horizon budget split evenly, rounded up."""
        return -(-self.budget_inspections // self.cycles)

    @property
    def cycle_days(self) -> int:
        return (5 if self.weekdays_only else 7) * self.cycle_weeks


@dataclass(frozen=True)
class Config:
    solver: str
    seed: int
    capacity: Capacity
    prize: dict[str, Any]
    coverage: dict[str, Any]
    paths: dict[str, str]
    raw: dict[str, Any]

    def path(self, key: str) -> Path:
        """Resolve a configured directory against the repository root."""
        return REPO_ROOT / self.paths[key]


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"missing '{key}' in {where}")
    return mapping[key]


def _validate_optional(data: dict[str, Any], capacity: Capacity) -> None:
    """Validate the modeling sections added for the optimization stage (all optional)."""
    cycle = data["capacity"].get("cycle_weeks", capacity.horizon_weeks)
    if not 1 <= int(cycle) <= capacity.horizon_weeks:
        raise ConfigError("capacity.cycle_weeks must be between 1 and horizon_weeks")
    risk = data.get("risk", {})
    if risk.get("kappa", 1) <= 0:
        raise ConfigError("risk.kappa must be > 0")
    if risk.get("lag_days", 0) < 0:
        raise ConfigError("risk.lag_days must be >= 0")
    weights = data.get("harrington", {}).get("state_weights")
    if weights is not None and (len(weights) != 5 or any(w < 0 for w in weights)):
        raise ConfigError("harrington.state_weights needs 5 non-negative values (depth 0..4)")
    mix = data.get("prize", {}).get("site_mix")
    if mix is not None and abs(sum(mix.values()) - 1.0) > 1e-9:
        raise ConfigError("prize.site_mix must sum to 1")
    if data.get("data", {}).get("scope", "city_limits") not in {"city_limits", "postal"}:
        raise ConfigError("data.scope must be city_limits or postal")


def parse_config(data: dict[str, Any]) -> Config:
    """Validate a parsed YAML mapping and build a Config."""
    solver = _require(data, "solver", "config")
    if solver not in SOLVERS:
        raise ConfigError(f"solver must be one of {sorted(SOLVERS)}, got {solver!r}")

    cap = _require(data, "capacity", "config")
    capacity = Capacity(
        teams=int(_require(cap, "teams", "capacity")),
        hours_per_day=float(_require(cap, "hours_per_day", "capacity")),
        weekdays_only=bool(_require(cap, "weekdays_only", "capacity")),
        horizon_weeks=int(_require(cap, "horizon_weeks", "capacity")),
        weekly_mileage_cap=float(_require(cap, "weekly_mileage_cap", "capacity")),
        budget_inspections=int(_require(cap, "budget_inspections", "capacity")),
        service_minutes=float(_require(cap, "service_minutes", "capacity")),
        cycle_weeks=int(cap.get("cycle_weeks", 4)),
    )
    if capacity.teams < 1 or capacity.horizon_weeks < 1 or capacity.budget_inspections < 1:
        raise ConfigError("teams, horizon_weeks and budget_inspections must be >= 1")
    if not 0 < capacity.hours_per_day <= 24:
        raise ConfigError("hours_per_day must be in (0, 24]")

    coverage = _require(data, "coverage", "config")
    share = _require(coverage, "random_share", "coverage")
    if not 0 <= share <= 1:
        raise ConfigError("coverage.random_share must be in [0, 1]")

    prize = _require(data, "prize", "config")
    weights = _require(prize, "h_weights", "prize")
    if abs(sum(weights.values()) - 1.0) > 1e-9:
        raise ConfigError("prize.h_weights must sum to 1")

    _validate_optional(data, capacity)

    paths = _require(data, "paths", "config")
    for key, value in paths.items():
        p = Path(value)
        if p.is_absolute() or p.drive or value.startswith(("/", "\\")):
            raise ConfigError(f"paths.{key} must be relative to the repo root, got {value!r}")

    return Config(
        solver=solver,
        seed=int(_require(data, "seed", "config")),
        capacity=capacity,
        prize=prize,
        coverage=coverage,
        paths=paths,
        raw=data,
    )


def load_config(path: str | Path | None = None) -> Config:
    """Load config from `path` (default: config/default.yaml)."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG
    with open(cfg_path, encoding="utf-8") as fh:
        return parse_config(yaml.safe_load(fh))
