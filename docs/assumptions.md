# Assumptions and open items

Everything here is a placeholder to be confirmed or replaced. Numeric values live in
`config/default.yaml`.

## Parameters not yet sourced
| Item | Placeholder | Needed from |
|---|---|---|
| Teams | 2 | DOH contract / subcontractor |
| Hours per inspection day | 8 | DOH contract |
| Weekly mileage cap M | 300 | DOH contract |
| Inspection budget B per horizon | 200 | DOH contract (PA receives funding for about 10,000 inspections/yr statewide) |
| Service time per inspection | 20 min | Measure or ask inspectors |
| Deterrence effect (lambda, Harrington parameters) | 0.25 | Literature (Abouk & Adams 2017; Tangirala et al. 2006), then sensitivity analysis |

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
