"""Report figures and dashboard. Importing this package registers every figure."""

from tobacco_inspect.viz import (  # noqa: F401  (imports populate the registry)
    figures_geo,
    figures_overview,
    figures_policy,
    figures_risk,
)
from tobacco_inspect.viz.registry import FIGURES, export_all, render, sections

__all__ = ["FIGURES", "export_all", "render", "sections"]
