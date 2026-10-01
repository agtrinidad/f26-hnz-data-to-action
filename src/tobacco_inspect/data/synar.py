"""PA 2025 Annual Synar Report: transcribed tables, validation and outlet classification.

Source: Pennsylvania Department of Health, Health Informatics Office, Statistical Support Team
(2026, May). *2025 annual Synar report* (local copy: data/pdf/synar_report_2025.pdf).

The Synar survey is a probability sample of cigarette retailers (frame: DOR Cigarette License
File; Allegheny is a simple-random stratum), so its rates are a random-sample benchmark that the
FDA inspection records (selected, not random) cannot provide. Caveats: cigarettes only; summer
2025 only; Allegheny n = 100 completed outlets.

The tables below were transcribed by hand from the PDF (page numbers in `PAGES`). A second team
member should check them against the PDF; `validate()` checks the internal totals.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

SOURCE = "PA DOH 2025 Annual Synar Report (published May 2026), data/pdf/synar_report_2025.pdf"
NA = np.nan

# --- Table 1, page 8: region results (weighted rates, standard errors, 95% limits) ----------
REGIONS = pd.DataFrame(
    [
        ("Statewide", "State", 1698, 1261, 189, 15.2, 1.2, 12.8, 17.5),
        ("Northcentral", "NC", 103, 85, 5, 6.3, 3.7, 0.0, 13.5),
        ("Northeast", "NE", 207, 171, 19, 11.1, 2.6, 5.9, 16.3),
        ("Northwest", "NW", 104, 82, 4, 4.6, 2.2, 0.3, 8.8),
        ("Southcentral", "SC", 170, 145, 6, 4.4, 2.3, 0.0, 9.0),
        ("Southeast", "SE", 303, 213, 43, 20.0, 3.9, 12.4, 27.5),
        ("Southwest", "SW", 205, 147, 17, 11.3, 3.2, 4.9, 17.6),
        ("Allegheny", "AL", 130, 100, 26, 26.0, 4.4, 17.3, 34.7),
        ("Delaware", "DE", 110, 83, 20, 24.1, 4.7, 14.8, 33.4),
        ("Erie", "ER", 100, 65, 8, 12.3, 4.1, 4.2, 20.4),
        ("Philadelphia", "PH", 266, 170, 41, 24.1, 3.3, 17.7, 30.6),
    ],
    columns=[
        "region",
        "abbr",
        "selected",
        "completed",
        "violations",
        "rate",
        "se",
        "lower",
        "upper",
    ],
)

# --- Tables 7 and 8, pages 12 and 14: outlet type (rates n/a below 40 visits) ----------------
OUTLETS = pd.DataFrame(
    [
        ("Bar/tavern", "bar_tavern", 6, 1, NA, NA, NA),
        ("Beer distributor", "beer_distributor", 95, 9, 8.3, 2.6, 14.0),
        ("Convenience/gas", "convenience_gas", 426, 60, 13.9, 10.4, 17.4),
        ("Convenience/grocery/no gas", "convenience_independent", 278, 65, 23.7, 18.0, 29.3),
        ("Dollar store", "dollar_store", 153, 4, 2.9, 0.0, 6.2),
        ("Pharmacy/drug store", "pharmacy", 14, 0, NA, NA, NA),
        ("News outlet", "news", 4, 0, NA, NA, NA),
        ("Restaurant/deli", "restaurant_deli", 39, 5, NA, NA, NA),
        ("Supermarket", "supermarket", 65, 4, 6.6, 0.0, 13.3),
        ("Tobacco", "tobacco_shop", 168, 38, 22.3, 15.3, 29.4),
        ("Other", "other", 13, 3, NA, NA, NA),
    ],
    columns=["outlet_type_synar", "outlet_type", "visited", "violations", "rate", "lower", "upper"],
)

# --- Tables 2-6, pages 10-12: purchaser and clerk attributes -------------------------------
ATTRIBUTES = pd.DataFrame(
    [
        ("purchaser_gender", "Male", 410, 53, 14.0, 10.2, 17.8),
        ("purchaser_gender", "Female", 851, 136, 15.7, 12.8, 18.7),
        ("purchaser_age", "15", 60, 0, 0.0, 0.0, 5.0),
        ("purchaser_age", "16", 173, 19, 10.9, 5.4, 16.4),
        ("purchaser_age", "17", 209, 34, 18.0, 10.8, 25.1),
        ("purchaser_age", "18", 271, 46, 18.5, 13.4, 23.5),
        ("purchaser_age", "19", 317, 42, 12.1, 8.0, 16.2),
        ("purchaser_age", "20", 231, 48, 21.5, 15.3, 27.6),
        ("purchaser_race", "White", 896, 116, 13.1, 10.5, 15.7),
        ("purchaser_race", "Black", 320, 65, 20.3, 15.2, 25.5),
        ("purchaser_race", "Other", 45, 8, 17.8, 7.9, 27.6),
        ("purchaser_ethnicity", "Hispanic", 50, 9, 18.6, 8.8, 28.4),
        ("purchaser_ethnicity", "Non-Hispanic", 1211, 180, 15.0, 12.7, 17.4),
        ("clerk_gender", "Male", 680, 119, 17.3, 14.0, 20.6),
        ("clerk_gender", "Female", 581, 70, 12.6, 9.3, 15.9),
    ],
    columns=["attribute", "level", "visited", "violations", "rate", "lower", "upper"],
)

# --- Graph 1, page 6: statewide history. Bounds are READ OFF THE CHART (integers, approximate) --
HISTORY = pd.DataFrame(
    {
        "year": list(range(2016, 2026)),
        "lower": [8, 6, 7, 6, 14, 14, 14, 9, 11, 13],
        "upper": [12, 9, 11, 10, 19, 19, 19, 14, 16, 18],
    }
)
HISTORY["midpoint"] = (HISTORY["lower"] + HISTORY["upper"]) / 2
HISTORY["note"] = (
    "approximate: bounds read from Graph 1 (p. 6); 2025 exact rate is 15.2 (12.8-17.5)"
)

PAGES = {
    "regions": "p. 8 (Table 1)",
    "outlets": "pp. 12, 14 (Tables 7, 8)",
    "attributes": "pp. 10-12 (Tables 2-6)",
    "history": "p. 6 (Graph 1; approximate)",
}


def validate() -> None:
    """Internal-consistency checks on the transcription (raises AssertionError)."""
    states = REGIONS[REGIONS["abbr"] == "State"].iloc[0]
    parts = REGIONS[REGIONS["abbr"] != "State"]
    assert parts["selected"].sum() == states["selected"] == 1698
    assert parts["completed"].sum() == states["completed"] == 1261
    assert parts["violations"].sum() == states["violations"] == 189
    assert OUTLETS["visited"].sum() == 1261 and OUTLETS["violations"].sum() == 189
    for attr, g in ATTRIBUTES.groupby("attribute"):
        if attr in {"purchaser_gender", "purchaser_age", "purchaser_ethnicity", "clerk_gender"}:
            assert g["visited"].sum() == 1261, attr
            assert g["violations"].sum() == 189, attr
    race = ATTRIBUTES[ATTRIBUTES["attribute"] == "purchaser_race"]
    assert race["visited"].sum() == 1261 and race["violations"].sum() == 189


def write_tables(interim_dir: Path) -> None:
    """Write the transcribed tables to data/interim (committed, small)."""
    validate()
    out = Path(interim_dir)
    out.mkdir(parents=True, exist_ok=True)
    regions = REGIONS.assign(source=SOURCE, pages=PAGES["regions"])
    outlets = OUTLETS.assign(source=SOURCE, pages=PAGES["outlets"])
    attrs = ATTRIBUTES.assign(source=SOURCE, pages=PAGES["attributes"])
    regions.to_csv(out / "synar_2025_regions.csv", index=False)
    outlets.to_csv(out / "synar_2025_outlet_types.csv", index=False)
    attrs.to_csv(out / "synar_2025_purchaser_clerk.csv", index=False)
    HISTORY.to_csv(out / "synar_history_2016_2025.csv", index=False)


def allegheny_rate() -> tuple[float, float, float]:
    """Allegheny County retailer violation rate (proportion) with 95% limits."""
    r = REGIONS[REGIONS["abbr"] == "AL"].iloc[0]
    return r["rate"] / 100, r["lower"] / 100, r["upper"] / 100


def outlet_type_rates() -> pd.DataFrame:
    """Weighted violation rate by outlet type (proportions; NaN where Synar reports n/a)."""
    out = OUTLETS.copy()
    for col in ("rate", "lower", "upper"):
        out[col] = out[col] / 100
    return out


def history() -> pd.DataFrame:
    return HISTORY.copy()


# --------------------------------------------------------------------------- classification
# Chain names from the report's outlet definitions (p. 24) plus common Pittsburgh-area brands.
CONVENIENCE_GAS_CHAINS = (
    r"7[- ]?ELEVEN|AM ?PM|A[- ]PLUS|CIRCLE K|COGO|CONVENIENT FOOD MART|CROSSROADS|E[- ]?Z MART|"
    r"GET ?GO|GIT N GO|GO[- ]MART|KWIK FILL|QUICK ?STOP|RUTTER|SHEETZ|STOP[- ]N[- ]GO|STUCKEY|"
    r"TOWN (AND|&) COUNTRY FOOD|TURKEY HILL|UNI[- ]?MART|WAWA|SUNOCO|SPEEDWAY|SHELL|GULF|\bBP\b|"
    r"EXXON|MARATHON|CITGO|LUKOIL|MOBIL|ROYAL FARMS|LOVE'?S|PILOT|\bGAS\b|FUEL|PETRO"
)
SUPERMARKET_CHAINS = (
    r"ACME|FOOD LION|GIANT EAGLE|GIANT FOOD|\bGIANT\b|KARNS|SAVE[- ]A[- ]LOT|SHOP ?'?N'? ?SAVE|"
    r"WEIS|ALDI|WHOLE FOODS|TRADER JOE|SHOPRITE|WALMART|WAL[- ]MART|COSTCO|SAM'?S CLUB|SUPERMARKET"
)
RULES = [
    (
        "tobacco_shop",
        r"\b(SMOKE|SMOKES|VAPE|VAPES|VAPOR|TOBACCO|CIGAR|CIGARS|HOOKAH|CBD|KRATOM|LIQUID)\b",
    ),
    ("dollar_store", r"DOLLAR|FIVE BELOW|BIG LOTS|99 CENT"),
    ("pharmacy", r"\b(CVS|RITE ?AID|WALGREEN|WALGREENS)\b"),
    ("supermarket", SUPERMARKET_CHAINS),
    ("pharmacy", r"\b(PHARMACY|DRUG|DRUGS)\b"),
    ("convenience_gas", CONVENIENCE_GAS_CHAINS),
    ("beer_distributor", r"BEER|DISTRIBUTOR|BEVERAGE|\bBEV\b"),
    ("bar_tavern", r"\b(BAR|TAVERN|PUB|LOUNGE|CLUB|INN|SALOON)\b"),
    (
        "restaurant_deli",
        r"PIZZA|\bDELI\b|RESTAURANT|GRILL|CAFE|DINER|SUBS?\b|BAKERY|DONUT|COFFEE|CHINESE|"
        r"KITCHEN|WINGS|BURGER",
    ),
    ("news", r"\bNEWS\b|NEWSSTAND"),
    (
        "convenience_independent",
        r"MARKET|GROCER|FOOD ?MART|MINI ?MART|CONVENIENCE|CORNER|MART\b|"
        r"STORE|SHOP|EXPRESS|QUICK|FOODS?\b",
    ),
]
OUTLET_TYPES = list(dict.fromkeys(name for name, _ in RULES)) + ["other"]


def classify_outlet(name: str) -> str:
    """Assign one of Synar's outlet types from a trade or retailer name (heuristic).

    Order matters (a Giant Eagle pharmacy is a supermarket; a "smoke shop" is tobacco). Names that
    match no rule fall into `other`, which is Synar's "last resort" category and has no
    reportable rate.
    """
    text = re.sub(r"\s+", " ", str(name).upper())
    for label, pattern in RULES:
        if re.search(pattern, text):
            return label
    return "other"
