"""Gallery page: curated figures and presets from the registry, each with editable text."""

from __future__ import annotations

import io
import zipfile

import streamlit as st

from tobacco_inspect.viz import registry
from tobacco_inspect.viz.ui.common import download_buttons, text_editor, transparent


def page(cfg, data, dpi: int) -> None:
    section = st.sidebar.radio("Section", registry.sections())
    st.title(section)
    rendered = {}
    for spec in (s for s in registry.FIGURES.values() if s.section == section):
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
            text = text_editor(spec.name, fig.default_text)
            if text:
                fig = registry.render(spec.name, data, cfg, text=text, **params)
            st.pyplot(fig, width="stretch")
            rendered[spec.name] = fig
            download_buttons(spec.name, fig, dpi, registry.table(spec.name, data, cfg, **params))
    if rendered:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, fig in rendered.items():
                zf.writestr(f"{name}.png", registry.to_png_bytes(fig, dpi, transparent()))
        st.sidebar.download_button(
            f"Download this section (zip, {len(rendered)} PNGs)",
            buf.getvalue(),
            f"{section.lower()}_figures.zip",
            "application/zip",
        )
