# Final report and public release plan

Status as of 2026-10-07. This is the working plan for taking the 9/21 draft report to a final
version that matches the 10/5 deck and the repo outputs, and for releasing the repo publicly.
Figure production (section 3) is done in code; the rest is open.

## 1. Who reads it, and what they need

| Audience | Looks for | Where it goes |
|---|---|---|
| Data scientists | Leakage guard (30-day lag), selection bias, AUC 0.72 vs. prior-violators 0.57, top-10% lift 1.47 (95% interval ~1.2-1.8), reproducibility | Analysis; appendix "Reproducing this" |
| Business / program managers | Cost, capacity, what changes Monday; routing does not bind at ~4 checks/month; census option +$24-30K | Executive summary; Recommendations with a cost table |
| Product managers (tool owner after class) | Maintenance, inputs, outputs (CSV route sheets), config-driven runs, February license refresh | New "Implementation and maintenance" subsection |
| State DOH / FDA | Fits the existing contract; screening aid, not a finding; randomization is defensible | Recommendations; limitations |
| Retailers | "Why us?"; fairness; compliant stores not harassed | Equity subsection; `why_us.csv` explanation |
| City council | One number, one picture: 48% of licenses have no history; cost of universal coverage; equity ratios | Executive summary; Figure 1 |
| Civilians / youth-health advocates | Are kids safer? Deterrence is assumed from the literature, not measured here | Limitations, stated plainly |

## 2. Report gaps to fix

1. **Empty sections.** Write "Mitigating Disparate Impact" (Abigail; deck slide 13 and
   `outputs/regime_equity.csv`) and the Conclusion (Anastasia).
2. **Missing analysis.** The body has no simulation or routing results, though the executive summary
   promises them. Add backtest (slide 10), simulation (slide 19), routing sensitivity (optimizer gains
   0-11% only when time is scarce) and census-scale cost (slide 11).
3. **Two tests mixed.** The statewide backtest (49,032 checks, AUC 0.72) is the headline. The
   postal-scope repeat-check test (AUC 0.575, quintile lift 1.55) and the 217-location diagnostic
   (lift 1.85x to 1.52x, the h_i version) are different tests; label by scope or move to the appendix.
4. **Two universes mixed.** Postal scope (1,808 records / 208 violations / 744 locations / 1,633
   undated) vs. city limits (911 / 120 / 379 / 813 undated). Use city limits as the main universe;
   postal numbers go in the appendix. Use 744 locations (current script output; older drafts said 743).
5. **"~44 checks a year."** Define it. City counts by decision year are about 35 / 53 / 65 / 10
   (2022-25); 2025 looks like data lag, not a falling violation rate.
6. **Simulation labels.** Checked against `outputs/simulation_policies.csv`: the deck's slide 19 is
   consistent. "Stores react (rho = 0.9)" is the delta = 0, rho = 0.9 cell (fixed list 0.22, planned
   policy 1.22, random 1.01); "don't react" is delta = 0, rho = 0 (1.78, 1.23, 1.02). Say which cell the
   report uses.
7. **Notation and typos.** Delta_i (deck) vs. delta_i (report); the formula omits the epsilon
   tie-breaker the text mentions; label the objective "(1)"; "Federal Drug Administration" should be
   "Food and Drug Administration".
8. **Synar calibration.** The deck says p_i is calibrated to the Allegheny County Synar benchmark; the
   report never says so. Describe it (see `src/tobacco_inspect/data/synar.py`) or drop it from the deck.
9. **References.** The PA Department of Agriculture entry is mangled and duplicated, and Zotero
   `google-docs/?...` links remain. Rebuild the list. Huang 2024 and Lam 2022 are listed but not cited.
10. **Attribution and AI audit.** Keep the AI audit (course requirement); confirm with the team whether
    the attribution block stays; trim the Gemini transcript to what the course policy requires.
11. **Executive summary** is long; cut to ~250 words (question, finding, recommendation, cost, caveat).
12. **Tone.** Keep the existing hedging in Interpretation; avoid claims the data cannot carry.

## 3. Figures (done in code: dashboard "Report" tab)

The ordered list lives in `config/report_figures.yaml` (id, registered figure, caption, alt text,
audience, takeaway, report section, status). Run `uv run tobacco-inspect dashboard` and open the
**Report** tab to edit title/subtitle/source, caption and alt text per figure, filter by audience,
untick figures to leave out, and download a zip of PNGs plus `captions.md`. Command line:
`uv run tobacco-inspect viz --report [--out DIR] [--transparent]`.

| Fig | Registered figure | Report section | Note |
|---|---|---|---|
| 1 | `map_observed` | Exec summary / data | hero; 166 with history, 179 without |
| 2 | `coverage_funnel` | Data | 467 / 392 / 345 / 188 |
| 3 | `checks_by_year` | Data / limitations | small denominators; decision-date proxy |
| 4 | `backtest_lift` | Analysis | now shows AUC beside each scorer |
| 5 | `simulated_policies_compare` | Analysis | new; no-response vs. rho = 0.9 |
| 6 | `marginal_value` | Recommendations | +$23.8K floor; +$30.1K with second pass |
| 7 | `regime_frontier` | Recommendations | targeting helps below the full sweep |
| 8 | `equity_regimes_race` | Disparate impact | was registered but never rendered |
| 9 | `map_tract_minority` | Disparate impact | minority share only; coverage overlay is future work |

Changes made with the tab: `simulated_policies` now picks the strongest response as the cell where the
fixed list does worst (it previously picked delta = 0.25, rho = 0.5 by sort order). Backtest AUC for
"prior violators first" computes to 0.56 from the CSV; the deck prints 0.57, so reconcile one way.
`docs/deliverable/figures/*.png` are still the Oct 3 renders; re-export after the final data freeze.
Still to build if wanted: a Figure 1 coverage-by-tract overlay; a cost table (as a table, not a chart).

## 4. Path to the final report

1. Freeze numbers: `uv run pytest`, `uv run tobacco-inspect run-all`, diff `outputs/` against the deck;
   record each claim and its source file in a table in this plan (the earlier crosswalk was removed).
2. Restructure Analysis: Data, Risk model and backtest, Simulation, Routing, Census-scale cost, Equity,
   Limitations.
3. Write the missing sections (items 1-2) using the existing role split.
4. Fix references, notation and typos (items 7 and 9).
5. Trace every number to a file in `outputs/` or `data/`; record it in the crosswalk.
6. Team read-through for tone toward retailers and civilians; export PDF/docx into `docs/deliverable/`.

## 5. Repo hygiene before going public

Already clean: no secrets, no absolute paths, no `.obsidian` tracked, notebooks without outputs, CI
portability check.

**Decisions made (2026-10-08)**
- Commit email: rewrite the Gmail address on 19 commits to the Andrew address (history rewrite;
  collaborators must re-clone).
- Andrew emails in `pyproject.toml` and the human draft: keep.
- Dropped: course assignment PDF, `docs/claude-plans/`, `docs/reconciliation-2026-10-01/`, the Claude
  report draft and the marginal-framing insert. Kept: `claude-drafts/10-02-2026-critical-review.md`.
- Store names and store-level CSVs stay in the repo, with an explicit screening-aid notice.

**Data and legal**
- Add data terms and attribution (OSM ODbL share-alike, FDA OCE, PA Dept. of Revenue, Census/ACS/TIGER,
  NCES, Synar report) to `docs/data-sources.md` or a new `DATA_LICENSES.md`.
- Put an explicit "screening aid, not a finding of noncompliance" notice at the top of the README and
  beside `outputs/risk_scores.csv` and `why_us.csv`. Consider publishing aggregates only, with a script
  to regenerate store-level files.
- Document how `raw/pittsburgh_inspections_cleaned.csv` was produced (original export is not in the
  repo) or drop the postal diagnostic from the public pipeline.

**Polish**
- Add `CITATION.cff`; update README findings to final numbers; fix or document the fixed as-of date
  (2026-07-31) in `scripts/diagnostic_postal_scope.py`.
- Existing lint debt: `ruff check` flags `data/features.py:116` (line length) and `ruff format` flags
  `eval/regime.py`; fix before the CI gate is relied on.
- Secret scan of full history (for example gitleaks); fresh-clone test
  (`uv sync --extra dev && uv run pytest`); tag `v1.0-final`; update `CHANGELOG.md`; flip to public.

## 6. Open questions for the team

1. Rewrite git history to change the author email?
2. Publish store-level scores, or aggregates only?
3. Keep the attribution block and full AI transcript in the submitted report?
4. Keep or drop the postal-scope diagnostic (0.575 AUC) from the main body?
