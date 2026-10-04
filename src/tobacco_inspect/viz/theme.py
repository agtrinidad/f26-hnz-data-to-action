"""Deck-matched matplotlib styling: white page, ink text, one red accent, thin red footer rule."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

import matplotlib as mpl
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from tobacco_inspect.config import Config

TEXT_FIELDS = ("title", "subtitle", "source")
_TEXT_OVERRIDES: ContextVar[dict[str, str] | None] = ContextVar("text_overrides", default=None)


@contextmanager
def text_overrides(overrides: dict[str, str] | None) -> Iterator[None]:
    """Within the block, `titled` replaces default text for any field present in `overrides`."""
    token = _TEXT_OVERRIDES.set({k: v for k, v in (overrides or {}).items() if k in TEXT_FIELDS})
    try:
        yield
    finally:
        _TEXT_OVERRIDES.reset(token)


def palette(config: Config) -> dict[str, str]:
    return dict(config.raw["viz"]["palette"])


def apply_theme(config: Config) -> dict[str, str]:
    """Set rcParams from config.viz and return the palette."""
    v = config.raw["viz"]
    pal = palette(config)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": list(v["font"]),
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "text.color": pal["ink"],
            "axes.labelcolor": pal["muted"],
            "axes.edgecolor": pal["rule"],
            "xtick.color": pal["muted"],
            "ytick.color": pal["muted"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": pal["rule"],
            "grid.linewidth": 0.6,
            "axes.axisbelow": True,
            "axes.prop_cycle": mpl.cycler(
                color=[pal["red"], pal["blue"], pal["muted"], pal["coral"]]
            ),
            "legend.frameon": False,
        }
    )
    return pal


def new_figure(config: Config, **kw: Any) -> Figure:
    return Figure(figsize=tuple(config.raw["viz"]["figsize"]), **kw)


def titled(fig: Figure, config: Config, title: str, subtitle: str = "", source: str = "") -> Figure:
    """Deck-style header (bold title, gray subtitle) and footer (source note over a red rule)."""
    pal = palette(config)
    fig.default_text = {"title": title, "subtitle": subtitle, "source": source}
    over = _TEXT_OVERRIDES.get() or {}
    title, subtitle, source = (over.get(k, v) for k, v in fig.default_text.items())
    fig.text(0.04, 0.955, title, fontsize=17, fontweight="bold", color=pal["ink"], va="top")
    if subtitle:
        fig.text(0.04, 0.895, subtitle, fontsize=10.5, color=pal["muted"], va="top")
    fig.add_artist(
        Line2D([0.04, 0.96], [0.065, 0.065], color=pal["red"], lw=1.2, transform=fig.transFigure)
    )
    if source:
        fig.text(0.04, 0.03, source, fontsize=7.5, color=pal["muted"], va="center")
    fig.tight_layout(rect=(0.02, 0.09, 0.98, 0.84))  # fits tick labels; header/footer sit outside
    return fig
