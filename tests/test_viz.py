"""Figure registry, PNG export and geographic clustering."""

import matplotlib

matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

from tobacco_inspect import viz
from tobacco_inspect.config import load_config
from tobacco_inspect.eval import geo
from tobacco_inspect.viz import registry
from tobacco_inspect.viz.data import load_viz_data


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def data(cfg):
    d = load_viz_data(cfg)
    if d["risk"] is None:
        pytest.skip("processed data not present")
    return d


def test_every_available_figure_renders_and_exports(cfg, data, tmp_path):
    names = [n for n in viz.FIGURES if registry.available(n, data)]
    assert len(names) >= 12
    written = viz.export_all(data, cfg, tmp_path, names)
    assert len(written) == len(names)
    for path in written:
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert path.stat().st_size > 5_000


def test_every_figure_has_a_table(cfg, data):
    for name in viz.FIGURES:
        if registry.available(name, data):
            tbl = registry.table(name, data, cfg)
            assert isinstance(tbl, pd.DataFrame) and len(tbl) > 0, name


def test_unknown_figure_rejected(cfg, data, tmp_path):
    with pytest.raises(KeyError):
        viz.export_all(data, cfg, tmp_path, ["nope"])


def test_funnel_matches_deck_counts(cfg, data):
    t = registry.table("coverage_funnel", data, cfg).set_index("stage")["n"]
    assert (t.iloc[0], t.iloc[1], t.iloc[2], t.iloc[3]) == (467, 392, 345, 188)


def test_cluster_stores_finds_two_blobs():
    rng = np.random.default_rng(0)
    a = pd.DataFrame(
        {"lon": -79.99 + rng.normal(0, 0.0005, 20), "lat": 40.44 + rng.normal(0, 0.0005, 20)}
    )
    b = pd.DataFrame(
        {"lon": -79.93 + rng.normal(0, 0.0005, 20), "lat": 40.46 + rng.normal(0, 0.0005, 20)}
    )
    df = pd.concat([a, b], ignore_index=True)
    labels = geo.cluster_stores(df, eps_m=300, min_samples=4)
    assert set(labels) == {0, 1}
    assert labels.iloc[:20].nunique() == 1 and labels.iloc[20:].nunique() == 1


def test_hotspot_table_reconciles_with_locations(cfg, data):
    r = data["risk"]
    loc = geo.one_row_per_location(r[r["retail_license"]])
    assert len(loc) == 345
    hot = geo.hotspot_table(loc, eps_m=400, min_samples=4)
    clustered = geo.cluster_stores(loc, 400, 4) >= 0
    assert hot["stores"].sum() == clustered.sum()
    assert hot["prize_sum"].sum() == pytest.approx(loc.loc[clustered, "prize"].sum())
    assert hot["prize_sum"].is_monotonic_decreasing


def test_local_zscores_flag_dense_high_prize_group():
    rng = np.random.default_rng(1)
    df = pd.DataFrame({"lon": -80 + rng.uniform(0, 0.1, 60), "lat": 40.4 + rng.uniform(0, 0.1, 60)})
    df["prize"] = 0.1
    df.loc[:9, ["lon", "lat"]] = [-79.95, 40.45]
    df.loc[:9, "prize"] = 1.0
    z = geo.local_zscores(df, band_m=500)
    assert z.iloc[:10].min() > 2


def test_text_overrides_apply_and_defaults_survive(cfg, data):
    default = viz.render("top_stores", data, cfg)
    assert set(default.default_text) == {"title", "subtitle", "source"}
    custom = viz.render("top_stores", data, cfg, text={"title": "My title", "source": ""})
    assert custom.default_text == default.default_text
    shown = [t.get_text() for t in custom.texts]
    assert "My title" in shown and default.default_text["title"] not in shown
    assert default.default_text["subtitle"] in shown


def test_report_manifest_points_at_registered_figures():
    from tobacco_inspect.viz.report import load_manifest

    manifest = load_manifest()
    assert len(manifest) >= 8
    assert all(m.figure in viz.FIGURES and m.caption and m.alt for m in manifest)


def test_report_export_writes_pngs_and_captions(cfg, data, tmp_path):
    from tobacco_inspect.viz.report import export_report

    written = export_report(data, cfg, tmp_path)
    assert (tmp_path / "captions.md").exists()
    assert any(p.suffix == ".png" for p in written)


def test_simulated_compare_matches_deck(cfg, data):
    if data.get("simulation_policies") is None:
        pytest.skip("simulation output not present")
    t = registry.table("simulated_policies_compare", data, cfg)
    fixed = t[t["label"] == "Fixed top-risk list"].set_index("stores")["found_per_cycle"]
    assert fixed.iloc[0] > 1.5 and fixed.iloc[1] < 0.5
