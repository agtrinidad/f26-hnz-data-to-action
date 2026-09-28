# Contributing

Three-person team; keep it light but consistent.

## Workflow
1. Open or pick an issue (Task template). Note the owner and due date.
2. Branch from `main`: `feat/<topic>`, `fix/<topic>`, `docs/<topic>`. Keep branches short-lived.
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/): `feat: add tract assignment`,
   `fix:`, `docs:`, `test:`, `chore:`.
4. Open a PR using the template. One teammate reviews. Squash-merge into `main`.
5. Never commit directly to `main` once branch protection is on.

### Recommended GitHub settings (repo owner, one-time)
Settings, then Branches, then add a rule for `main`: require a pull request with 1 approval, require the
`CI / test` checks to pass, and disallow force pushes. Under General, allow squash merging only and
delete branches on merge. Add teammates as collaborators.

## Local checks
```bash
uv sync --extra dev
uv run ruff format . && uv run ruff check .
uv run pytest
uv run python scripts/package_submission.py --check
uv run pre-commit install        # optional: runs ruff/nbstripout on commit
```

## Rules of the road
- **Configuration, not code edits:** parameters live in `config/default.yaml`. Assumptions go in
  `docs/assumptions.md`.
- **Relative paths only.** The submission zip must run on another computer; the packager fails on
  absolute paths.
- **Data:** `data/raw/` is git-ignored. Commit only small files needed to run (`data/interim`,
  `data/processed`; total under about 25 MB). Record source, retrieval date and license in `data/README.md`.
- **Secrets/licenses:** never commit `.env` or `gurobi.lic`.
- **Notebooks:** strip outputs (`nbstripout`), number them (`01_eda.ipynb`), and move reusable logic into `src/`.
- **Randomness:** seed from `config.seed`; results must be reproducible.
- **GenAI (course academic-integrity policy):** log the exact prompt, the full response and the tool
  and version in `docs/llm-transcripts/` (see `LOG.md`). Verify outputs before use; you are responsible for
  their accuracy.
- **Attribution:** update `docs/attribution.md` as you go. It feeds the report's attribution page.
