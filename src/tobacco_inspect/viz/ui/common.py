"""Streamlit helpers shared by the Gallery and Builder pages (no figure logic here)."""

from __future__ import annotations

import sys

import streamlit as st

from tobacco_inspect.config import load_config
from tobacco_inspect.viz import registry
from tobacco_inspect.viz.data import load_viz_data


def config_path() -> str | None:
    argv = sys.argv[1:]
    return argv[argv.index("--config") + 1] if "--config" in argv else None


@st.cache_resource
def get_config(path: str | None):
    return load_config(path)


@st.cache_data(show_spinner="Loading data")
def get_data(path: str | None):
    return load_viz_data(get_config(path))


def text_editor(key: str, defaults: dict[str, str]) -> dict[str, str]:
    """Title/subtitle/source inputs prefilled with `defaults`; returns only the edited fields.

    Keyed on the default text, so a change that alters the default (a slider, a new column)
    resets the field to the new default.
    """
    with st.expander("Edit text (defaults shown; changes apply to the exported PNG)"):
        edited = {
            field: st.text_input(
                "Source note" if field == "source" else field.title(),
                value=default,
                key=f"{key}-{field}-{hash(default)}",
            )
            for field, default in defaults.items()
        }
    return {k: v for k, v in edited.items() if v != defaults[k]}


def download_buttons(key: str, fig, dpi: int, table=None, spec_json: str | None = None) -> None:
    """PNG always; CSV of the plotted data and the chart recipe when provided."""
    cols = st.columns([1, 1, 1, 3])
    cols[0].download_button(
        "Download PNG", registry.to_png_bytes(fig, dpi), f"{key}.png", "image/png", key=f"png-{key}"
    )
    if table is not None:
        cols[1].download_button(
            "Download CSV", table.to_csv(index=False), f"{key}.csv", "text/csv", key=f"csv-{key}"
        )
    if spec_json is not None:
        cols[2].download_button(
            "Download spec", spec_json, f"{key}.json", "application/json", key=f"spec-{key}"
        )
