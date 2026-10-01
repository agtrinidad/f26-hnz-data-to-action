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
