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


# --------------------------------------------------------------------------- team orienteering
@dataclass
class Plan:
    """Result of a multi-route plan. `routes` hold candidate indices (1..n-1) in visiting order."""

    routes: list[list[int]]
    prize: float
    times: list[float]
    solver: str = ""
    status: str = ""

    @property
    def visited(self) -> list[int]:
        return [i for r in self.routes for i in r]


def _route_time(order, travel, service) -> float:
    if not order:
        return 0.0
    legs = zip([0, *order], [*order, 0], strict=True)
    return float(sum(travel[a][b] for a, b in legs) + sum(service[i] for i in order))


def pick_solver(preferred: str = "gurobi") -> str:
    """First available MILP solver, preferring `preferred` (Gurobi, then HiGHS)."""
    for name in (preferred, "appsi_highs", "gurobi"):
        if pyo.SolverFactory(name).available(exception_flag=False):
            return name
    raise RuntimeError("no MILP solver available (Gurobi license or `uv sync --extra fallback`)")


def solve_team_orienteering(
    prizes,
    travel,
    service,
    day_minutes: float,
    n_routes: int,
    budget: int,
    floors: list[tuple[list[int], int]] | None = None,
    solver: str = "gurobi",
    time_limit: float = 60.0,
    mip_gap: float = 0.0,
    time_weight: float = 1e-5,
) -> Plan:
    """Budgeted team orienteering with route slots (team x day), at most one visit per store.

    Node 0 is the depot. Each route slot r is a tour from the depot of at most `day_minutes`
    (travel + service). Total visits <= `budget`; each store at most once overall;
    `floors` = [(candidate indices, minimum visits)] enforce coverage floors. Slots are
    interchangeable, so route sizes are ordered to break symmetry. Per-route MTZ constraints
    eliminate subtours. Falls back from Gurobi to HiGHS if the model exceeds a size-limited
    license.
    """
    n = len(prizes)
    if n < 2:
        return Plan([], 0.0, [], "", "empty")
    nodes, cust, slots = range(n), range(1, n), range(n_routes)
    m = pyo.ConcreteModel()
    m.x = pyo.Var(nodes, nodes, slots, within=pyo.Binary)
    m.y = pyo.Var(cust, slots, within=pyo.Binary)
    m.u = pyo.Var(cust, slots, bounds=(1, n - 1))
    # Prize first; among equal-prize plans prefer less travel (tiny `time_weight` per minute).
    m.obj = pyo.Objective(
        expr=sum(prizes[i] * m.y[i, r] for i in cust for r in slots)
        - time_weight
        * sum(travel[i][j] * m.x[i, j, r] for i in nodes for j in nodes if i != j for r in slots),
        sense=pyo.maximize,
    )
    m.no_self = pyo.Constraint(nodes, slots, rule=lambda m, i, r: m.x[i, i, r] == 0)
    m.out = pyo.Constraint(
        cust, slots, rule=lambda m, i, r: sum(m.x[i, j, r] for j in nodes) == m.y[i, r]
    )
    m.into = pyo.Constraint(
        cust, slots, rule=lambda m, j, r: sum(m.x[i, j, r] for i in nodes) == m.y[j, r]
    )
    m.depot_out = pyo.Constraint(slots, rule=lambda m, r: sum(m.x[0, j, r] for j in cust) <= 1)
    m.depot_bal = pyo.Constraint(
        slots,
        rule=lambda m, r: sum(m.x[0, j, r] for j in cust) == sum(m.x[i, 0, r] for i in cust),
    )
    m.once = pyo.Constraint(cust, rule=lambda m, i: sum(m.y[i, r] for r in slots) <= 1)
    m.budget = pyo.Constraint(expr=sum(m.y[i, r] for i in cust for r in slots) <= budget)

    def mtz(m, i, j, r):
        if i == j:
            return pyo.Constraint.Skip
        return m.u[i, r] - m.u[j, r] + (n - 1) * m.x[i, j, r] <= n - 2

    m.mtz = pyo.Constraint(cust, cust, slots, rule=mtz)
    m.time = pyo.Constraint(
        slots,
        rule=lambda m, r: (
            sum(travel[i][j] * m.x[i, j, r] for i in nodes for j in nodes if i != j)
            + sum(service[i] * m.y[i, r] for i in cust)
            <= day_minutes
        ),
    )
    if n_routes > 1:
        m.sym = pyo.Constraint(
            range(n_routes - 1),
            rule=lambda m, r: sum(m.y[i, r] for i in cust) >= sum(m.y[i, r + 1] for i in cust),
        )
    for k, (idx, minimum) in enumerate(floors or []):
        setattr(
            m,
            f"floor_{k}",
            pyo.Constraint(expr=sum(m.y[i, r] for i in idx for r in slots) >= minimum),
        )

    name = pick_solver(solver)
    plan = _solve(m, name, time_limit, mip_gap)
    if plan is None:  # size-limited license or similar: retry with the open-source solver
        name = "appsi_highs"
        plan = _solve(m, name, time_limit, mip_gap)
    if plan is None:
        raise RuntimeError("no solver could solve the team-orienteering model")
    status = plan
    if "infeasible" in status.lower():
        raise ValueError(
            f"team-orienteering model is infeasible: check floors, budget and day length ({status})"
        )
    routes = []
    for r in slots:
        succ = {i: j for i in nodes for j in nodes if i != j and pyo.value(m.x[i, j, r]) > 0.5}
        order, cur = [], succ.get(0)
        while cur not in (None, 0):
            order.append(cur)
            cur = succ.get(cur)
        if order:
            routes.append(order)
    return Plan(
        routes,
        float(sum(prizes[i] for r in routes for i in r)),
        [_route_time(r, travel, service) for r in routes],
        name,
        status,
    )


def _solve(m, name: str, time_limit: float, mip_gap: float):
    opt = pyo.SolverFactory(name)
    try:
        if name == "gurobi":
            opt.options["TimeLimit"], opt.options["MIPGap"] = time_limit, mip_gap
        else:
            opt.options["time_limit"], opt.options["mip_rel_gap"] = time_limit, mip_gap
        res = opt.solve(m)
        return str(res.solver.termination_condition)
    except Exception as exc:
        print(f"{name} failed ({str(exc)[:120]}); trying fallback")
        return None


def plan_ranked_batched(
    prizes,
    travel,
    service,
    day_minutes: float,
    n_routes: int,
    budget: int,
    floors: list[tuple[list[int], int]] | None = None,
) -> Plan:
    """Gate-B comparator: rank by prize, pick the top `budget` (floors first), then batch.

    Batching: take the highest-prize unassigned store as a route seed and repeatedly add the
    nearest unassigned selected store while the day fits. No optimization of which stores to take.
    """
    n = len(prizes)
    chosen: list[int] = []
    for idx, minimum in floors or []:
        ranked = sorted(idx, key=lambda i: -prizes[i])
        chosen += [i for i in ranked if i not in chosen][:minimum]
    for i in sorted(range(1, n), key=lambda i: -prizes[i]):
        if len(chosen) >= budget:
            break
        if i not in chosen:
            chosen.append(i)
    chosen = chosen[:budget]
    remaining, routes = set(chosen), []
    while remaining and len(routes) < n_routes:
        seed = max(remaining, key=lambda i: prizes[i])
        remaining.discard(seed)
        if _route_time([seed], travel, service) > day_minutes:
            continue  # cannot be visited within one day at all
        route = [seed]
        while remaining:
            nxt = min(remaining, key=lambda j: travel[route[-1]][j])
            if _route_time([*route, nxt], travel, service) > day_minutes:
                break
            route.append(nxt)
            remaining.discard(nxt)
        routes.append(route)
    return Plan(
        routes,
        float(sum(prizes[i] for r in routes for i in r)),
        [_route_time(r, travel, service) for r in routes],
        "heuristic",
        "ranked+batched",
    )
