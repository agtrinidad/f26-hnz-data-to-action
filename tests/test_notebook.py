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
