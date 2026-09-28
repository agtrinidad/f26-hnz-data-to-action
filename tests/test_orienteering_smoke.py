"""Toy 5-node instance: validates Pyomo + solver wiring, not the real model."""

import pyomo.environ as pyo
import pytest

from tobacco_inspect.model.orienteering import solve_orienteering

TRAVEL = [
    [0, 10, 10, 30, 30],
    [10, 0, 5, 30, 30],
    [10, 5, 0, 30, 30],
    [30, 30, 30, 0, 5],
    [30, 30, 30, 5, 0],
]
PRIZES = [0, 5, 6, 20, 1]
SERVICE = [0, 2, 2, 2, 2]


def _solver():
    for name in ("gurobi", "appsi_highs"):
        if pyo.SolverFactory(name).available(exception_flag=False):
            return name
    pytest.skip("no MILP solver available (Gurobi license or highspy)")


def test_tight_budget_picks_nearby_pair():
    # Cluster {1,2}: 10+5+10 travel + 4 service = 29 <= 30; prize 11.
    route = solve_orienteering(PRIZES, TRAVEL, SERVICE, budget=30, solver=_solver())
    assert sorted(route.visited) == [1, 2]
    assert route.prize == 11
    assert route.time <= 30 + 1e-6


def test_large_budget_can_reach_far_cluster():
    # Far cluster {3,4}: 30+5+30 travel + 4 service = 69 for prize 21.
    route = solve_orienteering(PRIZES, TRAVEL, SERVICE, budget=70, solver=_solver())
    assert route.prize >= 21
    assert route.time <= 70 + 1e-6
