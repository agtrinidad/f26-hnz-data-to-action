> Written for: the project team (Abigail, Anastasia, Avery), to decide what to change before the Oct 5/7 presentation and Oct 9 report. Claude Sonnet 5.5, 2026-10-02. Based on the 10-02 draft, memos 02-06, ADRs 0005-0007 and the assignment PDF; no new analysis was run.

# Are we conceptualizing the problem effectively?

## Verdict

**Mostly yes on rigor, no on framing.** The team has been unusually honest about what the evidence cannot show (selection bias, no deterrence data, Pittsburgh-only lift untestable, model is not the truth). The weakness is conceptual: the project is presented as a *routing* problem (prize-collecting TSP), but our own results say routing is irrelevant at the funded budget. The real decisions are **allocation** (how many checks, and where: Pittsburgh vs. elsewhere, targeted vs. sweep), **randomization** (how predictable to be), and **learning** (what data to generate). The final report should be organized around those, with the optimizer as the tool that matters only when time binds.

A second weakness: **we model costs and detections carefully, and the benefit not at all.** Every headline is "cost per violator found" or "violations found," while the actual goal (fewer sales to minors) is the one outcome we cannot measure, and detections *fall* if deterrence works.

## 1. Data scientist

| Concern | Evidence | What to do |
|---|---|---|
| **The label is a noisy, selected outcome.** One undercover buy is a coin flip, and FDA chose whom to inspect | 48% of retail licenses have any FDA history; violation rate 13.2% in the city sample, 26% in Synar Allegheny | Say "violation propensity" not "violator." Keep the three evidence labels everywhere |
| **The calibration fixes the level, not the ranking** | Prior-shift moves the mean 16.3% to 26.0% | State plainly that the 26% (n = 100, cigarettes, one summer) cannot correct *who* is risky |
| **The model barely beats a one-line rule at the top** | Top-10% lift 1.47 vs 1.49 for prior-violators-first; AUC gain (0.72 vs 0.57) largely from outlet type | Lead with "a simple, explainable rule is almost as good at the top." That strengthens the case for a transparent list |
| **Pittsburgh is not statewide-typical** | City rate 0% FY2013, 1.6% FY2019, 31-44% FY2022-24; statewide 11-29% | The model is trained on PA and applied to a city whose rate swings by period. Period, inspector and purchaser effects likely dominate store risk. Make this a headline limitation, not item 7 of a list |
| **Validation is circular for the policy tests** | Simulation truth = model's own probabilities; hidden heterogeneity unidentified | Keep "simulated" labels; show the sigma sweep, not one baseline |
| **The list is unstable** | Top-11 overlap with the baseline is 6-11 of 11 under plausible weights | Present as a decision aid. With 4 picks a month, noise from Thompson and the random share is comparable to the signal |
| **Double counting** | Prior violations enter $p_i$, severity in $h_i$, and $\omega_{q_i}$ in $\delta_i$ | Either remove one path or show $\lambda = 0$ as a robustness row |
| **Leakage guard is good** | 30-day lag test passes | Keep, and say it |

## 2. Business analyst

1. **The benefit side is missing.** We never convert checks into youth sales prevented or dollars, so the recommendation cannot be justified as value for money. We *can* do a break-even without new data: "a census costs about $27k at the margin; it must deter about X sales per year to equal the targeted plan." Even a clearly labeled, assumption-driven version beats silence.
2. **Wrong comparison set.** Pittsburgh is about 3-4% of statewide checks (1.5% in FY2025-26). A 345-check census is about 13% of Pennsylvania's published checks. The funder's real question is whether those checks are worth more here than in the rest of the state. The report should name this opportunity cost, even if it cannot answer it. It also exposes that "present budget" (44) is whatever DOH chose, not a measured need.
3. **Marginal vs. full cost.** $13k-$66k (bottom-up) vs. $40k-$138k (top-down) is a 10x spread that readers will read as sloppiness. Pick the view that matches the decision: DOH adding work to a running contract faces marginal cost; a new funder faces full cost. State which one you headline and why.
4. **Who pays, who benefits.** Beneficiaries are DOH/FDA and youth; the cost of a census falls on a program whose authority over the city is unverified (ACHD vs. DOH). Make the open question explicit in the recommendation, not in the checkpoints.
5. **Stakeholder resistance.** The draft names retailer resistance; add inspector and subcontractor resistance (discretion, workload, contest of "why us").

## 3. Product manager

- **Who is the user and what do they touch?** The human draft never says. Proposed: DOH program staff and the regional subcontractor receive a *monthly route sheet with a plain-language reason per store* (already produced: `schedule_route_sheets.csv`, `why_us.csv`). Say this in the executive summary: the deliverable is a usable monthly artifact, not a model.
- **One recommendation, staged.** The repo now holds three framings (targeted plan, census, regime). The report should commit to: *adopt the randomized ranked list now; fund a learning pilot; decide the default on measured evidence.* Put stage gates and a stop rule on the pilot (for example, drop the census default if measured deterrence memory is short or visibility is not convex).
- **Scope discipline.** The census and regime analysis is strong but risks swallowing the narrative. For the 10-minute talk (Oct 5/7), 2 slides on the census, not 6.
- **Adoption risks.** Do not publish the schedule; keep the contest process for inspectors; the Gurobi license is size-limited (ADR 0002), so say that HiGHS is the maintainable fallback and the exact optimizer is optional at this volume.
- **Success metrics for a pilot:** coverage (share of stores checked), measured city violation rate and its standard error, second-pass dose-response in time since last check, share of checks in highest-poverty tracts, cost per check actually incurred.

## 4. Operations research specialist

| Concern | Detail | What to do |
|---|---|---|
| **The problem collapses at the real budget** | $B_c \approx 4$, one team-day fits about 15 stops, so (5) is slack and (7) binds. The MILP reduces to top-$B$ selection by prize | Call the model a *budgeted selection problem with an optional routing layer* and report that the budget's shadow price is large and the time's is zero (this can be read from the solver duals or the Gate B sweep). That is a result, not a failure |
| **Objective mismatch** | The MILP maximizes detections x exposure ($\tilde r_i$); memo 06 scores regimes on violation exposure after deterrence; the two can rank policies differently (detections fall when deterrence works) | State one objective: the prize is a *proxy* for compliance value, and say which scorecard is used where |
| **Randomization is emergent, not optimized** | Thompson ($\kappa = 5$) and a 20% random share were tuned by simulation. Nothing guarantees an inspection-probability profile | Next-step formulation: choose inspection probabilities $\pi_i$ with $\sum \pi_i \le B$, $\pi_i \ge \pi_{\min}$, maximizing expected prize minus a predictability penalty, then sample a schedule that meets them. Flag as future work; do not rebuild before Oct 9 |
| **Myopic and rolling** | Cycles are solved one at a time; recency and deterrence are dynamic | Name it honestly as a rolling-horizon heuristic, or as a restless-bandit-like problem; do not call it optimal over the horizon |
| **Formulation mismatch in the draft** | The human draft's single-route MTZ model (constraint 5 plus budget 6) is not what the code solves (K route slots, random-share floor, symmetry breaking) | Use memo 05's formulation. Keep the single-route version only as the special case |
| **Candidate-pool heuristic** | Top 30 by sampled prize plus forced stores | Say it is a speed-up, not part of the model |
| **Census is a different OR problem** | Memo 04 partitions one tour into day-long routes (route first, split second; within 0.05% of optimum on small cases). Labor, not mileage, drives cost | Present the census as a *workforce-and-calendar* problem, not as the same MILP at larger scale |
| **What-if tool** | The assignment encourages OptiGuide for what-if analysis | The Gate B sweep and the cost sensitivity are natural candidates; mention one OptiGuide-style what-if (for example, "what if we add a third team?" or "what if the day is 4 hours?") if time allows |

## Cross-cutting issues to fix before submission

1. **Two inconsistent scopes in the human draft.** Data Summary uses 911 checks / 120 violations (city limits); Empirical Assessment uses 1,808 / 208 / 743 locations (postal "PITTSBURGH") and 1,633 of 1,808 missing dates (vs. 813 of 911). Keep one scope. The Claude draft uses city limits and footnotes the other.
2. **Formulation does not match code.** See OR table. The human draft numbers the objective (1) in the table but not in the text, and its budget constraint is (6) vs. (7) in memo 05.
3. **Empty sections.** Recommendations and Next Steps are headings only; the Analysis trails off mid-sentence ("do not contain the current"). The Claude draft fills them; the team must check each claim.
4. **The draft predates the census/regime work.** The executive summary says nothing about the pilot or the break-evens (1.17, 0.64).
5. **Sourcing flags.** IRS mileage (72.5 vs. 76 cents), BLS wage year, Synar tables (second-person check pending), 2016-25 Synar history read off a chart.
6. **Page limits (assignment PDF).** Executive summary 1 page; analytical model and data under 3 pages (move the constraint table and the data table to the appendix if over); attribution 0.5-1 page.
7. **GenAI policy.** Course requires exact prompts and full responses in the appendix, with the tool version. The LOG shows the Gemini version blank and no transcript files. Fix this; an academic-integrity deviation costs more than any modeling gap.
8. **Terminology.** "Federal Drug Administration" appears in the draft; it is the Food and Drug Administration. Use "violation propensity," not "violator," for stores.
9. **Code package.** The PDF requires self-standing files with a ReadMe and relative paths; run `uv run python scripts/package_submission.py --check` and test from a clean clone. The repo also contains a `.zip` at the top level; confirm what it is before shipping.

## Questions the team should settle (in order of value)

1. **Headline recommendation:** is it "randomized ranked list now, learning pilot next"? (This draft assumes yes.)
2. **Which cost view do we headline:** marginal ($27k) or full ($40k-$138k)?
3. **Can we state a break-even deterrence effect** even if assumption-driven?
4. **How much talk time for the census** vs. the targeted plan?
5. **Who owns the missing facts** (DOH store-selection rule; purchaser mix; ACHD authority; Synar requirement)?
