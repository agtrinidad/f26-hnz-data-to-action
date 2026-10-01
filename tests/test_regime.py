"""Offline tests for the regime comparison: truth noise, second pass, frontier, year simulation."""

import copy

import numpy as np
import pandas as pd
import pytest
import yaml

from tobacco_inspect.config import DEFAULT_CONFIG, ConfigError, parse_config
from tobacco_inspect.eval import census as C
from tobacco_inspect.eval import regime as R
from tobacco_inspect.eval import simulate
from tobacco_inspect.model import thompson

P_VEC = np.linspace(0.05, 0.55, 40)  # mean 0.30, a clear risk gradient


def _travel(n, seed=0):
    rng = np.random.default_rng(seed)
    xy = rng.random((n + 1, 2)) * 10
    return np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))


def _params():
    cfg = parse_config(yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")))
    return C.CostParams.from_config(cfg), cfg


# --------------------------------------------------------------------------- truth with noise
def test_truth_keeps_the_city_rate_and_default_truth_is_the_model():
    rng = np.random.default_rng(0)
    for truth in (R.Truth(sigma=1.0), R.Truth(sigma=0.5, slope=0.6), R.Truth(slope=0.5)):
        assert np.allclose(truth.draws(P_VEC, 50, rng).mean(axis=1), P_VEC.mean(), atol=1e-6)
    assert np.allclose(R.Truth().draws(P_VEC, 3, rng), np.clip(P_VEC, 1e-4, 1 - 1e-4))


def test_slope_compresses_the_spread_and_sigma_adds_hidden_spread():
    rng = np.random.default_rng(0)
    flat = R.Truth(slope=0.4).draws(P_VEC, 20, rng).std(axis=1).mean()
    base = R.Truth().draws(P_VEC, 20, rng).std(axis=1).mean()
    assert flat < base
    # hidden heterogeneity breaks the exact link between truth and model score
    corr = np.corrcoef(R.Truth(sigma=1.5).draws(P_VEC, 1, rng)[0], P_VEC)[0, 1]
    assert corr < 0.95


def test_calibrated_truth_hits_the_target_lift_for_each_hidden_sigma():
    own = R.realized_lift(P_VEC, R.Truth(), n_draws=2)
    target = 0.5 * (own + 1.0)
    for sigma in (0.0, 0.3):
        truth = R.Truth.calibrated(P_VEC, target, sigma)
        assert truth.sigma == sigma and 0 < truth.slope < 1
        assert R.realized_lift(P_VEC, truth) == pytest.approx(target, abs=0.01)
    # a target the model already fails to beat leaves the model unattenuated
    assert R.Truth.calibrated(P_VEC, own + 0.5).slope == 1.0


def test_max_hidden_sigma_is_the_noise_that_alone_explains_the_lift():
    own = R.realized_lift(P_VEC, R.Truth(), n_draws=2)
    target = 0.5 * (own + 1.0)
    sigma = R.max_hidden_sigma(P_VEC, target)
    assert sigma > 0
    assert R.realized_lift(P_VEC, R.Truth(sigma, 1.0)) == pytest.approx(target, abs=0.01)
    assert R.max_hidden_sigma(P_VEC, own + 0.5) == 0.0


# --------------------------------------------------------------------------- shared response
def test_effective_p_matches_the_documented_channels():
    p = np.full(10, 0.4)
    hist = [np.array([0, 1]), np.array([1, 2])]
    out = simulate.effective_p(p, hist, delta=0.5, memory=2)
    assert out[0] == pytest.approx(0.4 * 0.5) and out[5] == pytest.approx(0.4)
    assert out[1] == pytest.approx(0.4 * 0.5 * 0.5)  # inspected in two cycles: compounds
    seen = simulate.effective_p(p, hist, gamma=0.5)  # 3 of 10 stores inspected recently
    assert np.allclose(seen, 0.4 * (1 - 0.5 * 0.3))
    assert np.allclose(simulate.effective_p(p, []), p)


def test_run_reports_exposure_and_is_unchanged_without_response():
    p = np.full(20, 0.3)
    res = simulate.run(lambda c, h: np.arange(3), p, 3, 4, np.random.default_rng(0))
    assert np.allclose(res["exposure"], 0.3)
    res2 = simulate.run(lambda c, h: np.arange(3), p, 3, 4, np.random.default_rng(0), delta=0.5)
    assert res2["exposure"][0] == pytest.approx(0.3) and res2["exposure"][-1] < 0.3


# --------------------------------------------------------------------------- second pass
def test_second_pass_posterior_update_matches_hand_computation():
    a, b = thompson.beta_prior_from_p(np.array([0.2]), 5)  # Beta(1, 4)
    a2, b2 = thompson.update(a, b, 1, np.array([1]))
    assert (a2[0], b2[0]) == (2.0, 4.0)
    a3, b3 = thompson.update(a, b, 1, np.array([0]))
    assert (a3[0], b3[0]) == (1.0, 5.0)


def test_second_pass_policies_behave_as_defined():
    rng = np.random.default_rng(1)
    noisy, example = R.adaptive_second_pass(P_VEC, 10, 5, R.Truth(sigma=1.5), 600, rng)
    g = noisy.set_index("policy")
    assert (noisy["second_pass_checks"] == 10).all()
    assert all(len(sel) == 10 for sel in example.values())
    # re-checking stage-1 violators is what finds repeat violators (FDA escalation trigger)
    assert g.loc["violators_first", "repeat_events"] > g.loc["random", "repeat_events"]
    # with an exact model the model ranking beats a random second pass
    exact, _ = R.adaptive_second_pass(P_VEC, 10, 5, R.Truth(), 600, rng)
    assert exact.set_index("policy").loc["static_model", "gain_vs_random"] > 0


def test_second_pass_with_no_information_is_not_worse_than_random():
    flat = np.full(30, 0.25)
    summary, _ = R.adaptive_second_pass(flat, 8, 5, R.Truth(), 800, np.random.default_rng(2))
    row = summary.set_index("policy").loc["posterior_mean"]
    assert row["gain_vs_random"] > -4 * row["gain_se"] - 0.05


# --------------------------------------------------------------------------- frontier
def test_frontier_is_monotone_and_meets_the_census_at_full_budget():
    params, cfg = _params()
    day = cfg.capacity.daily_budget_minutes
    n = len(P_VEC)
    fr = R.frontier(
        P_VEC,
        _travel(n),
        params,
        day,
        [8, 16, 24, 32],
        truth=R.Truth(sigma=1.0),
        kappa=5,
        n_sims=60,
        n_truth=60,
    )
    for pol in ("random", "targeted", "targeted_model_p"):
        d = fr[fr.policy == pol].sort_values("checks")["distinct_violators"].to_numpy()
        assert np.all(np.diff(d) > 0)
    census = fr[fr.policy == "census_floor"].iloc[0]
    assert census["distinct_violators"] == pytest.approx(P_VEC.sum())
    assert census["coverage_stores"] == 1.0 and census["coverage_top_decile"] == 1.0
    at = fr[fr.checks == 16].set_index("policy")["distinct_violators"]
    assert at["targeted_model_p"] >= at["targeted"]  # noisy truth discounts the optimistic line
    assert at["targeted"] > at["random"]
    assert np.isnan(fr[fr.policy == "targeted"]["se_rate"]).all()
    second = fr[fr.policy.str.startswith("census_floor+")]
    assert (second["checks"] > n).all()
    assert (second["cost_bottom_up"] > census["cost_bottom_up"]).all()


def test_frontier_charges_commissioning_to_the_census_not_the_running_program():
    params, cfg = _params()
    day = cfg.capacity.daily_budget_minutes
    n = len(P_VEC)
    kw = dict(truth=R.Truth(sigma=1.0), kappa=5, n_sims=20, n_truth=20, second_pass_fracs=())
    lean = R.frontier(P_VEC, _travel(n), params, day, [16], **kw).set_index("policy")
    full = R.frontier(
        P_VEC, _travel(n), params, day, [16], charge_commissioning_to_capped=True, **kw
    ).set_index("policy")
    extra = params.pick("training_fixed", "base") * (1 + params.pick("overhead_share", "base"))
    gap = full.loc["random", "cost_bottom_up"] - lean.loc["random", "cost_bottom_up"]
    assert gap == pytest.approx(extra)
    assert lean.loc["census_floor", "cost_bottom_up"] == full.loc["census_floor", "cost_bottom_up"]


def test_marginal_costs_are_positive_along_the_path():
    params, cfg = _params()
    fr = R.frontier(
        P_VEC,
        _travel(40),
        params,
        cfg.capacity.daily_budget_minutes,
        [8, 16, 24],
        truth=R.Truth(sigma=1.0),
        kappa=5,
        n_sims=20,
        n_truth=20,
    )
    m = R.marginal(fr, "random").dropna()
    assert (m["dollars_per_added_violator"] > 0).all()
    assert (m["checks_per_added_violator"] > 0).all()


# --------------------------------------------------------------------------- year simulation
def _year(regime, response=None, **kw):
    return R.year_sim(P_VEC, regime, response or {}, R.Truth(sigma=1.0), 5, n_sims=30, **kw)


def test_year_sim_check_counts_and_no_response_means_no_reduction():
    capped = _year("capped", budget_per_cycle=2)
    assert capped["checks"] == 24 and capped["reduction"] == pytest.approx(0, abs=1e-12)
    floor = _year("census_floor", second_pass_share=0.25)
    assert floor["checks"] == len(P_VEC) + 10
    assert (floor["counts"] >= 1 - 1e-9).all()  # the floor: every store at least once


def test_each_store_is_checked_at_most_once_when_capped():
    assert _year("capped", budget_per_cycle=2)["counts"].max() <= 1 + 1e-9


def test_response_lowers_exposure_more_for_the_regime_with_more_checks():
    resp = {"delta": 0.25, "memory": 3}
    capped = _year("capped", resp, budget_per_cycle=2)
    floor = _year("census_floor", resp)
    assert 0 < capped["reduction"] < floor["reduction"]
    assert _year("census_floor", {**resp, "gamma": 0.3})["reduction"] > floor["reduction"]


def test_risk_first_order_front_loads_protection_for_the_riskiest_stores():
    resp = {"delta": 0.5, "memory": 6}
    risk_first = _year("census_floor", resp, order="risk_first", second_pass_share=0)
    rand = _year("census_floor", resp, order="random", second_pass_share=0)
    assert risk_first["reduction"] > rand["reduction"]


def test_year_sim_rejects_unknown_regime_and_second_pass():
    with pytest.raises(ValueError):
        R.year_sim(P_VEC, "nope", {}, R.Truth(), 5, n_sims=2)
    with pytest.raises(ValueError):
        R.year_sim(P_VEC, "census_floor", {}, R.Truth(), 5, n_sims=2, second_pass="nope")


def test_gamma_power_makes_visibility_deterrence_convex_or_concave():
    p = np.full(10, 0.4)
    hist = [np.array([0, 1, 2, 3, 4])]  # half the stores inspected
    lin = simulate.effective_p(p, hist, gamma=0.8)[9]
    convex = simulate.effective_p(p, hist, gamma=0.8, gamma_power=2)[9]
    concave = simulate.effective_p(p, hist, gamma=0.8, gamma_power=0.5)[9]
    assert lin == pytest.approx(0.4 * (1 - 0.8 * 0.5))
    assert convex > lin > concave  # at c < 1 a convex response deters less than a linear one


def test_crossing_interpolates_and_reports_no_crossing():
    assert R.crossing([0, 1, 2], [-1, -1, 1]) == pytest.approx(1.5)
    assert np.isnan(R.crossing([0, 1, 2], [1, 2, 3]))


# --------------------------------------------------------------------------- equity
def test_equity_compare_counts_never_checked_and_high_poverty_share():
    cand = pd.DataFrame({"license_id": list("abcdef"), "tract_geoid": ["t1"] * 3 + ["t2"] * 3})
    uni = pd.DataFrame(
        {
            "license_id": list("abcdef"),
            "acs_poverty_rate": [0.1] * 3 + [0.4] * 3,
            "acs_youth_share": [0.2] * 6,
        }
    )
    out = R.equity_compare(
        cand, uni, {"census": np.ones(6), "capped": np.array([0.5, 0.5, 0.5, 0, 0, 0])}
    ).set_index("regime")
    assert out.loc["census", "share_stores_never_checked"] == 0
    assert out.loc["capped", "share_stores_never_checked"] == pytest.approx(0.75)
    assert out.loc["census", "share_inspections_high_poverty"] == pytest.approx(0.5)
    assert out.loc["capped", "share_inspections_high_poverty"] == 0


# --------------------------------------------------------------------------- config
def test_regime_config_is_validated():
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    for key, bad in (("floor_months", 12), ("second_pass_share", 1.5), ("observed_lift", 0.5)):
        broken = copy.deepcopy(data)
        broken["regime"][key] = bad
        with pytest.raises(ConfigError, match="regime"):
            parse_config(broken)
