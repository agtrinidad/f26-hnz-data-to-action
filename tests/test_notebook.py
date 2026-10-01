"""The implementation notebook must quote the Proposed Alternative verbatim."""

import json
import re
from datetime import date

from tobacco_inspect import pipeline
from tobacco_inspect.config import REPO_ROOT, load_config

NOTEBOOK = REPO_ROOT / "notebooks" / "02_risk_and_schedule.ipynb"
SOURCE = REPO_ROOT / "docs" / "sources" / "proposed_alternative.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_quoted_passages_match_the_proposal_exactly():
    source = _norm(SOURCE.read_text(encoding="utf-8"))
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    quotes = []
    for cell in nb["cells"]:
        if cell["cell_type"] == "markdown" and "proposal-quote" in cell["metadata"].get("tags", []):
            body = "".join(cell["source"])
            quotes.append(_norm(body.split("> ", 1)[1]))
    assert len(quotes) == 4  # the four paragraphs of the Proposed Alternative
    for q in quotes:
        assert q in source
        assert "’" in source or "“" in source  # curly quotes preserved in the source


def test_notebook_has_no_stored_outputs():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")


def test_cycle_workdays_skip_federal_holidays():
    cap = load_config().capacity
    days = pipeline.cycle_workdays(date(2026, 11, 23), 0, cap)
    assert date(2026, 11, 26) not in days  # Thanksgiving
    assert all(d.weekday() < 5 for d in days) and len(days) == cap.cycle_days


NOTEBOOK3 = REPO_ROOT / "notebooks" / "03_census_vs_sampling.ipynb"


def test_census_notebook_context_quote_and_no_outputs():
    nb = json.loads(NOTEBOOK3.read_text(encoding="utf-8"))
    source = _norm(SOURCE.read_text(encoding="utf-8"))
    quotes = [
        _norm("".join(c["source"]).split("> ", 1)[1])
        for c in nb["cells"]
        if c["cell_type"] == "markdown" and "proposal-quote" in c["metadata"].get("tags", [])
    ]
    assert len(quotes) == 1 and quotes[0] in source and "over random sampling" in quotes[0]
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")


NOTEBOOK4 = REPO_ROOT / "notebooks" / "04_regime_comparison.ipynb"


def test_regime_notebook_has_no_stored_outputs_and_states_what_is_new():
    nb = json.loads(NOTEBOOK4.read_text(encoding="utf-8"))
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")
    text = " ".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")
    assert "What is new here, and what is reused" in text
    assert "assumed" in text  # every deterrence number carries the assumed label


def test_regime_pipeline_smoke_on_real_inputs():
    import pytest

    cfg = load_config()
    if not (cfg.path("processed") / pipeline.SCORES_FILE).exists():
        pytest.skip("risk scores not built (run `tobacco-inspect fit`)")
    res = pipeline.regime(cfg, write=False, n_scale=0.05)
    n = res["N"]
    assert len(res["p"]) == n
    assert res["equity"]["share_stores_never_checked"].iloc[1] == pytest.approx(0, abs=1e-9)
    assert set(res["response_grid"]["response"]) == set(pipeline.RESPONSES)
    fr = res["frontier"]
    assert fr[fr.policy == "census_floor"].iloc[0]["checks"] == n
    assert res["cen_cost"] > res["cap_cost"] > 0
