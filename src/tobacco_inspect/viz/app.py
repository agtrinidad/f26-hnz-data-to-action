"""Streamlit dashboard shell. Run `tobacco-inspect dashboard`.

Pages live in viz/ui/: Gallery (curated figures and presets) and Builder (build your own).
"""

from __future__ import annotations

import matplotlib
import streamlit as st

matplotlib.use("Agg")

from tobacco_inspect import viz  # noqa: E402,F401  (populates the registries)
from tobacco_inspect.viz.ui import builder, gallery  # noqa: E402
from tobacco_inspect.viz.ui.common import config_path, get_config, get_data  # noqa: E402

PAGES = {"Gallery": gallery.page, "Builder": builder.page}


def main() -> None:
    st.set_page_config(page_title="Tobacco inspection figures", layout="wide")
    cfg, data = get_config(config_path()), get_data(config_path())
    st.sidebar.title("Report figures")
    page = st.sidebar.radio("Mode", list(PAGES), horizontal=True)
    dpi = st.sidebar.select_slider(
        "PNG resolution (dpi)", [150, 200, 300, 450, 600], int(cfg.raw["viz"]["dpi"])
    )
    st.sidebar.checkbox(
        "Transparent PNG background",
        key="png-transparent",
        value=bool(cfg.raw["viz"].get("transparent", False)),
        help="Applies to downloads. The preview here always shows a white page.",
    )
    PAGES[page](cfg, data, dpi)


main()
