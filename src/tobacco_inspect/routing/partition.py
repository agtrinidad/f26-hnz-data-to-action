"""Partition every store into day-long routes (a census: visit all locations once).

This is a capacitated vehicle-routing problem with a depot (node 0), travel times in minutes
(`travel[i][j]`, possibly asymmetric: one-way streets) and a per-stop time (`service[i]`). The
objective is the fewest team-days, then the least driving. The heuristic is "route first, split
second": build one good tour through all stores (nearest neighbor + 2-opt), then cut it optimally
into consecutive pieces that each fit in a day (dynamic program), then polish each route.

Held-Karp gives exact optimal tours for small groups, used to measure the heuristic's gap.
"""

from __future__ import annotations

import numpy as np


def route_minutes(order, travel, service) -> float:
    """Depot -> stops in `order` -> depot: driving plus time at stops (minutes)."""
    if not len(order):
        return 0.0
    path = [0, *order, 0]
    drive = sum(travel[a][b] for a, b in zip(path[:-1], path[1:], strict=True))
    return float(drive + sum(service[i] for i in order))


def nearest_neighbor_order(nodes, travel, start: int = 0) -> list[int]:
    left, order, cur = set(nodes), [], start
    while left:
        nxt = min(left, key=lambda j: travel[cur][j])
        order.append(nxt)
        left.discard(nxt)
        cur = nxt
    return order


def two_opt_symmetric(order, sym: np.ndarray, max_passes: int = 50) -> list[int]:
    """2-opt on a symmetric cost matrix with O(1) move evaluation (depot = node 0)."""
    route = [0, *order, 0]
    n = len(route)
    for _ in range(max_passes):
        improved = False
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                a, b, c, d = route[i - 1], route[i], route[j], route[j + 1]
                if sym[a, c] + sym[b, d] < sym[a, b] + sym[c, d] - 1e-9:
                    route[i : j + 1] = route[i : j + 1][::-1]
                    improved = True
        if not improved:
            break
    return route[1:-1]


def two_opt_directed(order, travel, service, max_passes: int = 50) -> list[int]:
    """2-opt for one (short) route using the true directed times; never lengthens the route."""
    best = list(order)
    best_cost = route_minutes(best, travel, service)
    for _ in range(max_passes):
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                cand = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                cost = route_minutes(cand, travel, service)
                if cost < best_cost - 1e-9:
                    best, best_cost, improved = cand, cost, True
        if not improved:
            break
    return best


def split_giant_tour(tour, travel, service, day_minutes: float, max_stops: int = 40):
    """Optimal split of `tour` into consecutive routes, each <= `day_minutes`.

    Minimizes (number of routes, total minutes) lexicographically. Raises if a single store
    cannot fit in a day.
    """
    n = len(tour)
    inf = (10**9, float("inf"))
    best = [inf] * (n + 1)
    prev = [-1] * (n + 1)
    best[0] = (0, 0.0)
    for i in range(n):
        if best[i] == inf:
            continue
        for j in range(i, min(n, i + max_stops)):
            seg = tour[i : j + 1]
            cost = route_minutes(seg, travel, service)
            if cost > day_minutes:
                if j == i:
                    raise ValueError(
                        f"store {tour[i]} alone exceeds the day limit ({cost:.0f} min)"
                    )
                break
            cand = (best[i][0] + 1, best[i][1] + cost)
            if cand < best[j + 1]:
                best[j + 1], prev[j + 1] = cand, i
    routes, j = [], n
    while j > 0:
        i = prev[j]
        routes.append(tour[i:j])
        j = i
    return routes[::-1]


def census_routes(travel, service, day_minutes: float, nodes=None, polish: bool = True):
    """Routes covering every node in `nodes` (default 1..n-1) exactly once, each within a day.

    Returns a list of routes (lists of node indices). Asserts coverage and the day limit.
    """
    travel = np.asarray(travel, dtype=float)
    n = travel.shape[0]
    nodes = list(range(1, n)) if nodes is None else list(nodes)
    sym = (travel + travel.T) / 2
    tour = two_opt_symmetric(nearest_neighbor_order(nodes, sym), sym)
    routes = split_giant_tour(tour, travel, service, day_minutes)
    if polish:
        routes = [two_opt_directed(r, travel, service) for r in routes]
    check_routes(routes, travel, service, day_minutes, nodes)
    return routes


def check_routes(routes, travel, service, day_minutes: float, nodes) -> None:
    """Every store exactly once; every route within the day limit."""
    flat = [i for r in routes for i in r]
    assert sorted(flat) == sorted(nodes), "routes must cover every store exactly once"
    for r in routes:
        assert route_minutes(r, travel, service) <= day_minutes + 1e-6, "route exceeds the day"


def held_karp(nodes, travel, service) -> tuple[float, list[int]]:
    """Exact minimum-time tour through `nodes` from/to the depot (n <= about 13)."""
    nodes = list(nodes)
    n = len(nodes)
    if n == 0:
        return 0.0, []
    full = 1 << n
    inf = float("inf")
    dp = [[inf] * n for _ in range(full)]
    parent = [[-1] * n for _ in range(full)]
    for k in range(n):
        dp[1 << k][k] = travel[0][nodes[k]]
    for mask in range(full):
        for last in range(n):
            if not mask & (1 << last) or dp[mask][last] == inf:
                continue
            for nxt in range(n):
                if mask & (1 << nxt):
                    continue
                m2 = mask | (1 << nxt)
                cost = dp[mask][last] + travel[nodes[last]][nodes[nxt]]
                if cost < dp[m2][nxt]:
                    dp[m2][nxt], parent[m2][nxt] = cost, last
    last = min(range(n), key=lambda k: dp[full - 1][k] + travel[nodes[k]][0])
    best = dp[full - 1][last] + travel[nodes[last]][0]
    order, mask = [], full - 1
    while last != -1:
        order.append(nodes[last])
        mask, last = mask ^ (1 << last), parent[mask][last]
    order.reverse()
    return float(best + sum(service[i] for i in nodes)), order


def heuristic_gap(routes, travel, service, size: int = 9, seed: int = 0, trials: int = 20):
    """Heuristic tour vs the exact optimum on random `size`-store subsets of routes."""
    rng = np.random.default_rng(seed)
    gaps = []
    pool = [r for r in routes if len(r) >= size]
    for _ in range(trials):
        if not pool:
            break
        r = pool[rng.integers(len(pool))]
        sub = [r[i] for i in sorted(rng.choice(len(r), size, replace=False))]
        exact, _ = held_karp(sub, travel, service)
        sym = (np.asarray(travel) + np.asarray(travel).T) / 2
        heur = route_minutes(
            two_opt_directed(
                two_opt_symmetric(nearest_neighbor_order(sub, sym), sym), travel, service
            ),
            travel,
            service,
        )
        gaps.append(heur / exact - 1)
    return gaps


__all__ = [
    "census_routes",
    "route_minutes",
    "split_giant_tour",
    "held_karp",
    "two_opt_directed",
    "two_opt_symmetric",
    "nearest_neighbor_order",
    "check_routes",
    "heuristic_gap",
]
