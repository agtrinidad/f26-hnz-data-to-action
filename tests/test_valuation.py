"""Offline tests for the marginal-value tables (identities on synthetic inputs)."""

import numpy as np
import pandas as pd
import pytest
import yaml

from tobacco_inspect.config import DEFAULT_CONFIG, parse_config
from tobacco_inspect.eval import census as C
from tobacco_inspect.eval import valuation as V


def _cfg():
    return parse_config(yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8")))


def _front():
    rows = [
        ("targeted", 44, 16.0, 3000.0),
        ("census_floor", 345, 88.0, 27000.0),
        ("census_floor+adaptive_second_pass", 431, 100.0, 33000.0),
    ]
    return pd.DataFrame(rows, columns=["policy", "checks", "distinct_violators", "cost_bottom_up"])


def test_marginal_cost_is_difference_over_capped():
    cfg = _cfg()
    t = V.marginal_cost_table(_front(), C.CostParams.from_config(cfg), 44, 345, 86)
    floor, full = t.iloc[0], t.iloc[1]
    assert floor["incremental_dollars"] == 24000
    assert floor["incremental_checks"] == 301
    assert floor["dollars_per_incremental_violator"] == round(24000 / 72)
    assert full["incremental_dollars"] == 30000
    assert full["topdown_high_incremental"] == 400 * 387  # full-cost sensitivity, not headline


def test_marginal_cost_missing_row_raises():
    with pytest.raises(KeyError):
        V.marginal_cost_table(_front(), C.CostParams.from_config(_cfg()), 50, 345, 86)


def test_break_even_parity_when_per_dollar_equal():
    # census reduces exposure exactly in proportion to cost: achieved == required
    grid = pd.DataFrame({"response": ["r"], "capped_reduction": [0.02], "census_reduction": [0.20]})
    t = V.break_even_table(grid, cap_cost=3000.0, cen_cost=30000.0, baseline_events=88.0)
    assert t.loc[0, "achieved_over_required"] == pytest.approx(
        (100 * 0.18) / (100 * 0.02 / 3000 * 27000), abs=0.01
    )
    assert t.loc[0, "dollars_per_prevented_violation"] == round(27000 / (0.18 * 88))


def test_break_even_no_response_gives_nan_not_division_error():
    grid = pd.DataFrame(
        {"response": ["none"], "capped_reduction": [0.0], "census_reduction": [0.0]}
    )
    t = V.break_even_table(grid, 3000.0, 30000.0, 88.0)
    assert np.isnan(t.loc[0, "dollars_per_point"])


def test_opportunity_shares():
    t = V.opportunity_cost_table(
        C.CostParams.from_config(_cfg()), 345, 30000.0, 387, 44, 2900, 1_000_000.0
    ).set_index("measure")["value"]
    assert t["Pittsburgh share of PA published checks today"] == pytest.approx(44 / 2900)
    assert t["Incremental marginal dollars as share of annual award"] == pytest.approx(0.03)


def test_whatif_calendar_scales_with_teams():
    rng = np.random.default_rng(0)
    xy = rng.random((31, 2)) * 5
    travel = np.sqrt(((xy[:, None] - xy[None]) ** 2).sum(-1))
    t = V.whatif_census(travel, C.CostParams.from_config(_cfg()), day_hours=(8,), teams=(1, 2))
    one, two = t.iloc[0], t.iloc[1]
    assert one["bottom_up_dollars"] == two["bottom_up_dollars"]  # teams change time, not cost
    assert two["calendar_workdays"] == -(-int(one["team_days"]) // 2)


def test_whatif_capped_budget_binds():
    s = pd.DataFrame({"route_minutes": [113.2, 86.7]})
    t = V.whatif_capped(s, (4, 8), (1, 3))
    assert t["route_fits_in_one_day"].all()
    assert set(t["binding_constraint"]) == {"budget (stores per cycle)"}


def test_lambda_robustness_baseline_overlaps_fully():
    cfg = _cfg()
    rng = np.random.default_rng(1)
    n = 40
    cand = pd.DataFrame(
        {
            "h": rng.random(n),
            "p": rng.random(n) * 0.5,
            "deterrence": rng.random(n),
            "tract_geoid": [str(i % 7) for i in range(n)],
        }
    )
    t = V.lambda_robustness(cfg, cand, [0.0, cfg.prize["lambda_deterrence"]], budget=11)
    base = t[t["is_baseline"]].iloc[0]
    assert base["overlap_with_baseline"] == 11
    assert cfg.prize["lambda_deterrence"] == 0.25  # the deepcopy left the loaded config untouched
