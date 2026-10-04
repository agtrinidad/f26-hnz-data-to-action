"""Report figures, chart builder and dashboard. Importing this package registers everything."""

from tobacco_inspect.viz import (  # noqa: F401  (imports populate the registries)
    figures_geo,
    figures_overview,
    figures_policy,
    figures_risk,
)
from tobacco_inspect.viz.presets import register_presets
from tobacco_inspect.viz.registry import FIGURES, export_all, render, render_spec, sections

register_presets()

__all__ = ["FIGURES", "export_all", "render", "render_spec", "sections"]
