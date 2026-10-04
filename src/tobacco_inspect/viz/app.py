"""Streamlit dashboard: every registered figure with a PNG download. Run `tobacco-inspect dashboard`.

No figure logic lives here; it only lays out the registry (see viz/registry.py).
"""

from __future__ import annotations

import io
import sys
import zipfile

import matplotlib
import streamlit as st

matplotlib.use("Agg")

from tobacco_inspect import viz  # noqa: E402,F401  (populates the registry)
from tobacco_inspect.config import load_config  # noqa: E402
from tobacco_inspect.viz import registry  # noqa: E402
from tobacco_inspect.viz.data import load_viz_data  # noqa: E402


def _config_path() -> str | None:
    argv = sys.argv[1:]
    return argv[argv.index("--config") + 1] if "--config" in argv else None


@st.cache_resource
def _config(path: str | None):
    return load_config(path)


@st.cache_data(show_spinner="Loading data")
def _data(path: str | None):
    return load_viz_data(_config(path))


def main() -> None:
    st.set_page_config(page_title="Tobacco inspection figures", layout="wide")
    cfg = _config(_config_path())
    data = _data(_config_path())
    default_dpi = int(cfg.raw["viz"]["dpi"])

    st.sidebar.title("Report figures")
    section = st.sidebar.radio("Section", registry.sections())
    dpi = st.sidebar.select_slider("PNG resolution (dpi)", [150, 200, 300, 450, 600], default_dpi)

    specs = [s for s in registry.FIGURES.values() if s.section == section]
    st.title(section)
    rendered = {}
    for spec in specs:
        with st.container(border=True):
            st.subheader(spec.title)
            if not registry.available(spec.name, data):
                st.info(
                    f"Needs data that is not present: {', '.join(spec.needs)}. Run the pipeline."
                )
                continue
            params = {}
            if spec.params:
                cols = st.columns(len(spec.params))
                for col, (key, (default, lo, hi, step)) in zip(
                    cols, spec.params.items(), strict=True
                ):
                    params[key] = col.slider(
                        key.replace("_", " "), lo, hi, default, step, key=f"{spec.name}-{key}"
                    )
            fig = registry.render(spec.name, data, cfg, **params)
            defaults = fig.default_text
            with st.expander("Edit text (defaults shown; changes apply to the exported PNG)"):
                # keying on the default means moving a slider that changes the default resets it
                edited = {
                    field: st.text_input(
                        field.title() if field != "source" else "Source note",
                        value=default,
                        key=f"{spec.name}-{field}-{hash(default)}",
                    )
                    for field, default in defaults.items()
                }
            text = {k: v for k, v in edited.items() if v != defaults[k]}
            if text:
                fig = registry.render(spec.name, data, cfg, text=text, **params)
            st.pyplot(fig, width="stretch")
            rendered[spec.name] = fig
            left, right, _ = st.columns([1, 1, 4])
            left.download_button(
                "Download PNG", registry.to_png_bytes(fig, dpi), f"{spec.name}.png", "image/png",
                key=f"png-{spec.name}",
            )  # fmt: skip
            tbl = registry.table(spec.name, data, cfg, **params)
            if tbl is not None:
                right.download_button(
                    "Download CSV", tbl.to_csv(index=False), f"{spec.name}.csv", "text/csv",
                    key=f"csv-{spec.name}",
                )  # fmt: skip

    if rendered:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, fig in rendered.items():
                zf.writestr(f"{name}.png", registry.to_png_bytes(fig, dpi))
        st.sidebar.download_button(
            f"Download this section (zip, {len(rendered)} PNGs)", buf.getvalue(), f"{section.lower()}_figures.zip",
            "application/zip",
        )  # fmt: skip


main()
