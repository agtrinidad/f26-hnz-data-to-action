"""Chart-builder: specs, validation, aggregation numbers, every chart kind, CLI parity."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from tobacco_inspect import viz
from tobacco_inspect.config import load_config
from tobacco_inspect.viz import datasets, registry
from tobacco_inspect.viz.build import prepare, validate
from tobacco_inspect.viz.charts import KINDS
from tobacco_inspect.viz.data import load_viz_data
from tobacco_inspect.viz.spec import ChartSpec, SpecError

S = ChartSpec


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def data(cfg):
    d = load_viz_data(cfg)
    if d["risk"] is None:
        pytest.skip("processed data not present")
    return d


EXAMPLES = {
    "bar": S("stores", "bar", x="outlet_type", y="prize", agg="mean", sort="desc"),
    "bar_stacked": S(
        "stores",
        "bar",
        x="outlet_type",
        color="fda_history",
        agg="count",
        options={"stacked": True, "horizontal": False},
    ),  # fmt: skip
    "bar_facet": S("stores", "bar", x="outlet_type", agg="share", facet="fda_history", top_n=6),
    "line": S("fda_checks", "line", x="year", y="violation", agg="mean"),
    "scatter": S(
        "stores",
        "scatter",
        x="acs_poverty_rate",
        y="prize",
        color="acs_youth_share",
        size="p",
        options={"trend": True},
    ),  # fmt: skip
    "scatter_facet": S("stores", "scatter", x="h", y="p", facet="fda_history"),
    "hist": S("licenses", "hist", x="prize", color="fda_history"),
    "box": S("stores", "box", x="outlet_type", y="prize", sort="desc", top_n=8),
    "heatmap": S("simulation", "heatmap", x="delta", y="policy", color="found_per_cycle"),
    "concentration": S("stores", "concentration", x="prize"),
    "map_points": S("stores", "map", color="prize", options={"clusters": True, "schools": True}),
    "map_density": S("stores", "map", options={"map_mode": "density"}),
    "kpi": S("stores", "kpi", options={"kpis": [{"label": "Stores", "agg": "count"}]}),
    "table": S("stores", "table", y="prize", top_n=5, options={"columns": ["trade_name", "prize"]}),
}


@pytest.mark.parametrize("name", EXAMPLES)
def test_every_kind_renders_a_png(name, cfg, data, tmp_path):
    fig = registry.render_spec(EXAMPLES[name], data, cfg)
    path = registry.export_png(fig, tmp_path / "x.png", 60)
    assert path.read_bytes()[:4] == b"\x89PNG"
    assert set(fig.default_text) == {"title", "subtitle", "source"}


def test_every_kind_is_covered():
    assert {e.kind for e in EXAMPLES.values()} == set(KINDS)


def test_choropleth_needs_tracts_or_says_so(cfg, data):
    spec = S("stores", "map", color="prize", agg="sum", options={"map_mode": "choropleth"})
    if data["tracts"] is None:
        with pytest.raises(SpecError, match="Tract boundaries"):
            registry.render_spec(spec, data, cfg)
    else:
        registry.render_spec(spec, data, cfg)


def test_catalog_grain_matches_deck_counts(cfg, data):
    assert len(datasets.load("stores", data, cfg)) == 345
    assert len(datasets.load("licenses", data, cfg)) == 467


def test_bar_aggregation_matches_pandas(cfg, data):
    stores = datasets.load("stores", data, cfg)
    got = prepare(S("stores", "bar", x="outlet_type", y="prize", agg="mean"), data, cfg)
    want = stores.groupby("outlet_type")["prize"].mean()
    assert got.set_index("outlet_type")["value"].to_dict() == pytest.approx(want.to_dict())
    share = prepare(S("stores", "bar", x="outlet_type", agg="share"), data, cfg)
    assert share["value"].sum() == pytest.approx(1.0)


def test_filters_and_top_n(cfg, data):
    spec = S(
        "stores", "bar", x="outlet_type", agg="count", top_n=3,
        filters=[{"col": "fda_history", "values": ["FDA history"]}],
    )  # fmt: skip
    got = prepare(spec, data, cfg)
    assert len(got) == 3 and got["value"].sum() <= 188


def test_concentration_toy():
    from tobacco_inspect.viz.charts import _compute_curve

    df = pd.DataFrame(
        {"score": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1], "v": [50, 10, 10, 10, 5, 5, 5, 3, 1, 1]}
    )
    curve = _compute_curve(df, S("stores", "concentration", x="score", y="v"), None)
    assert np.interp(0.1, curve["share_of_rows"], curve["cum_share_ranked"]) == pytest.approx(0.5)
    assert curve["cum_share_best"].iloc[-1] == pytest.approx(1.0)
    assert (curve["cum_share_best"] >= curve["cum_share_ranked"] - 1e-12).all()


def test_heatmap_cells_match_pivot(cfg, data):
    sim = datasets.load("simulation", data, cfg)
    got = prepare(EXAMPLES["heatmap"], data, cfg).pivot_table(
        index="policy", columns="delta", values="value"
    )
    want = sim.pivot_table(
        index="policy", columns="delta", values="found_per_cycle", aggfunc="mean"
    )
    pd.testing.assert_frame_equal(got, want, check_names=False)


def test_kpi_values(cfg, data):
    spec = S(
        "stores", "kpi",
        options={"kpis": [
            {"label": "n", "agg": "count"},
            {"label": "observed", "column": "fda_observed", "agg": "mean", "fmt": "percent"},
        ]},
    )  # fmt: skip
    got = prepare(spec, data, cfg)
    assert got["value"].iloc[0] == 345
    assert got["display"].iloc[1].endswith("%")


def test_validation_messages(cfg, data):
    df = datasets.load("stores", data, cfg)
    assert validate(S("stores", "bar", x="outlet_type"), df) == []
    bad = validate(S("stores", "scatter", x="outlet_type", y="nope"), df)
    assert any("must be numeric" in m for m in bad)
    assert any("not in this dataset" in m for m in bad)
    assert any("needs" in m for m in validate(S("stores", "bar"), df))
    assert any("not used" in m for m in validate(S("stores", "hist", x="prize", y="p"), df))
    facet_bad = validate(S("stores", "bar", x="fda_history", facet="outlet_type"), df)
    assert any("Facet" in m for m in facet_bad)
    empty = S("stores", "bar", x="outlet_type", filters=[{"col": "prize", "min": 5, "max": 6}])
    with pytest.raises(SpecError):
        prepare(empty, data, cfg)


def test_spec_json_round_trip_and_unknown_keys():
    spec = EXAMPLES["scatter"]
    assert ChartSpec.from_json(spec.to_json()) == spec
    with pytest.raises(SpecError):
        ChartSpec.from_json({"dataset": "stores", "kind": "bar", "bogus": 1})


def test_role_inference(cfg, data):
    roles = datasets.infer_roles(datasets.load("stores", data, cfg))
    assert roles["tract_geoid"] == "id" and roles["outlet_type"] == "category"
    assert roles["prize"] == "numeric" and roles["lon"] == "geo"


def test_text_override_beats_spec_text(cfg, data):
    spec = S("stores", "hist", x="prize", text={"title": "from spec"})
    assert "from spec" in [t.get_text() for t in registry.render_spec(spec, data, cfg).texts]
    fig = registry.render_spec(spec, data, cfg, text={"title": "from user"})
    assert "from user" in [t.get_text() for t in fig.texts]


def test_presets_registered_in_gallery(cfg, data):
    for name in ("prize_distribution", "risk_concentration", "map_density"):
        assert name in viz.FIGURES
        assert len(registry.table(name, data, cfg)) > 0


def test_cli_renders_saved_spec(tmp_path):
    from tobacco_inspect.cli import main

    spec_file = tmp_path / "my_chart.json"
    spec_file.write_text(EXAMPLES["bar"].to_json(), encoding="utf-8")
    assert main(["viz", "--spec", str(spec_file), "--out", str(tmp_path)]) == 0
    assert (tmp_path / "my_chart.png").stat().st_size > 5_000
    assert json.loads(spec_file.read_text())["kind"] == "bar"


def test_builder_page_runs_for_every_kind():
    from streamlit.testing.v1 import AppTest

    app = Path(viz.__file__).parent / "app.py"
    at = AppTest.from_file(str(app), default_timeout=180).run()
    at.sidebar.radio[0].set_value("Builder").run()
    assert not at.exception
    for kind in KINDS:
        at.selectbox(key="b-kind").set_value(kind).run()
        assert not at.exception, kind


def test_map_zoom_crops_view_around_center(cfg, data):
    base = S("stores", "map", color="prize")
    full = registry.render_spec(base, data, cfg).axes[0]
    xs = full.get_xlim()
    stores = datasets.load("stores", data, cfg)
    cx, cy = float(stores["lon"].median()), float(stores["lat"].median())
    zoomed = S(
        "stores", "map", color="prize",
        options={"zoom": 4, "center_lon": cx, "center_lat": cy},
    )  # fmt: skip
    ax = registry.render_spec(zoomed, data, cfg).axes[0]
    assert np.isclose(ax.get_xlim()[1] - ax.get_xlim()[0], (xs[1] - xs[0]) / 4)
    assert np.isclose(np.mean(ax.get_xlim()), cx) and np.isclose(np.mean(ax.get_ylim()), cy)
    default_center = registry.render_spec(S("stores", "map", options={"zoom": 2}), data, cfg).axes[
        0
    ]
    assert np.isclose(np.mean(default_center.get_xlim()), np.mean(xs), atol=1e-3)


def test_transparent_png_has_alpha(cfg, data, tmp_path):
    from PIL import Image

    fig = registry.render_spec(EXAMPLES["bar"], data, cfg)
    solid = registry.export_png(fig, tmp_path / "solid.png", 60)
    clear = registry.export_png(fig, tmp_path / "clear.png", 60, transparent=True)
    assert Image.open(solid).convert("RGBA").getpixel((2, 2))[3] == 255
    assert Image.open(clear).convert("RGBA").getpixel((2, 2))[3] == 0
    assert registry.to_png_bytes(fig, 60, True)[:4] == b"\x89PNG"


def test_cli_transparent_flag(tmp_path):
    from PIL import Image

    from tobacco_inspect.cli import main

    assert main(["viz", "--names", "coverage_funnel", "--out", str(tmp_path), "--transparent"]) == 0
    assert Image.open(tmp_path / "coverage_funnel.png").convert("RGBA").getpixel((2, 2))[3] == 0
