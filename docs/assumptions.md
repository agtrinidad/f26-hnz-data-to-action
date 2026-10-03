# Assumptions and open items

Everything here is a placeholder to be confirmed or replaced. Numeric values live in
`config/default.yaml`.

## Parameters and their status (updated 2026-09-30)
Status: SOURCED (public document), PROXIED (derived from public data), ASSUMED (placeholder).
Evidence in [sources/README.md](sources/README.md); derivation in
[process/02_Data_Acquisition_Memo.md](process/02_Data_Acquisition_Memo.md).

| Item | Value | Status | Basis / still needed |
|---|---|---|---|
| Statewide inspections per year | about 10,000 funded; about 2,900 undercover checks published (FY2023-25) | SOURCED / observed | DOH page; OCE national files (memo section 12) |
| Horizon | 13 weeks (quarter) | PROXIED | Decision card; the earlier config said 1 week |
| Inspection budget B per horizon | 11 | PROXIED | City-limits undercover checks FY2022-25 average 44/yr / 4 (OCE files). Earlier placeholders (200, 28, 19) used wider scopes |
| Teams | 2 | ASSUMED | Job posting suggests adult supervisor + youth purchaser per team; confirm with DOH/subcontractor |
| Hours per inspection day | 8 | ASSUMED | Standard workday |
| Weekly mileage cap M | 300 | ASSUMED | Likely non-binding; replace with OSM drive-time limit |
| Service time per inspection | 20 min | ASSUMED | Measure or ask inspectors |
| Cost per inspection | $116 to $400 | PROXIED | $1.16M award / 10,000 funded, or / about 2,900 published checks (about $400) |
| Deterrence effect (lambda, Harrington parameters) | 0.25 | ASSUMED | Literature (Abouk & Adams 2017; Tangirala et al. 2006), then sensitivity. Escalation states can follow the FDA penalty schedule (OIG) |
| Scope | City of Pittsburgh limits | DECIDED 2026-09-30 | Config `data.scope`; only 463 of 884 postal-"Pittsburgh" licenses are inside the city. 44 FDA locations are of unknown scope |

## Modeling assumptions
- Inspections and education visits change retailer behavior; the size of the effect is assumed and
  flagged as such in the write-up.
- The DOH is the client, scoped to Pittsburgh (real-world ownership is state-level; Pittsburgh is a
  test case).
- Predict-then-optimize: decisions do not change the risk model's inputs within a horizon (except
  via the explicit Harrington state), so ML is not embedded in the MILP (ADR 0003).

## Source-document issues to fix
- The project plan's "Reference Papers" section lists the security-games URL twice, once labeled as
  Lee et al. (2018). The intended reference is Lee, Shook-Sa, Bowling & Ribisl (2018), Nicotine &
  Tobacco Research 20(11), doi:10.1093/ntr/ntx149. See [references.md](references.md).
- The roundtable transcript recommends HiGHS/CBC/OR-Tools over Gurobi for city maintainability. The
  team decided Gurobi is primary (course-provided), with HiGHS as fallback (ADR 0002).

## Added with the optimization stage (2026-09-30)
| Item | Value | Status | Basis / note |
|---|---|---|---|
| Planning cycle | monthly (`cycle_weeks: 4`), 3 cycles per quarter, 4 stores per cycle | PROXIED | Proposal says monthly; B per cycle = ceil(11 / 3) |
| Thompson prior strength kappa | 5 | ASSUMED (chosen by simulation) | Moderate randomization; kappa 20 collapsed under assumed exploitation (outputs/simulation_kappa.csv) |
| Reserved random share | 20% (at least 1 of 4 slots) | ASSUMED | From the proposal's randomization; power analysis says a Pittsburgh random arm cannot estimate base rates (memo 03) |
| Population base rate for p_i | Synar Allegheny 26.0% (CI 17.3-34.7) | SOURCED, with caveats | Cigarettes only, summer 2025, n = 100 |
| Deterrence weights by penalty depth | [0.25, 0.6, 0.8, 1.0, 1.0] | ASSUMED | Follows FDA's escalation ladder; the strength is not identified by data |
| Deterrence delta, exploitation rho (simulation only) | 0 to 0.25, 0 to 0.9 | ASSUMED | Sensitivity grid; never headline |
| Depot | downtown Pittsburgh (40.4372, -79.9972) | ASSUMED | Replace with the team's actual base |
| Cost per check | $116 to about $400 | PROXIED | Award / funded volume, or / published volume |
| Per-tract coverage floor | 0 (was 1) | CHANGED | About 94 tracts vs about 11 checks a quarter: arithmetically infeasible; audited instead |
| Decision-date lag guard | 30 days | ASSUMED | Approximates publication delay; inspection dates are missing for about 90% of records |

## Added with the census scenario (2026-09-30)
Parameters live in `config/default.yaml` under `census:` (low / base / high). Memo: [process/04_Census_Inspection_Scenario.md](process/04_Census_Inspection_Scenario.md).
| Item | Low / base / high | Status | Basis |
|---|---|---|---|
| Unit of the census | 345 distinct retail locations (407 with every license type) | DECIDED for analysis | Retail locations are where an under-21 purchaser can buy |
| On-site time per store | 20 min | ASSUMED | Same as `capacity.service_minutes` |
| Paperwork, evidence, entry per check | 10 / 15 / 25 min | ASSUMED | No public figure |
| Retry share (closed store, refused attempt) | 5% / 10% / 20% | ASSUMED | |
| Traffic and parking factor on OSM times | 1.0 / 1.5 / 2.0 | ASSUMED | OSM times are free-flow |
| Supervisor wage | $28 / $35.28 / $45 per hour | PROXIED | BLS OEWS Pittsburgh compliance officers mean $35.28 (reference year to verify) |
| Purchaser wage | $15 / $15 / $20 per hour | SOURCED | Contractor posting for under-21 purchasers |
| Benefits and payroll load | 1.25 / 1.35 / 1.5 | ASSUMED | |
| Mileage rate | $0.725 / $0.76 / $0.76 | SOURCED | IRS 2026 business rate (mid-year revision to verify) |
| Commute miles per route (team base to city) | 10 / 25 / 50 | ASSUMED | Team base unknown |
| Overhead / fixed fee | 15% / 30% / 50% of direct cost | ASSUMED | Cost-plus-fixed-fee contract |
| Data handling per check | $2 / $5 / $10 | ASSUMED | |
| One-time training and commissioning | $0 / $2,000 / $5,000 | ASSUMED | |
| Top-down cost per check | $116 / $400 | PROXIED | DOH award / funded checks; award / published checks |
| Follow-up rate for violators | 58% / 73% / 88% | SOURCED | PA records (58%) and OIG national (88%) |
| Deterrence window (calendar profile only) | 3 months | ASSUMED | No data on how long a check changes behavior |

## Added with the regime comparison (2026-10-01)
Parameters live in `config/default.yaml` under `regime:` and `census:`. Memo: [process/06_Regime_Comparison.md](process/06_Regime_Comparison.md). Every row that models behavior is ASSUMED: no data identify how checks or their visibility change seller behavior.

| Item | Value | Status | Basis |
|---|---|---|---|
| Observed model lift (top 10%) | 1.47 | SOURCED | Gate A pooled replay, PA FY2022-25; interval 1.23 to 1.77 |
| Targeted-line lift discount (memo 04) | 1.5 | SOURCED | Rounded Gate A lift; now read from `census.targeted_lift` |
| Hidden store-level heterogeneity (sigma) | swept 0 / 0.5 / 1.0 / 1.5; baseline 0 | ASSUMED | Not identified; at most 1.74 is consistent with the observed lift. Slope is calibrated so the lift equals 1.47 at each sigma |
| Census-floor first pass | months 1 to 9 | ASSUMED | `regime.floor_months` |
| Second-pass size | 25% of N (86 checks) | ASSUMED | `regime.second_pass_share` |
| Store-specific deterrence (delta, memory) | 25% for 3 months; 50% for 6 months | ASSUMED | Replaces the fixed 3-month window of memo 04 and the cycle-based delta of notebook 02 with one shared model, in months |
| General deterrence (gamma, shape) | gamma 0.3; shape swept 0.25 to 3 | ASSUMED | Share of stores checked in the last 6 months; shape (1 linear, above 1 convex) decides which regime is cost-effective |
| Cost of the running (capped) program | bottom-up from routes, no commissioning | PROXIED | Today's contract is already trained; switch `charge_commissioning_to_capped` |
| Latest annual DOH award | $1,159,731 | SOURCED | Now `census.award_dollars` (context only) |

## Reconciliation note (2026-10-01, updated 2026-10-03)
The 11 quarterly checks round up to four per cycle, so the saved schedule has 12 visits (about 48 a year against the 44-a-year proxy). An exact 4/4/3 split was ported from the reconciled copy and then reverted: every other analysis uses a uniform 4 per cycle, and one convention is more useful than one store.

## Added with the marginal-value analysis (2026-10-03)
| Item | Value | Status | Basis / note |
|---|---|---|---|
| Headline cost basis | marginal: bottom-up increment over today's capped program (44 checks, no commissioning) | CHOSEN | ADR 0008; top-down shown as a sensitivity only |
| Statewide published checks per year | about 2,900 | SOURCED | OCE files; `valuation.pa_published_checks_per_year`. The draft's 13% for the census implies a different count; confirm |
| Value of a prevented sale | none asserted | CHOSEN | Memo 07 reports the price per prevented violation-equivalent instead |
| Violation-equivalent | reduction in exposure x 88 expected violations in one full pass | ASSUMED | Not a count of sales to minors |
| Workdays per month | 21 | ASSUMED | Converts what-if calendars to months |
