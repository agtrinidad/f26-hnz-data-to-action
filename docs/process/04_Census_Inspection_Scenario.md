# Memo 04: What if we checked every licensed location in a year?

**Project:** Optimizing the Order and Execution of Periodic Tobacco Retail Inspections in Pittsburgh, PA
**Date:** 2026-09-30. **Scope:** City of Pittsburgh limits. **Companions:** [memo 03](03_Implementation_Results.md) (the targeted plan),
[notebook 03](../../notebooks/03_census_vs_sampling.ipynb) and its [executed HTML copy](04_Census_Notebook_Executed.html),
[ADR 0006](../adr/0006-census-as-a-scenario.md), [APA source catalog](../data-sources.md), [assumptions](../assumptions.md).

Written for the project team and for any reader deciding whether this idea deserves money. It can be read without the code. Every number here is reproduced by
`uv run tobacco-inspect census` and by the notebook.

---

## 1. The short answer

**The question.** Instead of choosing a few stores each month, what if DOH checked *every* distinct licensed location in the city once in a year? How would the work be
divided up, what would it cost line by line, and does it "capture" more than absolute random sampling?

**The answer in five lines.**
1. **It is smaller than it sounds.** The universe is **345 distinct retail locations** (407 if vending-only and wholesale locations are included). With a two-person team (supervisor
   plus under-21 purchaser), the work is about **28 team-days** in the base case (24 to 37 across assumptions): roughly six weeks for one team, three weeks for two.
2. **It is cheap in marginal terms and moderate in full-cost terms.** Pricing the actual routes gives about **$27,000** (range $13,000 to $66,000). Using DOH's award per check ($116 to
   about $400) gives **$40,000 to $138,000**. Either way it is about 3.5% to 12% of the latest annual DOH award, and 8 times the city's recent annual volume (about 44 checks a year).
3. **It is not more efficient per check than random sampling, and it is less efficient than targeting.** Each check finds a violation with the store's own probability, so any scheme that
   spreads checks evenly detects the same number of violations per check. A census does catch **about 14% more distinct violators than "absolute" random draws** of the same size
   (88 vs 76), because random draws repeat some stores and miss 37% of them. But a *simple* random sample without repeats of the same size is the census.
4. **What a census uniquely buys is coverage and measurement, not violations per dollar:** every store, including all of the riskiest, is checked; the city's violation rate is learned to
   within about 2.3 points (Synar's Allegheny sample of 100 gives 4.4); and the 180 stores (52%) with no FDA record get their first *unselected* label, which is the fix for the selection bias
   that limits the risk model.
5. **A hybrid is worth testing:** a one-time census (or a stratified half-census) to learn the true base rate and label every store, then back to the targeted, randomized list.

**What cannot be claimed:** that a census reduces underage sales (no data on deterrence), that the dollar figures are DOH's actual costs (most inputs are assumptions), or that the capture
numbers are exact for Pittsburgh (they use the model's probabilities, calibrated to Synar's Allegheny 26% with a 17-35% interval). The exact formulas hold for any probabilities; the levels do not.

---

## 2. Labels and plain-language glossary

Labels as in memo 03: **observed** (real records), **simulated** (a synthetic year where each store sells with the model's probability), **assumed** (a number nobody has measured).
Exact formulas are identities and hold whatever the probabilities are.

| Term | Meaning |
|---|---|
| Census | Checking every distinct licensed location once in the year |
| Coin-flip idea | One undercover purchase is a trial: store *i* sells to the minor with probability *p_i*. A store is not simply "violator" or "compliant" |
| Violations detected | Sales our checks witness |
| Distinct violators caught | Different stores caught at least once (what enforcement acts on) |
| Coverage | Share of stores checked at least once |
| Absolute random draws | Each check picks any store at random, so a store can be picked twice |
| Simple random sample | Random stores without repeats |
| Team-day | One team's working day (8 hours) |
| Marginal vs full cost | Marginal = price of the extra work (bottom-up from the routes). Full = award divided by checks, which also pays for statewide travel, management and contractor margin |
| Standard error | Typical size of the statistical wobble in an estimate (smaller = more precise) |

---

## 3. What was done, step by step

### 3.1 Define the universe
From the city license file: 467 licenses at **407 distinct locations**; 392 retail licenses at **345 distinct retail locations** (stores holding two licenses, such as cigarette plus other
tobacco, count once); 62 locations hold only vending, wholesale, stamping or itinerant licenses. The census analysis uses the 345 retail locations (where an under-21 purchaser can buy);
the 407-location version is costed as a variant. These sit in 94 census tracts. The license list changes daily and licenses expire each February, so "a year" means this snapshot.

### 3.2 Portion the work: where
Each team works an 8-hour day. At each store: 20 minutes on site plus 15 minutes of paperwork (assumed). Drive times between stores come from the OpenStreetMap network
(`routing/distance.py`, cached by store list) multiplied by a traffic factor (1.5, assumed). Stores are cut into day-long routes with a standard "route first, split second" method
(`routing/partition.py`): draw one good loop through all stores (nearest neighbor then 2-opt), then cut it optimally into pieces that each fit in a day. Checks built in: every store appears
exactly once; no route exceeds the day. **Quality check:** on random 9-store subsets the heuristic's tour was on average 0.05% longer than the exact optimum (worst 0.37%), found by exact dynamic programming.

### 3.3 Portion the work: when
Four calendars place the routes on weekdays (federal holidays skipped) with random placement so no neighborhood learns its day:
A summer block (July 6 to August 21, like Synar), B quarters, C months, D risk-staged (riskiest routes first). Risk-staging by *store* (each risk tier routed separately) was also priced.

### 3.4 Price it two ways
- **Bottom-up** (`eval/census.py`): supervisor and purchaser hours (with benefits), mileage, retries for closed stores or refused attempts, data handling, one-time training, and an overhead
  share. Low, base and high settings for every parameter; a one-at-a-time sensitivity shows which inputs matter.
- **Top-down:** the latest DOH award ($1,159,731) divided by checks: $116 (10,000 funded checks) or about $400 (about 2,900 published checks).
- **Sourced inputs:** IRS 2026 mileage rate (72.5 cents Jan-Jun; a 76-cent July revision appeared in search results, to verify); a contractor posting offering under-21 purchasers $15 an hour; BLS mean $35.28 an hour for Pittsburgh
  compliance officers as the supervisor proxy (reference year to verify). See the [APA catalog](../data-sources.md). Everything else is assumed and listed in section 7.

### 3.5 Measure capture
Exact expected values for each policy (`capture_*` functions), checked by Monte Carlo (300 to 3,000 runs depending on the check): census, simple random sample, absolute random draws, stratified random by tract,
and targeted top-n. Also: standard error of the city rate; the random budget needed to match the census; follow-up and two-pass layers; capture per dollar.

### 3.6 Tests and outputs
65 automated tests pass, including: routes cover every store once and respect the day; 2-opt never lengthens a route; the heuristic matches brute force on a tiny case; cost scenarios are
ordered and overhead adds correctly; census equals a simple random sample at full budget; closed-form capture equals simulation within Monte Carlo error; calendars respect their windows. Files: `outputs/census_*.csv`
(routes, cost summary and components, capture table, calendars), the notebook and this memo.

---

## 4. Results

### 4.1 How the work portions out (simulated routes, assumed times)
| Case | Team-days | Team-hours | Driving hours |
|---|---|---|---|
| Low (fast paperwork, light traffic) | 24 | 191 | 8 |
| **Base** | **28** | **238** | **13.5** |
| High (slow paperwork, heavy traffic) | 37 | 338 | 21.7 |

In the base case routes hold 12 to 13 stores (mean 12.3); the longest uses 478 of 480 minutes. Team time is 54% on site, 40% paperwork and only 6% driving, because the stores are close together:
**this is a labor problem, not a mileage problem.** The on-site and paperwork time alone force at least 26 team-days.

| Calendar | Window | Working weeks | Busiest month (routes) |
|---|---|---|---|
| A summer block | Jul 6 to Aug 20 | 8 | 18 (2 teams) |
| B quarters | Jan to Dec | 51 | 4 |
| C months | Jan to Dec | 50 | 3 |
| D risk-staged | Jan to Dec | 50 | 5 |

Teams needed for one block of 28 team-days: 1 team about 6 weeks; 2 teams 3; 4 teams 2; 8 teams 1. **Risk-staging by store** costs 4 extra team-days (32 vs 28) and 387 extra minutes (about 3%).

**Does the calendar matter?** Only if a check changes behavior for a while. Under an *assumed* three-month window the total protection over a repeating year is identical for every calendar. The profile differs: a summer
block leaves winter and spring without recently-checked stores; spreading routes keeps a steady presence. If checks have no lasting effect, the calendar is irrelevant.

### 4.2 Expense breakdown (one census of 345 locations)
| Line | Low | Base | High |
|---|---|---|---|
| Labor (supervisor + purchaser, with benefits) | $10,240 | $16,139 | $32,954 |
| Mileage | $324 | $806 | $1,866 |
| Data handling and QA | $724 | $1,898 | $4,140 |
| Training and commissioning (one time) | $0 | $2,000 | $5,000 |
| Overhead / fixed fee | $1,693 | $6,253 | $21,980 |
| **Total** | **$12,982** | **$27,096** | **$65,940** |
| Per check | $38 | $78 | $191 |

**Top-down:** $40,020 (at $116 a check) to $138,000 (at $400). The bottom-up price is lower because it covers only the extra work in a dense city; the award per check also pays for statewide
travel, management, reporting and contractor margin. Read bottom-up as the marginal cost of adding the work to an existing program and top-down as the full-cost price of a new one.

**What moves the base total most** (one input at a time): paperwork minutes (10 to 25 changes the total from $24,085 to $33,111), overhead share ($23,970 to $31,265), supervisor wage ($24,058 to $31,152), one-time training ($24,496 to
$30,996). Mileage rate and traffic factor barely matter (under $1,100).

**Follow-up layer.** FDA practice re-checks violators. A census is expected to find about 88; following up 58% to 88% of them adds **51 to 77 checks** (base 64) and catches 15 to 24 repeat violations, which is what triggers
FDA's escalating penalties. Extra cost: about $4,000 to $6,100 (bottom-up) or $5,900 to $31,000 depending on the per-check price.

**Scale.** 345 checks is 7.9 times the city's recent volume (about 44 a year) and 13% of Pennsylvania's recent published undercover checks (about 2,635 a year). Today's volume at the same prices would cost $5,000 to $17,400 a year.
As a share of the $1,159,731 award: 2.3% (bottom-up base) or 3.5% to 11.9% (top-down).
**Variant, every license type (407 locations):** 28 / 33 / 44 team-days and $15,294 / $31,465 / $76,236 (low / base / high).

### 4.3 Capture compared with random sampling
Exact expectations and a Monte Carlo that agrees (simulated truth).

| Policy (budget) | Violations detected | Distinct violators caught | Stores covered | Riskiest 10% covered |
|---|---|---|---|---|
| Census (345 checks) | 88.0 | 88.0 | 100% | 100% |
| Simple random, same 345 | 88.0 | 88.0 | 100% | 100% |
| Absolute random, 345 draws | 88.0 | 76.0 | 63% | 63% |
| Simple random, 86 checks | 21.9 | 21.9 | 25% | 25% |
| Absolute random, 86 draws | 21.9 | 21.1 | 22% | 22% |
| Targeted, 86 checks (model's own p, optimistic) | 34.7 | 34.7 | 25% | 100% |
| Targeted, 86 checks (observed replay lift 1.5x) | 32.9 | 32.9 | 25% | 100% |

**Reading it.**
- **Per check, a census and a random sample are equal.** Both detect about 0.255 violations per check. The only gap against absolute random draws is *repeat-and-miss*: 345 random draws touch 63% of stores, so
  they catch 14% fewer distinct violators. To match one census, random draws need about 1.19 times as many checks (411); to *cover* 90%, 95% or 99% of stores they need 2.3, 3.0 or 4.6 times as many.
- **Targeting is more efficient per check** (about 2.6 checks per violator vs 3.9 for random or census), if the model's ranking holds; the observed replay lift is about 1.5 (memo 03).
- **Coverage is where a census differs:** a quarter-sized random sample covers only 25% of the riskiest 10% of stores. A targeted list covers them all with a tenth of the checks, a census with all 345.

### 4.4 Precision and the value of unbiased labels
Standard error of the observed city violation rate: **census 2.3 points; 345 random checks 2.3; Synar-sized sample (n = 100) 4.4.** Interval half-width: census +/-4.4 points, n = 100 +/-8.5. For comparison, memo 03 showed that a
20% random arm at the city's current volume would need 8.5 years to estimate the rate and 23 years to detect a targeting lift; a census delivers the rate in one year.
Today **180 of 345 retail locations (52%) have no FDA record.** A census labels every one of them with no selection, once. That is the cleanest available training sample for the risk model (it removes the inspected-stores-only bias), though how much the model
would improve was not tested here.

### 4.5 Capture per dollar
| Policy | Checks | Distinct violators | Checks per violator | $ per violator (bottom-up base) | at $116 | at $400 |
|---|---|---|---|---|---|---|
| Census | 345 | 88.0 | 3.9 | $308 | $455 | $1,569 |
| Targeted, observed lift 1.5x | 86 | 32.9 | 2.6 | $205 | $303 | $1,046 |
| Targeted, model's own p | 86 | 34.7 | 2.5 | $195 | $288 | $992 |
| Simple random, 86 checks | 86 | 21.9 | 3.9 | $308 | $455 | $1,569 |
| Absolute random, 345 draws | 345 | 76.0 | 4.5 | $356 | $527 | $1,816 |

Going from a targeted quarter-sized program to a full census adds 259 checks to catch 55 more distinct violators: **4.7 extra checks per extra violator**, about **$369 (bottom-up) to $1,881 ($400 a check)** each.
Checking every store *twice* adds 61 distinct violators for 345 extra checks (about 6 checks each). Following up violators once is cheaper: 64 checks for about 20 repeat violations.

---

## 5. What this does and does not tell us

| Question | Answer | Label |
|---|---|---|
| Can it be done? | About 28 team-days (24 to 37) | simulated routes, assumed times |
| What would it cost? | $13,000 to $66,000 marginal (base $27,000); $40,000 to $138,000 fully loaded | assumed / proxied |
| More effective per check than random? | No (equal). Better than repeat-allowed random draws by about 14% in distinct violators | exact |
| More effective than targeting? | No: targeting is about 1.5 times better per check | simulated / observed lift |
| What does it uniquely buy? | Full and equal coverage; a city rate to +/-4.4 points; first unselected labels for 52% of stores | exact / observed |
| Does it deter more? | Unknown. A deterrence effect is assumed in the calendar discussion only | assumed |
| When is it worth it? | When coverage, measurement and legitimacy matter more than violations per dollar | judgment |

**Hybrid worth testing:** one census (or a stratified half-census) to learn the true base rate and label all stores, then return to the targeted randomized plan using the unbiased labels.

## 6. Corrections, surprises and judgment calls

1. **"Capture" had to be defined.** The first intuition was that a census must capture more than random. It does not per check; the benefit is coverage and measurement. The memo reports four definitions so the reader can see where each policy wins.
2. **Two universes.** 345 retail locations vs 407 with every license type vs 392 retail licenses; stores with two licenses count once.
3. **Bottom-up came out below top-down.** Expected on reflection (marginal vs full cost) but worth saying plainly: the cost range is wide because the two views answer different questions.
4. **Driving is only 6% of the day.** Pittsburgh's stores are close together and OSM times are free-flow; the traffic factor (1.5) is assumed. The conclusion that labor dominates holds across the sensitivity range (drive factor 1 to 2 changes the total by about $1,000).
5. **A test caught my mistake in a test:** the risk-staged calendar test used the wrong route for "riskiest"; fixed before use.
6. **A cache fix:** the travel-time matrix cache now keys on the store list, so scenarios with different store sets do not overwrite one another.
7. **Numbers that moved:** "about 8 times the annual volume" is 7.9; stores without an FDA record is 180 (52%), counted after merging two-license stores.
8. **Not modeled:** purchaser availability and legal limits (school calendars, hours), recognition of repeat purchasers by clerks, store opening hours beyond a retry allowance, license turnover during the year.

## 7. Assumptions register

Full table with status tags in [assumptions.md](../assumptions.md) (section "Added with the census scenario"). The inputs that matter most for cost are paperwork time per check, the overhead share, the supervisor wage, and one-time training.
Sourced: purchaser wage, IRS mileage, follow-up rate. Proxied: supervisor wage, top-down cost per check. Everything else is assumed. For capture: store probabilities (the model's, calibrated to Synar Allegheny 26%, interval 17-35%).

## 8. Human checkpoints

1. Agree the unit (345 retail locations; 407 with every license type).
2. Replace assumed cost inputs with DOH or contractor figures (paperwork time, overhead, supervisor pay, training).
3. Confirm whether the FDA contract lets DOH run a city census or whether separate funding is needed.
4. Confirm purchaser supply and scheduling limits.
5. Decide whether coverage, a precise base rate and unbiased labels are worth the added cost; this memo prices them (about 4.7 extra checks per extra violator over a targeted program).
6. Verify the wage and mileage sources flagged in the APA catalog.
7. Confirm each figure's label before reuse.
8. Added 2026-10-01 (see [memo 06](06_Regime_Comparison.md)): whether census data can serve Synar's random-sample requirement; whether Allegheny County Health Department rather than the state owns enforcement in the city; whether certainty of a check changes seller behavior (no data).

## 9. Reproduce and inspect

```
uv run tobacco-inspect census                       # writes outputs/census_*.csv (about 1 minute)
uv run python scripts/build_notebook_03.py          # regenerates notebooks/03_census_vs_sampling.ipynb
uv run pytest                                       # 88 tests (includes the regime tests)
```
Key files: `src/tobacco_inspect/routing/partition.py` (routes, exact check), `src/tobacco_inspect/eval/census.py` (costs, calendars, capture), `pipeline.census`, `config/default.yaml` (`census:` section with low/base/high),
`outputs/census_routes.csv`, `census_cost_summary.csv`, `census_cost_components.csv`, `census_capture.csv`, `census_calendars.csv`.
