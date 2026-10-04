"""Figure registry: each figure is `fn(data, config, **params) -> Figure`, registered by name.

The CLI, dashboard and tests all go through this module, so adding a figure is one decorated
function and nothing else.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pandas as pd
from matplotlib.figure import Figure

from tobacco_inspect.config import Config


@dataclass(frozen=True)
class FigureSpec:
    name: str
    section: str
    title: str
    fn: Callable[..., Figure]
    needs: tuple[str, ...] = ()
    params: dict[str, tuple] = field(default_factory=dict)  # name -> (default, lo, hi, step)
    table: Callable[..., pd.DataFrame] | None = None  # data behind the figure, for CSV download


FIGURES: dict[str, FigureSpec] = {}


def figure(
    name: str,
    section: str,
    title: str,
    needs: tuple[str, ...] = (),
    params: dict[str, tuple] | None = None,
):
    """Register a figure function under `name` in dashboard `section`.

    `params` maps a keyword of the figure function to (default, lo, hi, step); the dashboard
    turns each into a slider.
    """

    def deco(fn: Callable[..., Figure]) -> Callable[..., Figure]:
        if name in FIGURES:
            raise ValueError(f"duplicate figure name {name!r}")
        FIGURES[name] = FigureSpec(name, section, title, fn, tuple(needs), params or {})
        return fn

    return deco


def attach_table(name: str):
    """Register the function `(data, config, **params) -> DataFrame` behind figure `name`."""

    def deco(fn: Callable[..., pd.DataFrame]) -> Callable[..., pd.DataFrame]:
        FIGURES[name] = replace(FIGURES[name], table=fn)
        return fn

    return deco


def sections() -> list[str]:
    return list(dict.fromkeys(spec.section for spec in FIGURES.values()))


def available(name: str, data: dict[str, Any]) -> bool:
    return all(data.get(k) is not None for k in FIGURES[name].needs)


def _params(spec: FigureSpec, overrides: dict[str, Any]) -> dict[str, Any]:
    return {**{k: v[0] for k, v in spec.params.items()}, **overrides}


def render(
    name: str,
    data: dict[str, Any],
    config: Config,
    text: dict[str, str] | None = None,
    **params: Any,
) -> Figure:
    """Render figure `name`. `text` may override title/subtitle/source; the figure's default
    text is always available afterwards as `fig.default_text`."""
    from tobacco_inspect.viz.theme import apply_theme, text_overrides

    spec = FIGURES[name]
    missing = [k for k in spec.needs if data.get(k) is None]
    if missing:
        raise KeyError(f"figure {name!r} needs data {missing}; run the pipeline first")
    apply_theme(config)
    with text_overrides(text):
        return spec.fn(data, config, **_params(spec, params))


def table(name: str, data: dict[str, Any], config: Config, **params: Any) -> pd.DataFrame | None:
    spec = FIGURES[name]
    return spec.table(data, config, **_params(spec, params)) if spec.table else None


def to_png_bytes(fig: Figure, dpi: int) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi)
    return buf.getvalue()


def export_png(fig: Figure, path: Path, dpi: int) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, format="png", dpi=dpi)
    return path


def export_all(
    data: dict[str, Any], config: Config, out_dir: Path, names: list[str] | None = None
) -> list[Path]:
    """Render and save every available (or the named) figure; returns the written paths."""
    dpi = int(config.raw["viz"]["dpi"])
    written = []
    for name in names or list(FIGURES):
        if name not in FIGURES:
            raise KeyError(f"unknown figure {name!r}; known: {sorted(FIGURES)}")
        if not available(name, data):
            continue
        written.append(export_png(render(name, data, config), Path(out_dir) / f"{name}.png", dpi))
    return written
