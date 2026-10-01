"""Offline tests for the data acquisition/enrichment code (no network)."""

import json

import numpy as np
import pandas as pd
import pytest

from tobacco_inspect.config import REPO_ROOT
from tobacco_inspect.data import features, geocode, ingest


def test_location_keys_follow_notebook_rule():
    df = pd.DataFrame({"n": [" corner  store "], "a": ["12 Main St., Apt 2"], "z": ["15213-1234"]})
    out = ingest.add_location_keys(df, "n", "a", "z")
    assert out.loc[0, "location_key"] == "12 MAIN ST APT 2|15213"
    assert out.loc[0, "retailer_entity_key"] == "CORNER STORE|12 MAIN ST APT 2|15213"


def test_match_address_standardizes_for_matching_only():
    s = pd.Series(["5901 Fifth Avenue Suite 3", "5901 5th Ave", "100 North Craig Street"])
    m = ingest.match_address(s)
    assert m[0] == m[1] == "5901 5TH AVE"
    assert m[2] == "100 N CRAIG ST"


def test_name_similarity_ignores_corporate_noise():
    assert geocode.name_similarity("Quick Stop Sunoco LLC", "QUICK STOP SUNOCO") > 0.9
    assert geocode.name_similarity("Quick Stop", "Pizza Palace") < 0.55


def test_classify_store():
    assert features.classify_store("Mike's Vape & Smoke Shop") == "smoke_vape_shop"
    assert features.classify_store("GETGO #3456") == "gas_convenience"
    assert features.classify_store("Zzz Holdings") == "other"


def test_proximity_features_distances_and_counts():
    retailers = pd.DataFrame({"lon": [-80.0, -80.0], "lat": [40.44, 40.50]})
    # one site ~111 m north of retailer 0 (0.001 degrees latitude)
    sites = pd.DataFrame({"lon": [-80.0], "lat": [40.441]})
    out = features.proximity_features(retailers, sites, "school", [300, 1000])
    assert 100 < out.loc[0, "school_nearest_m"] < 125
    assert out.loc[0, "school_within_300m"] == 1
    assert out.loc[1, "school_within_1000m"] == 0


def test_proximity_features_handles_missing_coordinates():
    retailers = pd.DataFrame({"lon": [np.nan], "lat": [np.nan]})
    sites = pd.DataFrame({"lon": [-80.0], "lat": [40.44]})
    out = features.proximity_features(retailers, sites, "school", [300])
    assert out["school_nearest_m"].isna().all()


def test_parse_acs_tracts(tmp_path):
    est = {f"B01001{i:03d}": 10 for i in range(1, 50)}
    est["B01001001"] = 400
    err = {k: 5 for k in est}
    blob = {
        "release": {"name": "ACS test 5-year"},
        "data": {
            "14000US42003010301": {
                "B01001": {"estimate": est, "error": err},
                "B17001": {
                    "estimate": {"B17001001": 400, "B17001002": 80},
                    "error": {"B17001001": 20, "B17001002": 15},
                },
            }
        },
    }
    path = tmp_path / "acs.json"
    path.write_text(json.dumps(blob), encoding="utf-8")
    df = features.parse_acs_tracts(path)
    row = df.iloc[0]
    assert row["tract_geoid"] == "42003010301"
    assert row["acs_under18"] == 80  # 8 age bands x 10
    assert row["acs_youth_share"] == pytest.approx(0.2)
    assert row["acs_poverty_rate"] == pytest.approx(0.2)
    assert row["acs_youth_share_moe"] > 0


def test_geocode_cache_roundtrip(tmp_path, monkeypatch):
    calls = []

    def fake_batch(rows):
        calls.append(len(rows))
        return pd.DataFrame(
            {"location_key": rows["location_key"], "match": "Match", "lon": -80.0, "lat": 40.4}
        )

    monkeypatch.setattr(geocode, "_batch_request", fake_batch)
    addr = pd.DataFrame(
        {
            "location_key": ["A|15213", "B|15213"],
            "street": ["A", "B"],
            "city": ["PITTSBURGH"] * 2,
            "state": ["PA"] * 2,
            "zip5": ["15213"] * 2,
        }
    )
    cache = tmp_path / "cache.csv"
    first = geocode.geocode_addresses(addr, cache)
    second = geocode.geocode_addresses(addr, cache)  # fully cached: no further request
    assert calls == [2]
    assert len(first) == len(second) == 2


def test_fda_history_matches_notebook_counts_minus_tn_rows():
    raw = REPO_ROOT / "data" / "raw"
    if (
        not (raw / "pittsburgh_inspections_cleaned.csv").exists()
        and not (raw / "Pittsburgh Inspections.csv").exists()
    ):
        pytest.skip("FDA export not present (git-ignored raw data)")
    fda = geocode.load_fda_history(raw)
    assert len(fda) == 1812  # notebook 01 had 1,816 incl. 4 South Pittsburg, TN rows
    assert fda["location_key"].nunique() == 748
    assert fda["retailer_entity_key"].nunique() == 867


def test_statewide_vs_pittsburgh_table():
    actions = pd.DataFrame({"year": [2023, 2023, 2024]})
    pgh = pd.DataFrame(
        {
            "decision_date_parsed": pd.to_datetime(["2023-03-01", "2023-05-01", "2024-01-01"]),
            "underage_sale_violation": [1, 0, 1],
            "Outcome": ["Warning Letter", "No Violations Observed", "Warning Letter"],
        }
    )
    out = ingest.statewide_vs_pittsburgh(actions, pgh).set_index("year")
    assert out.loc[2023, "pa_tobacco_warning_letters"] == 2
    assert out.loc[2023, "pgh_records"] == 2
    assert out.loc[2023, "pgh_wl_share_of_pa"] == 0.5


def test_oce_fiscal_year_table_and_followup():
    oce = pd.DataFrame(
        {
            "fy": [2023, 2023, 2023, 2024],
            "up_involved": [True, True, True, True],
            "underage_sale_violation": [1, 0, 0, 1],
            "postal_pittsburgh": [True, True, False, False],
            "location_key": ["A|15213", "A|15213", "B|15001", "C|15001"],
            "decision_date_parsed": pd.to_datetime(
                ["2023-01-01", "2023-07-01", "2023-02-01", "2024-02-01"]
            ),
        }
    )
    t = ingest.oce_by_fiscal_year(oce).set_index("fy")
    assert t.loc[2023, "up_checks"] == 3 and t.loc[2023, "violations"] == 1
    assert t.loc[2023, "pgh_up_checks"] == 2
    f = ingest.followup_intervals(oce)
    assert f.loc[f["location_key"] == "A|15213", "days_to_next"].iloc[0] == 181
    assert f.loc[f["location_key"] == "C|15001", "days_to_next"].isna().all()


def test_assign_city_scope_inherits_from_matched_license():
    fda_loc = pd.DataFrame(
        {
            "location_key": ["A", "B", "C", "D"],
            "lon": [-80.0, -80.1, np.nan, np.nan],
            "lat": [40.4, 40.5, np.nan, np.nan],
            "in_city_limits": [True, False, False, False],
        }
    )
    scope_lic = pd.DataFrame({"in_city_limits": [True, False]})
    links = pd.DataFrame(
        {
            "location_key": ["C", "D"],
            "lic_index": [0, 1],
            "match_tier": ["address", "address"],
        }
    )
    out = geocode.assign_city_scope(fda_loc, links, scope_lic).set_index("location_key")
    assert out["city_scope"].to_dict() == {
        "A": "in_city",
        "B": "outside_city",
        "C": "in_city",
        "D": "outside_city",
    }
