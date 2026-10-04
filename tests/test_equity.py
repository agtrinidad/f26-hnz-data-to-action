import pandas as pd
import pytest

from tobacco_inspect.eval import equity


def _universe(with_minority=True):
    # tracts A, B are majority-minority (2 stores each); C, D are not (2 stores each)
    uni = pd.DataFrame(
        {
            "license_id": list("abcdefgh"),
            "tract_geoid": list("AABBCCDD"),
            "acs_poverty_rate": [0.3] * 4 + [0.1] * 4,
            "acs_youth_share": [0.2] * 8,
        }
    )
    if with_minority:
        uni["acs_minority_share"] = [0.8] * 4 + [0.2] * 4
    return uni


def test_majority_minority_coverage_ratio():
    uni = _universe()
    # 2 checks per majority-minority store-pair tract, 1 per other tract -> 4 vs 2 inspections
    counts = pd.Series([1, 1, 1, 1, 1, 0, 0, 0], index=uni.index)
    s = equity.equity_summary(equity.coverage_by_tract(uni, counts))
    assert s["tracts_majority_minority"] == 2
    assert s["share_retailers_majority_minority"] == pytest.approx(0.5)
    assert s["share_inspections_majority_minority"] == pytest.approx(4 / 5)
    assert s["inspections_per_retailer_majority_minority"] == pytest.approx(1.0)
    assert s["inspections_per_retailer_other"] == pytest.approx(0.25)
    assert s["majority_minority_coverage_ratio"] == pytest.approx(4.0)
    assert s["corr_coverage_minority"] > 0


def test_equal_coverage_gives_ratio_one():
    uni = _universe()
    s = equity.equity_summary(equity.coverage_by_tract(uni, pd.Series(1.0, index=uni.index)))
    assert s["majority_minority_coverage_ratio"] == pytest.approx(1.0)


def test_summary_without_minority_column_keeps_old_keys():
    uni = _universe(with_minority=False)
    s = equity.equity_summary(equity.coverage_by_tract(uni, pd.Series(1.0, index=uni.index)))
    assert "share_inspections_high_poverty" in s
    assert not any("minority" in k for k in s)
