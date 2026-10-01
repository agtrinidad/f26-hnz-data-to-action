"""Census scenario: check every distinct licensed location once in a year.

Three questions, three parts of this module:
1. Portioning: split the stores into day-long routes (`routing/partition.py`) and place the routes
   on a calendar (`portion_calendar`) in four ways.
2. Expense: a bottom-up cost built from the actual routes (`bottom_up_cost`) and a top-down cost
   from DOH's award per check (`top_down_cost`), each with low/base/high settings.
3. Capture: exact expected values for a census versus random sampling policies (`capture_*`),
   verified by Monte Carlo (`simulate_capture`).

A single undercover buy is a Bernoulli trial: store i sells with probability p_i. "Capture" is
therefore reported in several ways (violations detected, distinct violators, coverage), because a
census wins on some and ties on others.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from tobacco_inspect.routing import partition

SCENARIOS = ("low", "base", "high")


# --------------------------------------------------------------------------- parameters
@dataclass(frozen=True)
class CostParams:
    """Cost and time parameters; each field holds {"low", "base", "high"} (low = cheaper)."""

    onsite_minutes: float
    admin_minutes: dict
    retry_share: dict
    drive_factor: dict
    supervisor_wage: dict
    purchaser_wage: dict
    fringe: dict
    mileage_rate: dict
    avg_mph: float
    commute_miles_per_route: dict
    overhead_share: dict
    data_per_check: dict
    training_fixed: dict
    topdown_per_check: dict
    followup_rate: dict

    @classmethod
    def from_config(cls, config) -> CostParams:
        c = config.raw["census"]
        return cls(
            onsite_minutes=float(c["onsite_minutes"]),
            avg_mph=float(c["avg_mph"]),
            **{
                k: c[k]
                for k in (
                    "admin_minutes",
                    "retry_share",
                    "drive_factor",
                    "supervisor_wage",
                    "purchaser_wage",
                    "fringe",
                    "mileage_rate",
                    "commute_miles_per_route",
                    "overhead_share",
                    "data_per_check",
                    "training_fixed",
                    "topdown_per_check",
                    "followup_rate",
                )
            },
        )

    def pick(self, field: str, scenario: str) -> float:
        d = getattr(self, field)
        return float(d[scenario] if scenario in d else d["base"])


# --------------------------------------------------------------------------- routes and cost
def service_minutes(params: CostParams, scenario: str = "base") -> float:
    """Minutes at a store: on-site purchase attempt plus paperwork/evidence/data entry."""
    return params.onsite_minutes + params.pick("admin_minutes", scenario)


def build_routes(
    travel, params: CostParams, day_minutes: float, scenario: str = "base", nodes=None
):
    """Census routes under a scenario's time assumptions (traffic factor scales driving)."""
    t = np.asarray(travel, dtype=float) * params.pick("drive_factor", scenario)
    svc = [0.0] + [service_minutes(params, scenario)] * (t.shape[0] - 1)
    return partition.census_routes(t, svc, day_minutes, nodes=nodes), t, svc


def bottom_up_cost(routes, t, svc, params: CostParams, scenario: str = "base") -> pd.DataFrame:
    """Cost lines from the real routes (two-person team paid for the whole route time).

    Components: supervisor and purchaser labor (with fringe), mileage (drive time converted to
    miles at `avg_mph`, plus a commute from the team's base), retries for closed stores or refused
    attempts, data handling, one-time training, and an overhead share on direct costs.
    """
    p = lambda f: params.pick(f, scenario)  # noqa: E731
    stops = sum(len(r) for r in routes)
    route_min = [partition.route_minutes(r, t, svc) for r in routes]
    drive_min = sum(route_min) - stops * svc[1]
    retry = p("retry_share") * stops
    retry_min = retry * (svc[1] + 5.0)  # one more attempt: time at store plus a short re-drive
    team_hours = (sum(route_min) + retry_min) / 60.0
    labor = team_hours * (p("supervisor_wage") + p("purchaser_wage")) * p("fringe")
    miles = (drive_min + retry * 5.0) / 60.0 * params.avg_mph + len(routes) * p(
        "commute_miles_per_route"
    )
    lines = {
        "labor (supervisor + purchaser, with fringe)": labor,
        "mileage": miles * p("mileage_rate"),
        "data handling and QA": (stops + retry) * p("data_per_check"),
        "training and commissioning (one-time)": p("training_fixed"),
    }
    direct = sum(lines.values())
    lines["overhead (indirect / fixed fee)"] = direct * p("overhead_share")
    out = pd.DataFrame({"component": list(lines), "dollars": list(lines.values())})
    out["scenario"] = scenario
    out.attrs.update(
        stops=stops,
        routes=len(routes),
        team_hours=team_hours,
        miles=miles,
        retries=retry,
        drive_minutes=drive_min,
    )
    return out


def top_down_cost(n_checks: float, params: CostParams) -> dict[str, float]:
    """DOH award per check ($116 = award / 10,000 funded; $400 = award / ~2,900 published)."""
    lo, hi = params.topdown_per_check["low"], params.topdown_per_check["high"]
    return {"low": lo * n_checks, "high": hi * n_checks}


def cost_table(travel, params: CostParams, day_minutes: float, n_checks_extra: float = 0.0):
    """Bottom-up census cost for each scenario, with team-days and per-check cost."""
    rows = []
    for sc in SCENARIOS:
        routes, t, svc = build_routes(travel, params, day_minutes, sc)
        cost = bottom_up_cost(routes, t, svc, params, sc)
        total = cost["dollars"].sum()
        stops = cost.attrs["stops"]
        rows.append(
            {
                "scenario": sc,
                "stops": stops,
                "team_days": cost.attrs["routes"],
                "team_hours": round(cost.attrs["team_hours"], 1),
                "drive_hours": round(cost.attrs["drive_minutes"] / 60, 1),
                "total_dollars": round(total),
                "dollars_per_check": round(total / stops, 1),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- calendars
def workdays(start: date, end: date) -> list[date]:
    """Weekdays between start and end inclusive, skipping US federal holidays."""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from pandas.tseries.offsets import CustomBusinessDay

    bday = CustomBusinessDay(calendar=USFederalHolidayCalendar())
    return [d.date() for d in pd.date_range(start, end, freq=bday)]


def _assign(routes_idx, days, teams, rng) -> dict:
    """Place routes on distinct (day, team) slots at random within `days`."""
    slots = [(d, k) for d in days for k in range(1, teams + 1)]
    if len(routes_idx) > len(slots):
        raise ValueError(f"{len(routes_idx)} routes do not fit in {len(slots)} slots")
    pick = rng.choice(len(slots), size=len(routes_idx), replace=False)
    return {r: slots[i] for r, i in zip(routes_idx, pick, strict=True)}


def portion_calendar(
    plan: str, n_routes: int, route_risk, year: int, teams: int, rng
) -> pd.DataFrame:
    """Calendar for one portioning plan. Random placement keeps the order unpredictable.

    A: one summer block (Jul 6 to Aug 21, like Synar). B: quarters (a quarter of the routes each).
    C: months (a twelfth each). D: risk-staged (highest-risk routes in Q1, then Q2...), random order
    inside each quarter.
    """
    idx = list(range(n_routes))
    if plan == "A":
        placed = _assign(idx, workdays(date(year, 7, 6), date(year, 8, 21)), teams, rng)
    elif plan in ("B", "D"):
        order = (
            [i for i in np.argsort(-np.asarray(route_risk))]
            if plan == "D"
            else list(rng.permutation(idx))
        )
        chunks = np.array_split(order, 4)
        placed = {}
        for q, chunk in enumerate(chunks):
            lo = date(year, 3 * q + 1, 1)
            end = (pd.Timestamp(year=year, month=3 * q + 3, day=1) + pd.offsets.MonthEnd(0)).date()
            placed.update(_assign([int(i) for i in chunk], workdays(lo, end), teams, rng))
    elif plan == "C":
        chunks = np.array_split(list(rng.permutation(idx)), 12)
        placed = {}
        for m, chunk in enumerate(chunks):
            lo = date(year, m + 1, 1)
            end = (pd.Timestamp(lo) + pd.offsets.MonthEnd(0)).date()
            placed.update(_assign(list(map(int, chunk)), workdays(lo, end), teams, rng))
    else:
        raise ValueError(plan)
    rows = [{"route": r, "date": d, "team": k} for r, (d, k) in placed.items()]
    cal = pd.DataFrame(rows).sort_values(["date", "team"]).reset_index(drop=True)
    cal["plan"] = plan
    cal["month"] = pd.to_datetime(cal["date"]).dt.month
    return cal


def calendar_summary(cal: pd.DataFrame) -> dict:
    d = pd.to_datetime(cal["date"])
    return {
        "first_day": d.min().date().isoformat(),
        "last_day": d.max().date().isoformat(),
        "calendar_weeks": int(np.ceil((d.max() - d.min()).days / 7)) + 1,
        "busiest_month_routes": int(cal.groupby("month").size().max()),
        "months_covered": int(cal["month"].nunique()),
    }


# --------------------------------------------------------------------------- capture: exact
def expected_detected(p, n: float) -> float:
    """Expected violations detected by n checks at stores drawn uniformly (any scheme where each
    check lands on a uniformly random store): n times the mean probability."""
    return float(n * np.mean(p))


def distinct_census(p) -> float:
    """Census: every store once; distinct violators caught = sum of p_i."""
    return float(np.sum(p))


def distinct_srs(p, n: int) -> float:
    """Simple random sample without replacement of n stores."""
    return float(n / len(p) * np.sum(p))


def distinct_iid(p, n: int) -> float:
    """Absolute random sampling: n independent uniform draws (stores can repeat)."""
    p = np.asarray(p, dtype=float)
    return float(np.sum(1 - (1 - p / len(p)) ** n))


def coverage_iid(N: int, n: int) -> float:
    """Share of stores checked at least once by n independent uniform draws."""
    return float(1 - (1 - 1 / N) ** n)


def distinct_targeted(p, n: int) -> float:
    """Top-n stores by p (assumes the model's p is the truth: an optimistic upper bound)."""
    return float(np.sort(np.asarray(p))[::-1][:n].sum())


def distinct_two_pass(p) -> float:
    """Every store checked twice (independent attempts): at least one violation caught."""
    return float(np.sum(1 - (1 - np.asarray(p)) ** 2))


def followup_repeats(p, rate: float) -> tuple[float, float]:
    """Census plus re-checking violators with probability `rate`.

    Returns (extra checks, expected repeat violations caught): extra = rate * sum(p),
    repeats = rate * sum(p^2).
    """
    p = np.asarray(p, dtype=float)
    return float(rate * p.sum()), float(rate * (p**2).sum())


def se_rate_census(p) -> float:
    """Standard error of the observed city violation rate after a census (Bernoulli noise only)."""
    p = np.asarray(p, dtype=float)
    return float(np.sqrt(np.sum(p * (1 - p))) / len(p))


def se_rate_sample(p, n: int) -> float:
    """Standard error of the observed rate from n random checks (Synar: n = 100 in Allegheny)."""
    pbar = float(np.mean(p))
    return float(np.sqrt(pbar * (1 - pbar) / n))


def iid_budget_for_coverage(N: int, share: float) -> float:
    """Draws for independent random sampling to cover `share` of stores: N ln(1/(1-share))."""
    return float(N * np.log(1 / (1 - share)))


def iid_budget_for_distinct(p, target: float, upper: int = 50) -> float:
    """Smallest n (as a multiple of N) at which iid sampling catches `target` distinct violators."""
    N = len(p)
    lo, hi = 1, upper * N
    if distinct_iid(p, hi) < target:
        return float("nan")
    while lo < hi:
        mid = (lo + hi) // 2
        if distinct_iid(p, mid) >= target:
            hi = mid
        else:
            lo = mid + 1
    return float(lo)


# --------------------------------------------------------------------------- capture: simulated
def simulate_capture(p, policy: str, n: int, n_sims: int, rng, tracts=None) -> dict:
    """Monte Carlo of one year's checks. Returns means of events, distinct violators, coverage.

    policies: census | srs | iid | targeted | stratified (proportional by tract, then random).
    SIMULATED: stores sell with probability p_i; p is the model's population-calibrated estimate.
    """
    p = np.asarray(p, dtype=float)
    N = len(p)
    events, distinct, cover = [], [], []
    order = np.argsort(-p)
    groups = None
    if policy == "stratified":
        tr = pd.Series(tracts if tracts is not None else np.zeros(N))
        groups = [np.where(tr.to_numpy() == g)[0] for g in tr.unique()]
    for _ in range(n_sims):
        if policy == "census":
            sel = np.arange(N)
        elif policy == "srs":
            sel = rng.choice(N, size=min(n, N), replace=False)
        elif policy == "iid":
            sel = rng.choice(N, size=n, replace=True)
        elif policy == "targeted":
            sel = order[:n]
        elif policy == "stratified":
            quota = np.floor(np.array([len(g) for g in groups]) * n / N).astype(int)
            extra = n - quota.sum()
            frac = np.array([len(g) for g in groups]) * n / N - quota
            bump = np.zeros(len(groups), dtype=int)
            bump[np.argsort(-frac)[:extra]] = 1
            sel = np.concatenate(
                [
                    rng.choice(g, size=min(q + b, len(g)), replace=False)
                    for g, q, b in zip(groups, quota, bump, strict=True)
                ]
            )
        else:
            raise ValueError(policy)
        hit = rng.random(len(sel)) < p[sel]
        events.append(hit.sum())
        distinct.append(len(set(sel[hit])))
        cover.append(len(set(sel)) / N)
    return {
        "events": float(np.mean(events)),
        "distinct": float(np.mean(distinct)),
        "coverage": float(np.mean(cover)),
        "events_sd": float(np.std(events)),
    }


def capture_table(
    p, tracts=None, fractions=(0.1, 0.25, 0.5, 0.75, 1.0), n_sims=2000, seed=867, lift=1.5
):
    """Exact and simulated capture for policies at several budgets (n checks in the year)."""
    p = np.asarray(p, dtype=float)
    N, rng = len(p), np.random.default_rng(seed)
    top_decile = np.argsort(-p)[: max(1, N // 10)]
    rows = []
    for f in fractions:
        n = int(round(f * N))
        for pol, exact in (
            ("srs", distinct_srs(p, n)),
            ("iid", distinct_iid(p, n)),
            ("stratified", distinct_srs(p, n)),
            ("targeted", distinct_targeted(p, n)),
        ):
            sim = simulate_capture(p, pol, n, n_sims, rng, tracts)
            cov = coverage_iid(N, n) if pol == "iid" else n / N
            rows.append(
                {
                    "budget_checks": n,
                    "budget_share_of_N": f,
                    "policy": pol,
                    "events_exact": expected_detected(p, n) if pol != "targeted" else exact,
                    "distinct_exact": exact,
                    "distinct_sim": sim["distinct"],
                    "coverage_exact": cov,
                    "coverage_sim": sim["coverage"],
                    "top_decile_covered": cov
                    if pol != "targeted"
                    else min(1.0, n / len(top_decile)),
                    "cost_checks": n,
                }
            )
    out = pd.DataFrame(rows)
    out["distinct_per_check"] = out["distinct_exact"] / out["budget_checks"]
    # evidence-discounted targeted line: observed replay lift (~1.5x) instead of the model's own p
    out["distinct_if_lift"] = np.where(
        out["policy"] == "targeted",
        np.minimum(out["distinct_exact"], lift * out["budget_checks"] * p.mean()),
        out["distinct_exact"],
    )
    return out


# --------------------------------------------------------------------------- timing (assumed)
def store_check_months(routes, calendar: pd.DataFrame, n_stores: int) -> np.ndarray:
    """Month (1..12) in which each store (node i -> index i-1) is checked, from a calendar."""
    month_of_route = dict(zip(calendar["route"], calendar["month"], strict=True))
    out = np.zeros(n_stores, dtype=int)
    for r, route in enumerate(routes):
        for node in route:
            out[node - 1] = month_of_route[r]
    return out


def monthly_protection(check_month, p, memory_months: int) -> np.ndarray:
    """Risk-weighted share of stores 'recently checked' in each calendar month (steady state).

    ASSUMED deterrence window: a check protects a store for `memory_months` months, and the census
    repeats every year, so a store checked in month c is protected in months c .. c+memory-1
    (wrapping into the next year). The total over the year is the same for every calendar; only
    the profile differs (a summer block leaves winter and spring unprotected).
    """
    m = np.asarray(check_month)
    p = np.asarray(p, dtype=float)
    out = np.zeros(12)
    for month in range(1, 13):
        protected = ((month - m) % 12) < memory_months
        out[month - 1] = (p * protected).sum() / p.sum()
    return out


# --------------------------------------------------------------------------- scenario helpers
def _with(params: CostParams, field: str, value: float) -> CostParams:
    from dataclasses import replace

    return replace(params, **{field: {"low": value, "base": value, "high": value}})


def cost_sensitivity(travel, params: CostParams, day_minutes: float) -> pd.DataFrame:
    """One-at-a-time swing: set each banded parameter to its low and high, others at base."""
    base_total = (
        cost_table(travel, _freeze_base(params), day_minutes)
        .set_index("scenario")
        .loc["base", "total_dollars"]
    )
    rows = []
    for field in (
        "admin_minutes",
        "retry_share",
        "drive_factor",
        "supervisor_wage",
        "purchaser_wage",
        "fringe",
        "mileage_rate",
        "commute_miles_per_route",
        "overhead_share",
        "data_per_check",
        "training_fixed",
    ):
        band = getattr(params, field)
        totals = {}
        for end in ("low", "high"):
            p2 = _with(_freeze_base(params), field, band[end])
            totals[end] = (
                cost_table(travel, p2, day_minutes)
                .set_index("scenario")
                .loc["base", "total_dollars"]
            )
        rows.append(
            {
                "parameter": field,
                "low_value": band["low"],
                "high_value": band["high"],
                "total_at_low": totals["low"],
                "total_at_high": totals["high"],
                "swing": totals["high"] - totals["low"],
                "base_total": base_total,
            }
        )
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)


def _freeze_base(params: CostParams) -> CostParams:
    """All bands set to their base values, so scenario labels no longer change anything."""
    from dataclasses import replace

    fields = {
        f: {
            "low": params.pick(f, "base"),
            "base": params.pick(f, "base"),
            "high": params.pick(f, "base"),
        }
        for f in (
            "admin_minutes",
            "retry_share",
            "drive_factor",
            "supervisor_wage",
            "purchaser_wage",
            "fringe",
            "mileage_rate",
            "commute_miles_per_route",
            "overhead_share",
            "data_per_check",
            "training_fixed",
        )
    }
    return replace(params, **fields)


def risk_staged_cost(
    travel, params: CostParams, p, day_minutes: float, tiers: int = 4
) -> pd.DataFrame:
    """Cost of staging by risk: route each risk tier separately (scattered stops) vs geography."""
    p = np.asarray(p, dtype=float)
    t = np.asarray(travel, dtype=float) * params.pick("drive_factor", "base")
    svc = [0.0] + [service_minutes(params, "base")] * (t.shape[0] - 1)
    order = np.argsort(-p)
    rows = []
    geo = partition.census_routes(t, svc, day_minutes)
    geo_min = sum(partition.route_minutes(r, t, svc) for r in geo)
    rows.append(
        {"plan": "geographic (all stores)", "team_days": len(geo), "total_minutes": round(geo_min)}
    )
    total_routes, total_min = 0, 0.0
    for idx in np.array_split(order, tiers):
        nodes = [int(i) + 1 for i in idx]
        routes = partition.census_routes(t, svc, day_minutes, nodes=nodes)
        total_routes += len(routes)
        total_min += sum(partition.route_minutes(r, t, svc) for r in routes)
    rows.append(
        {
            "plan": f"risk tiers x{tiers} (each routed separately)",
            "team_days": total_routes,
            "total_minutes": round(total_min),
        }
    )
    out = pd.DataFrame(rows)
    out["extra_team_days_vs_geographic"] = out["team_days"] - len(geo)
    out["extra_minutes_vs_geographic"] = out["total_minutes"] - round(geo_min)
    return out
