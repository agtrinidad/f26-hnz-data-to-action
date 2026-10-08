"""Final-report figure manifest (config/report_figures.yaml): ordered figures with captions.

Each entry points at a registered figure by name, so the Report tab, the CLI and the tests all
reuse the same figure code; the manifest only adds order, caption, alt text and audience.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from tobacco_inspect.config import REPO_ROOT, Config
from tobacco_inspect.viz import registry

MANIFEST_FILE = REPO_ROOT / "config" / "report_figures.yaml"


@dataclass(frozen=True)
class ReportFigure:
    id: str
    figure: str
    caption: str
    alt: str
    report_section: str = ""
    takeaway: str = ""
    audience: tuple[str, ...] = ()
    status: str = "ready"

    @property
    def filename(self) -> str:
        return f"{self.id}_{self.figure}.png"


def load_manifest(path: Path = MANIFEST_FILE) -> list[ReportFigure]:
    rows = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["figures"]
    out = []
    for r in rows:
        if r["figure"] not in registry.FIGURES:
            raise KeyError(f"report figure {r['id']!r}: unknown figure {r['figure']!r}")
        out.append(ReportFigure(**{**r, "audience": tuple(r.get("audience", ()))}))
    ids = [r.id for r in out]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate ids in report figure manifest")
    return out


def captions_markdown(items: list[tuple[ReportFigure, str, str]]) -> str:
    """`items` are (entry, caption, alt) triples, possibly edited in the dashboard."""
    lines = ["# Report figure captions", ""]
    for rf, caption, alt in items:
        lines += [f"## {rf.filename}", "", caption, "", f"*Alt text:* {alt}", ""]
        if rf.report_section:
            lines += [f"*Report section:* {rf.report_section}", ""]
    return "\n".join(lines)


def export_report(
    data: dict[str, Any],
    config: Config,
    out_dir: Path,
    transparent: bool | None = None,
    manifest: list[ReportFigure] | None = None,
) -> list[Path]:
    """Render every available manifest figure to `out_dir`, plus captions.md."""
    manifest = manifest if manifest is not None else load_manifest()
    dpi = int(config.raw["viz"]["dpi"])
    if transparent is None:
        transparent = bool(config.raw["viz"].get("transparent", False))
    written, done = [], []
    for rf in manifest:
        if not registry.available(rf.figure, data):
            continue
        fig = registry.render(rf.figure, data, config)
        written.append(registry.export_png(fig, Path(out_dir) / rf.filename, dpi, transparent))
        done.append((rf, rf.caption, rf.alt))
    md = Path(out_dir) / "captions.md"
    md.write_text(captions_markdown(done), encoding="utf-8")
    return [*written, md]
