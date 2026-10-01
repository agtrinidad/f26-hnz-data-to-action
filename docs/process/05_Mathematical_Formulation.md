# Memo 05: Mathematical formulation of the inspection-scheduling model

**Project:** Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA
**Date:** 2026-09-30. **Companion files:** [memo 03 (implementation and results)](03_Implementation_Results.md),
[memo 04 (census scenario)](04_Census_Inspection_Scenario.md), [assumptions](../assumptions.md), `config/default.yaml`.

Written for the project team and for a reader who wants to check that the policy description (budgeted prize-collecting TSP, Harrington
targeting, vulnerable-site externality proxy, Stackelberg-style randomization) matches what the code actually optimizes. Each equation names the
source file that implements it. Where the code is simpler than the policy text, section 7 says so.

---

## 1. Summary of the approach

The model has two layers, and only the second is an optimization problem in the strict sense.

1. **Prediction and prize construction (not optimized).** Each distinct retail location $i$ gets a violation probability $p_i$ from a
   regularized logistic regression, an exposure proxy $h_i$ for the harm a violation causes, and a follow-up term $\delta_i$ from the
   Harrington-style enforcement state. These combine into a unit-free **prize** $r_i$.
2. **Cycle planning (optimized).** Each monthly cycle, the prizes are *randomized* (Thompson sampling), a share of slots is reserved for a
   simple random draw, and a **budgeted team orienteering problem** (a budgeted prize-collecting TSP with several routes) selects and orders
   stores to maximize collected prize.

This is predict-then-optimize: the prize enters the integer program as a plain coefficient (ADR 0003).

---

## 2. Notation

| Symbol | Meaning | Value / source |
|---|---|---|
| $\mathcal N$ | Candidate retail locations (one row per physical location) | 345 in city limits |
| $0$ | Depot (team base) | downtown Pittsburgh (`solve.depot`) |
| $\mathcal V = \{0\}\cup\mathcal M$ | Nodes of one cycle's routing graph | $\mathcal M \subseteq \mathcal N$ is the cycle's candidate set |
| $c \in \{1,\dots,C\}$ | Monthly cycle | $C=\lfloor 13/4\rfloor = 3$ |
| $\mathcal K = \{1,\dots,K\}$ | Route slots (team $\times$ day) in a cycle | $K=\min(\text{teams}\cdot\text{cycle days},\,B_c)$ |
| $t_{ij}$ | Drive time from $i$ to $j$, minutes | OSM drive-time matrix |
| $s$ | On-site service time per check | 20 min |
| $L$ | Length of a route day | 480 min (8 h) |
| $B$, $B_c$ | Inspection budget per horizon, per cycle | $B=11$, $B_c=\lceil B/C\rceil = 4$ |
| $\rho$ | Reserved random share | 0.20 |
| $\lambda$ | Weight on the follow-up (deterrence) term | 0.25 |
| $\kappa$ | Thompson prior strength (pseudo-checks) | 5 |
| $M$ | Candidate-pool size entering the MILP | 30 |

---

## 3. Layer 1: the prize

### 3.1 Prize definition (`model/prize.py`, `compute_prizes`)

$$
r_i \;=\; h_i\,p_i \;+\; \lambda\,\delta_i
$$

- $h_i\,p_i$ is **expected externality**: probability of a violation times the harm proxy if one occurs. This is the "minimize the consequences
  of noncompliance" idea in the policy text.
- $\lambda\,\delta_i$ is the **follow-up value** of checking store $i$ now (section 3.4).
- $r_i$ is unit-free. It is a ranking score, not a dollar figure.

### 3.2 Violation probability $p_i$ (`model/risk.py`)

$$
\hat p^{\,\text{raw}}_i = \sigma\!\big(\beta_0 + \beta^{\top}\phi_i\big),
\qquad
p_i = \sigma\!\big(\operatorname{logit}(\hat p^{\,\text{raw}}_i) + \Delta\big)
$$

$\phi_i$ holds the features in `model/history.py` (log prior checks, log prior violations, prior violation share, violations in the last 12/24/36
months, log days since last check and since last violation, log chain size, prior fiscal-year rate, outlet type). $\beta$ is fit with $L_2$
regularization (strength $C$ chosen by validating on the last fiscal year). The intercept shift $\Delta$ solves

$$
\frac{1}{|\mathcal N|}\sum_{i\in\mathcal N}\sigma\!\big(\operatorname{logit}(\hat p^{\,\text{raw}}_i)+\Delta\big) = \bar p_{\text{Synar}}
$$

so that the mean of $p_i$ equals the Synar Allegheny random-sample rate (26%). The shift moves levels but not the ranking. It corrects for the
FDA sample covering only stores that were chosen for inspection.

### 3.3 Exposure proxy $h_i$ (`model/prize.py`, `exposure_h`)

No per-store sales volume or health-cost data exists, so exposure is proximity to vulnerable sites, tract youth share, and past severity:

$$
h_i \;=\; w_1\,\text{site}_i \;+\; w_2\,\text{youth}_i \;+\; w_3\,\text{sev}_i,
\qquad (w_1,w_2,w_3)=(0.4,\,0.3,\,0.3)
$$

$$
\text{site}_i = 0.7\,\pi^{\text{school}}_i + 0.3\,\pi^{\text{youth site}}_i,
\qquad
\pi_i = \tfrac12 e^{-d_i/\ell} + \tfrac12\,\frac{\min(n_i,\,\bar n)}{\bar n}
$$

where $d_i$ is the distance to the nearest site, $n_i$ the count of sites within 300 m, and $(\ell,\bar n) = (300\text{ m},3)$ for schools and
$(150\text{ m},5)$ for other youth sites (libraries, community centers, playgrounds). $\text{youth}_i$ is the tract's under-age share, shrunk
toward the city median by an empirical-Bayes weight that accounts for the ACS margin of error, then rescaled to $[0,1]$. $\text{sev}_i =
\min(\text{points}_i, 8)/8$, with points 1 / 2 / 4 for a warning letter / civil money penalty / no-tobacco-sale order.

All three components lie in $[0,1]$ and the weights sum to 1, so $h_i\in[0,1]$.

### 3.4 Harrington-style follow-up term $\delta_i$ (`model/harrington.py`)

The enforcement state of store $i$ is its escalation depth $q_i=\min(v^{36}_i,4)$, where $v^{36}_i$ counts violations in the trailing 36
months. This mirrors FDA's escalating penalty ladder (HHS-OIG Exhibit 3). A store is **targeted** if $v^{24}_i\ge 1$ and **untargeted**
otherwise.

$$
\delta_i \;=\; \omega_{q_i}\cdot \min\!\Big(1,\ \frac{\text{days since last check}_i}{365}\Big),
\qquad \omega=(0.25,\,0.6,\,0.8,\,1.0,\,1.0)
$$

So $\delta_i\in[0,1]$ grows with time since the last inspection (the policy text's "greater time since past inspection") and with prior
noncompliance. An untargeted store keeps a small recency credit ($\omega_0=0.25$) rather than dropping to zero. The weights $\omega$ and
$\lambda$ are **assumptions**; no data we hold identifies a deterrence effect.

**Interpreting $\lambda$.** $\lambda$ (`prize.lambda_deterrence`, currently 0.25) is the weight that puts the follow-up term on the same
scale as expected externality. It says how much extra a check is worth because the store is recently noncompliant and has gone unchecked, over
and above its current violation risk. A store with maximum urgency ($\delta_i=1$) gains 0.25 in prize. Because $h_i p_i$ is a product of two
values in $[0,1]$ and $p_i$ averages about 0.26, typical $h_i p_i$ values are small, so 0.25 is not a minor nudge: for a store with
$h_i p_i\approx0.1$, a full $\delta_i$ more than doubles its prize. Setting $\lambda=0$ removes the term and ranks stores on expected
externality alone. Two cautions apply. First, $\lambda$ was not tuned or estimated, so it should be reported with a sensitivity sweep (for
example $\lambda\in\{0,\,0.1,\,0.25,\,0.5\}$) rather than defended as a point value. Second, prior violations already enter $p_i$ and are
counted again through $\omega_{q_i}$, so a larger $\lambda$ increases that overlap.

---

## 4. Layer 2: one planning cycle

### 4.1 Randomization before optimization (`model/thompson.py`, `pipeline.plan_cycle`)

Let $\mathcal E_c$ be the stores not yet visited in earlier cycles of the horizon.

**Thompson draw of the violation rate.** For each $i\in\mathcal E_c$:

$$
\tilde p_i \sim \operatorname{Beta}\big(\kappa p_i,\ \kappa(1-p_i)\big),
\qquad
\tilde r_i = h_i\,\tilde p_i + \lambda\,\delta_i
$$

The prior is centered on $p_i$, so the store's own history is not counted twice. $\kappa$ sets only how much the draw varies around $p_i$.

**Reserved random share.** Draw a set $\mathcal F_c\subseteq\mathcal E_c$ of size

$$
|\mathcal F_c| = \min\big(\max(1,\operatorname{round}(\rho B_c)),\ B_c,\ |\mathcal E_c|\big)
$$

uniformly without replacement. These stores are **forced** into the plan.

**Candidate pool.** From the remaining stores take the $M$ with the highest $\tilde r_i$, call this $\mathcal T_c$, and set
$\mathcal M = \mathcal F_c\cup\mathcal T_c$. This is a heuristic restriction that keeps the MILP small. It is not part of the optimization.

### 4.2 The budgeted team orienteering MILP (`model/orienteering.py`, `solve_team_orienteering`)

Let $\mathcal V=\{0\}\cup\mathcal M$, $n=|\mathcal V|$, and $\mathcal M$ the customers.

**Decision variables**

$$
x_{ijk}\in\{0,1\}\ \ (i\ne j\in\mathcal V,\ k\in\mathcal K):\ \text{route } k \text{ drives } i\to j
$$
$$
y_{ik}\in\{0,1\}\ \ (i\in\mathcal M,\ k\in\mathcal K):\ \text{route } k \text{ inspects store } i
$$
$$
u_{ik}\in[1,\,n-1]\ \ (i\in\mathcal M,\ k\in\mathcal K):\ \text{visit-order position (subtour elimination)}
$$

**Objective.** Maximize collected prize, with a negligible travel-time tie-breaker ($\varepsilon = 10^{-5}$ per minute):

$$
\max\ \sum_{k\in\mathcal K}\sum_{i\in\mathcal M}\tilde r_i\,y_{ik}\;-\;\varepsilon\sum_{k\in\mathcal K}\sum_{i\in\mathcal V}\sum_{j\in\mathcal V,\,j\ne i}t_{ij}\,x_{ijk}
\tag{1}
$$

**Constraints**

$$
\sum_{j\in\mathcal V} x_{ijk}=y_{ik}\quad\forall i\in\mathcal M,\ k\in\mathcal K
\tag{2a}
$$
$$
\sum_{i\in\mathcal V} x_{ijk}=y_{jk}\quad\forall j\in\mathcal M,\ k\in\mathcal K
\tag{2b}
$$
$$
\sum_{j\in\mathcal M} x_{0jk}\le 1,\qquad
\sum_{j\in\mathcal M} x_{0jk}=\sum_{i\in\mathcal M} x_{i0k}\quad\forall k\in\mathcal K
\tag{3}
$$
$$
u_{ik}-u_{jk}+(n-1)\,x_{ijk}\le n-2\quad\forall i\ne j\in\mathcal M,\ k\in\mathcal K
\tag{4}
$$
$$
\sum_{i\in\mathcal V}\sum_{j\in\mathcal V,\,j\ne i}t_{ij}\,x_{ijk}\;+\;s\sum_{i\in\mathcal M}y_{ik}\;\le\;L\quad\forall k\in\mathcal K
\tag{5}
$$
$$
\sum_{k\in\mathcal K}y_{ik}\le 1\quad\forall i\in\mathcal M
\tag{6}
$$
$$
\sum_{k\in\mathcal K}\sum_{i\in\mathcal M}y_{ik}\le B_c
\tag{7}
$$
$$
\sum_{k\in\mathcal K}\sum_{i\in\mathcal F_c}y_{ik}\ \ge\ |\mathcal F_c|
\tag{8}
$$
$$
\sum_{i\in\mathcal M}y_{ik}\ \ge\ \sum_{i\in\mathcal M}y_{i,k+1}\quad k=1,\dots,K-1
\tag{9}
$$

| Constraint | Role |
|---|---|
| (2a)-(2b) | Flow conservation: a store is entered and left exactly once if and only if route $k$ inspects it |
| (3) | Each route starts and ends at the depot (or is unused) |
| (4) | Miller-Tucker-Zemlin subtour elimination, one set per route |
| (5) | **Capacity:** drive time plus on-site time fits in a working day |
| (6) | Each store is inspected at most once per cycle |
| (7) | **Budget:** at most $B_c$ inspections per cycle |
| (8) | **Coverage floor:** every randomly reserved store must be included. With $\mathcal F_c$ chosen at random, this is the random-share guarantee. Equivalent to $y_{ik}$ summed to 1 for each forced store |
| (9) | Symmetry breaking only: route slots are interchangeable, so they are ordered by size. Does not change the optimum |

Routes use the same depot, so $\mathcal K$ indexes route-days. A route's team and calendar date are assigned *after* solving (section 4.4).

### 4.3 Special case: single route

With $K=1$, no floor, and $B_c=\infty$, (1)-(7) reduce to the classical **orienteering problem** (a prize-collecting TSP with a hard time budget),
which `solve_orienteering` implements. The multi-route model above is its budgeted team extension.

### 4.4 After the solve (`pipeline.solve`)

The solved routes receive a team index $k \bmod \text{teams}$ and a workday drawn at random without replacement from the cycle's working days
(Mon-Fri, minus federal holidays). The scheduled date is therefore unpredictable to the store. Stores visited are added to the visited set
$\mathcal V^{\text{visited}}$ and removed from $\mathcal E_{c+1}$, so across the horizon

$$
\sum_{c=1}^{C}\sum_{k}\sum_i y^{(c)}_{ik}\le 1\ \text{ for each store},
\qquad
\sum_{c}\sum_{k}\sum_i y^{(c)}_{ik}\le \textstyle\sum_c B_c .
$$

Each cycle's problem is solved separately and greedily in time (a rolling horizon), not jointly.

---

## 5. The two-stage object, written as one expectation

Over the whole horizon, the schedule is a random variable. Writing $S_c(\omega)$ for the set of stores inspected in cycle $c$, where $\omega$
bundles the Thompson draws, the random-share draw and the date draw:

$$
\max_{\text{policy}}\ \ \mathbb E_\omega\Big[\sum_{c=1}^{C}\sum_{i\in S_c(\omega)} \tilde r_i(\omega)\Big]
\quad\text{s.t. (2)-(9) in every cycle, and no store is repeated.}
$$

The policy is the mapping from (prizes, travel times, budget) to a randomized plan. Its **inspection probability** for store $i$ is

$$
\pi_i = \Pr\big(i\in S_c\text{ for some } c\big),
$$

which is high for high-prize stores, positive for every store through the random share $\rho$, and below 1 so that no store can be certain of
being checked.

---

## 6. How this maps to the policy text

| Policy statement | Where it appears in the math |
|---|---|
| Budgeted prize-collecting TSP: maximize benefit collected within capacity, not visit every node | Objective (1) with capacity (5) and budget (7); only a subset of nodes is visited |
| Prizes are risk scores that weigh consequences of noncompliance | $r_i = h_i p_i + \lambda\delta_i$ |
| Higher potential externality | $h_i$: vulnerable-site proximity, tract youth share, severity (3.3) |
| Greater time since past inspection | Recency factor inside $\delta_i$ (3.4) |
| Prior noncompliance | $p_i$ features, the severity term in $h_i$, and $\omega_{q_i}$ |
| Harrington targeted / untargeted groups | $q_i$ (escalation depth) and the targeted flag $v^{24}_i\ge1$, entering through $\omega_{q_i}$ |
| Stackelberg: agency commits to a schedule, stores respond | Randomized commitment: Thompson draws (4.1), reserved random share (8), random dates (4.4) |
| Bounded rationality: stores know they *can* be checked, not *whether* they will | $0<\pi_i<1$ for every store |
| Staffing and cost limits | $K$, $L$ in (5), and $B_c$ in (7) |

---

## 7. Where the code is simpler than the policy text

These gaps are deliberate or forced by data. They should be stated whenever the model is described.

1. **No bilevel game.** The Stackelberg idea is carried by *randomization*, not by solving a leader-follower program. Stores' best responses are
   not modeled in the optimization. They appear only in the simulation experiments (`eval/simulate.py`), under assumed behavior.
2. **Deterrence is an assumption.** $\lambda$ and $\omega$ are not estimated. Anything that depends on them is labeled "assumed" (memo 03).
3. **Exposure is a proxy.** $h_i$ is a unit-free proximity-and-youth score. There are no per-store sales volumes or dollar health costs.
4. **Days are not indexed in the MILP.** The decision card describes team $\times$ weekday indices, a weekly mileage cap and a per-tract floor.
   The implemented model uses route slots, so a weekly mileage cap is not in the model (`capacity.weekly_mileage_cap` is documented as likely
   non-binding), and `coverage.min_per_tract` is 0 because roughly 11 checks per quarter cannot cover about 96 tracts. Equity is audited after the
   fact (`eval/equity.py`) rather than constrained.
5. **Candidate pool.** Restricting to the top $M=30$ by sampled prize, plus the forced set, is a heuristic and can in principle exclude a
   store the full model would pick. At the actual budget ($B_c=4$) this is not expected to bind.
6. **Rolling, not joint.** Cycles are planned one at a time. A single horizon-wide model would be at least as good in expected prize.
7. **Routing barely matters at the real budget.** With $B_c\approx4$ and one team-day fitting about 15 stops, the MILP and a ranked-and-batched
   heuristic collect the same prize (memo 03, finding 4). The selection model earns its keep only when time or budget is tighter. A census does not use it:
   memo 04 partitions a single tour into day-long routes (route first, split second), a different, labor-driven problem, and memo 06 compares the two regimes.

---

## 8. Reproducing and checking

- Parameters: `config/default.yaml` (`prize`, `coverage`, `harrington`, `risk`, `solve`, `capacity`).
- Model code: `model/orienteering.py` (equations 1-9), `model/prize.py` (3.1, 3.3), `model/harrington.py` (3.4), `model/thompson.py` (4.1),
  `model/risk.py` (3.2), `pipeline.plan_cycle` (4.1 assembly).
- Solver: Gurobi, falling back to HiGHS if the license is size-limited (`pick_solver`). The default `mip_gap` is 0 and the time limit 60 s.
- Command: `uv run tobacco-inspect run-all`.
