"""Offline tests for the census scenario: partitioning, cost model, capture formulas."""

import copy
from datetime import date

import numpy as np
import pandas as pd
import pytest
import yaml

from tobacco_inspect.config import DEFAULT_CONFIG, ConfigError, load_config, parse_config
from tobacco_inspect.eval import census as C
from tobacco_inspect.routing import partition as P


def _instance(n=10, seed=0):
    rng = np.random.default_rng(seed)
    xy = rng.random((n + 1, 2)) * 10
    d = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))  # minutes
    return d, [0.0] + [20.0] * n


# --------------------------------------------------------------------------- partitioning
def test_census_routes_cover_every_store_once_within_the_day():
    travel, service = _instance(30)
    routes = P.census_routes(travel, service, day_minutes=120)
    flat = [i for r in routes for i in r]
    assert sorted(flat) == list(range(1, 31))
    assert all(P.route_minutes(r, travel, service) <= 120 + 1e-6 for r in routes)
    assert len(routes) >= int(np.ceil(30 * 20 / 120))  # cannot beat the on-site time bound


def test_split_rejects_a_store_that_cannot_fit_in_a_day():
    travel, service = _instance(3)
    with pytest.raises(ValueError, match="alone exceeds"):
        P.census_routes(travel, service, day_minutes=10)


def test_two_opt_never_lengthens_and_heuristic_is_near_exact():
    travel, service = _instance(8, seed=3)
    order = list(range(1, 9))
    better = P.two_opt_directed(order, travel, service)
    assert (
        P.route_minutes(better, travel, service) <= P.route_minutes(order, travel, service) + 1e-9
    )
    exact, _ = P.held_karp(order, travel, service)
    sym = (travel + travel.T) / 2
    heur = P.route_minutes(
        P.two_opt_directed(
            P.two_opt_symmetric(P.nearest_neighbor_order(order, sym), sym), travel, service
        ),
        travel,
        service,
    )
    assert exact - 1e-9 <= heur <= exact * 1.10


def test_held_karp_matches_brute_force_on_a_tiny_case():
    travel, service = _instance(5, seed=1)
    from itertools import permutations

    best = min(P.route_minutes(list(o), travel, service) for o in permutations(range(1, 6)))
    exact, order = P.held_karp(list(range(1, 6)), travel, service)
    assert exact == pytest.approx(best) and sorted(order) == [1, 2, 3, 4, 5]


# --------------------------------------------------------------------------- cost model
def test_cost_scenarios_are_ordered_and_sum_correctly():
    cfg = load_config()
    params = C.CostParams.from_config(cfg)
    travel, _ = _instance(40)
    table = C.cost_table(travel, params, 480).set_index("scenario")
    assert (
        table.loc["low", "total_dollars"]
        < table.loc["base", "total_dollars"]
        < table.loc["high", "total_dollars"]
    )
    routes, t, svc = C.build_routes(travel, params, 480, "base")
    lines = C.bottom_up_cost(routes, t, svc, params, "base")
    direct = lines.loc[~lines["component"].str.startswith("overhead"), "dollars"].sum()
    overhead = lines.loc[lines["component"].str.startswith("overhead"), "dollars"].iloc[0]
    assert overhead == pytest.approx(direct * params.pick("overhead_share", "base"))
    top = C.top_down_cost(345, params)
    assert top["low"] == 116 * 345 and top["high"] == 400 * 345


@pytest.mark.parametrize(
    "bad", [{"low": 5, "base": 1, "high": 9}, {"low": 3, "base": 4, "high": 2}]
)
def test_census_config_bands_validated(bad):
    with open(DEFAULT_CONFIG, encoding="utf-8") as fh:
        data = copy.deepcopy(yaml.safe_load(fh))
    data["census"]["admin_minutes"] = bad
    with pytest.raises(ConfigError, match="low <= base <= high"):
        parse_config(data)


# --------------------------------------------------------------------------- capture identities
P_VEC = np.array([0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.15, 0.25, 0.35, 0.45])


def test_srs_at_full_budget_equals_census():
    assert C.distinct_srs(P_VEC, len(P_VEC)) == pytest.approx(C.distinct_census(P_VEC))
    assert C.distinct_targeted(P_VEC, len(P_VEC)) == pytest.approx(C.distinct_census(P_VEC))


def test_iid_coverage_and_distinct_formulas():
    N = 345
    assert C.coverage_iid(N, N) == pytest.approx(1 - (1 - 1 / N) ** N)
    assert 0.63 < C.coverage_iid(N, N) < 0.64
    assert C.distinct_iid(P_VEC, 10) < C.distinct_census(P_VEC)
    assert C.iid_budget_for_coverage(100, 0.95) == pytest.approx(100 * np.log(20))
    # catching as many distinct violators as a census takes more than N draws
    assert C.iid_budget_for_distinct(P_VEC, C.distinct_census(P_VEC)) > len(P_VEC)


def test_closed_form_matches_simulation():
    rng = np.random.default_rng(5)
    p = np.clip(rng.beta(2, 6, 200), 0.01, 0.9)
    for policy, exact in (("srs", C.distinct_srs(p, 80)), ("iid", C.distinct_iid(p, 80))):
        sim = C.simulate_capture(p, policy, 80, 3000, np.random.default_rng(1))
        assert sim["distinct"] == pytest.approx(exact, rel=0.03)
    cen = C.simulate_capture(p, "census", 200, 3000, np.random.default_rng(2))
    assert cen["distinct"] == pytest.approx(C.distinct_census(p), rel=0.02)
    assert cen["coverage"] == 1.0


def test_precision_and_followup():
    assert C.se_rate_census(P_VEC) <= C.se_rate_sample(P_VEC, len(P_VEC)) + 1e-12
    assert C.se_rate_sample(np.full(50, 0.26), 100) == pytest.approx(np.sqrt(0.26 * 0.74 / 100))
    extra, repeats = C.followup_repeats(P_VEC, 0.5)
    assert extra == pytest.approx(0.5 * P_VEC.sum()) and repeats == pytest.approx(
        0.5 * (P_VEC**2).sum()
    )
    assert C.distinct_two_pass(P_VEC) > C.distinct_census(P_VEC)


# --------------------------------------------------------------------------- calendars and timing
def test_calendars_respect_windows_and_slots():
    rng = np.random.default_rng(0)
    cal = C.portion_calendar("A", 28, np.arange(28), 2027, 2, rng)
    d = pd.to_datetime(cal["date"])
    assert d.min() >= pd.Timestamp(2027, 7, 6) and d.max() <= pd.Timestamp(2027, 8, 21)
    assert not cal.duplicated(["date", "team"]).any() and len(cal) == 28
    assert (d.dt.weekday < 5).all()
    cd = C.portion_calendar("D", 28, np.arange(28)[::-1], 2027, 2, rng)  # route 0 is the riskiest
    quarter = pd.to_datetime(cd["date"]).dt.quarter.to_numpy()
    by_route = dict(zip(cd["route"], quarter, strict=True))
    assert by_route[0] == 1 and by_route[27] == 4  # risk-staged: riskiest first, least risky last
    assert date(2027, 7, 5) not in set(
        C.workdays(date(2027, 7, 1), date(2027, 7, 9))
    )  # July 4 observed


def test_monthly_protection_total_is_calendar_independent():
    p = np.random.default_rng(0).random(60) + 0.1
    summer = np.random.default_rng(1).choice([7, 8], 60)
    spread = np.random.default_rng(2).integers(1, 13, 60)
    a = C.monthly_protection(summer, p, 3)
    b = C.monthly_protection(spread, p, 3)
    assert a.mean() == pytest.approx(3 / 12) and b.mean() == pytest.approx(3 / 12)
    assert (
        a.min() == 0 and a.max() > b.max()
    )  # the summer block is bursty: some months fully unprotected
