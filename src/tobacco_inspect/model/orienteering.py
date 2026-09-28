"""Budgeted prize-collecting TSP / orienteering MILP (Pyomo).

`solve_orienteering` is the single-team, single-day core (MTZ subtour elimination), used to
validate the toolchain. The full model (teams k, weekdays d, weekly mileage, budget B, coverage
floors m_S, at-most-once per horizon) extends it. See docs/decision-card.md for the formulation.

TODO: extend to team orienteering with days.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyomo.environ as pyo


@dataclass(frozen=True)
class Route:
    visited: list[int]  # node indices in visiting order, excluding the depot
    prize: float
    time: float


def solve_orienteering(
    prizes: list[float],
    travel: list[list[float]],
    service: list[float],
    budget: float,
    solver: str = "gurobi",
) -> Route:
    """Maximize collected prize on a tour from depot (node 0) within a time budget.

    `prizes[0]`/`service[0]` are for the depot and are ignored. `travel[i][j]` is the time
    from i to j. The tour must return to the depot.
    """
    n = len(prizes)
    if n < 2:
        return Route([], 0.0, 0.0)
    nodes = range(n)
    customers = range(1, n)

    m = pyo.ConcreteModel()
    m.x = pyo.Var(nodes, nodes, within=pyo.Binary)
    m.y = pyo.Var(customers, within=pyo.Binary)
    m.u = pyo.Var(customers, bounds=(1, n - 1))
    m.obj = pyo.Objective(expr=sum(prizes[i] * m.y[i] for i in customers), sense=pyo.maximize)

    m.no_self = pyo.Constraint(nodes, rule=lambda m, i: m.x[i, i] == 0)
    m.out = pyo.Constraint(customers, rule=lambda m, i: sum(m.x[i, j] for j in nodes) == m.y[i])
    m.into = pyo.Constraint(customers, rule=lambda m, j: sum(m.x[i, j] for i in nodes) == m.y[j])
    m.depot_out = pyo.Constraint(expr=sum(m.x[0, j] for j in customers) <= 1)
    m.depot_in = pyo.Constraint(
        expr=sum(m.x[0, j] for j in customers) == sum(m.x[i, 0] for i in customers)
    )

    def mtz(m, i, j):
        if i == j:
            return pyo.Constraint.Skip
        return m.u[i] - m.u[j] + (n - 1) * m.x[i, j] <= n - 2

    m.mtz = pyo.Constraint(customers, customers, rule=mtz)
    m.time = pyo.Constraint(
        expr=sum(travel[i][j] * m.x[i, j] for i in nodes for j in nodes if i != j)
        + sum(service[i] * m.y[i] for i in customers)
        <= budget
    )

    opt = pyo.SolverFactory(solver)
    if not opt.available(exception_flag=False):
        raise RuntimeError(f"solver {solver!r} is not available")
    opt.solve(m)

    succ = {i: j for i in nodes for j in nodes if i != j and pyo.value(m.x[i, j]) > 0.5}
    order: list[int] = []
    cur = succ.get(0)
    while cur not in (None, 0):
        order.append(cur)
        cur = succ.get(cur)
    legs = zip([0, *order], [*order, 0], strict=True)
    total_time = sum(travel[a][b] for a, b in legs) if order else 0.0
    total_time += sum(service[i] for i in order)
    return Route(order, float(sum(prizes[i] for i in order)), float(total_time))
