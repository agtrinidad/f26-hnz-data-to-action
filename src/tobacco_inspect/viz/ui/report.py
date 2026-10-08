"""Report page: the final report's figures in order, with editable text, caption and alt text."""

from __future__ import annotations

import io
import zipfile

import streamlit as st

from tobacco_inspect.viz import registry
from tobacco_inspect.viz.report import captions_markdown, load_manifest
from tobacco_inspect.viz.ui.common import download_buttons, text_editor, transparent

STATUS = {"ready": "ready", "rerender": "re-render before use", "todo": "new, review"}


def page(cfg, data, dpi: int) -> None:
    st.title("Final report figures")
    st.caption(
        "Order, captions and alt text come from config/report_figures.yaml. Edit the title, "
        "subtitle and source in each figure's expander, and the caption and alt text below it; "
        "downloads reflect your edits."
    )
    manifest = load_manifest()
    only = st.sidebar.multiselect(
        "Show audience", sorted({a for m in manifest for a in m.audience})
    )
    keep, exported = [], []
    for rf in manifest:
        if only and not set(only) & set(rf.audience):
            continue
        spec = registry.FIGURES[rf.figure]
        with st.container(border=True):
            top = st.columns([4, 1])
            top[0].subheader(f"{rf.id.replace('fig', 'Figure ')}: {spec.title}")
            use = top[1].checkbox("Include in export", True, key=f"rep-use-{rf.id}")
            st.markdown(
                f"**Takeaway:** {rf.takeaway}  \n**Report section:** {rf.report_section}  \n"
                f"**Audience:** {', '.join(rf.audience)}  ·  "
                f"**Status:** {STATUS.get(rf.status, rf.status)}"
            )
            if not registry.available(rf.figure, data):
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
                        key.replace("_", " "), lo, hi, default, step, key=f"rep-{rf.id}-{key}"
                    )
            fig = registry.render(rf.figure, data, cfg, **params)
            text = text_editor(f"rep-{rf.id}", fig.default_text)
            if text:
                fig = registry.render(rf.figure, data, cfg, text=text, **params)
            st.pyplot(fig, width="stretch")
            caption = st.text_area("Caption", rf.caption, key=f"rep-cap-{rf.id}-{hash(rf.caption)}")
            alt = st.text_area("Alt text", rf.alt, key=f"rep-alt-{rf.id}-{hash(rf.alt)}", height=68)
            download_buttons(
                f"{rf.id}_{rf.figure}", fig, dpi, registry.table(rf.figure, data, cfg, **params)
            )
            if use:
                keep.append((rf, caption, alt))
                exported.append((rf.filename, fig))
    if exported:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, fig in exported:
                zf.writestr(name, registry.to_png_bytes(fig, dpi, transparent()))
            zf.writestr("captions.md", captions_markdown(keep))
        st.sidebar.download_button(
            f"Download report figures (zip, {len(exported)} PNGs + captions)",
            buf.getvalue(),
            "report_figures.zip",
            "application/zip",
        )
