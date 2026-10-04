"""Register the gallery presets in config/viz_presets.yaml as ordinary registered figures."""

from __future__ import annotations

from pathlib import Path

import yaml

from tobacco_inspect.config import REPO_ROOT
from tobacco_inspect.viz import datasets
from tobacco_inspect.viz.build import build, prepare
from tobacco_inspect.viz.registry import FIGURES, FigureSpec
from tobacco_inspect.viz.spec import ChartSpec

PRESET_FILE = REPO_ROOT / "config" / "viz_presets.yaml"


def register_presets(path: Path = PRESET_FILE) -> list[str]:
    if not Path(path).exists():
        return []
    presets = yaml.safe_load(Path(path).read_text(encoding="utf-8")).get("presets", {})
    for name, p in presets.items():
        if name in FIGURES:
            raise ValueError(f"preset {name!r} collides with a registered figure")
        spec = ChartSpec.from_json(p["spec"])
        needs = datasets.DATASETS[spec.dataset].needs
        if spec.opt("map_mode") == "choropleth":
            needs += ("tracts",)
        FIGURES[name] = FigureSpec(
            name,
            p["section"],
            p["title"],
            lambda data, config, _s=spec: build(_s, data, config),
            needs,
            {},
            lambda data, config, _s=spec: prepare(_s, data, config),
        )
    return list(presets)
