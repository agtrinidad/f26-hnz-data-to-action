"""Builder page: pick a dataset and chart type, map columns, filter, label, export.

The page only assembles a `ChartSpec`; drawing is `registry.render_spec`.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from tobacco_inspect.viz import datasets, registry
from tobacco_inspect.viz.build import choices, prepare
from tobacco_inspect.viz.charts import KINDS, Opt, fmt_cat
from tobacco_inspect.viz.charts_special import KPI_AGGS, KPI_FORMATS
from tobacco_inspect.viz.spec import AGGS, ChartSpec, SpecError
from tobacco_inspect.viz.ui.common import download_buttons, text_editor

PREFERRED = ("prize", "p", "h", "outlet_type", "fda_history", "year", "violation")


def _dash(c: str | None) -> str:
    return "—" if c is None else c


def _suggest(df: pd.DataFrame, ftype: str, used: set[str]) -> str | None:
    roles = datasets.infer_roles(df)
    pool = [c for c in choices(df, ftype) if roles[c] in {"numeric", "category", "date"}]
    pool = [c for c in PREFERRED if c in pool] + [c for c in pool if c not in PREFERRED]
    return next((c for c in pool if c not in used), None)


def _seed(key: str, value) -> None:
    """Set a widget's value before it is created (only if it has none yet)."""
    if key not in st.session_state:
        st.session_state[key] = value


def _load_spec(spec: ChartSpec) -> None:
    """Push a loaded spec into widget state (runs before any widget is created)."""
    ss = st.session_state
    ss["b-dataset"], ss["b-kind"] = spec.dataset, spec.kind
    pre = f"b-{spec.dataset}-{spec.kind}-"
    for name in ("x", "y", "color", "size", "facet"):
        ss[pre + name] = getattr(spec, name)
    ss[pre + "agg"], ss[pre + "sort"], ss[pre + "topn"] = spec.agg, spec.sort, spec.top_n or 0
    ss[pre + "fcols"] = [f["col"] for f in spec.filters]
    for f in spec.filters:
        ss[pre + "f-" + f["col"]] = f["values"] if "values" in f else (f["min"], f["max"])
    for name, value in spec.options.items():
        if name == "kpis":
            ss[pre + "kpi-n"] = len(value)
            for i, k in enumerate(value):
                ss[pre + f"kpi-{i}-label"] = k.get("label", "")
                ss[pre + f"kpi-{i}-col"] = k.get("column")
                ss[pre + f"kpi-{i}-agg"] = k.get("agg", "count")
                ss[pre + f"kpi-{i}-fmt"] = k.get("fmt", "number")
        else:
            ss[pre + "o-" + name] = value


def _filters(df: pd.DataFrame, pre: str, cfg) -> list[dict]:
    roles = datasets.infer_roles(df)
    cols = [c for c in df.columns if roles[c] in {"numeric", "category"}]
    picked = st.multiselect(
        "Filter rows on…",
        cols,
        key=pre + "fcols",
        format_func=lambda c: datasets.column_label(cfg, c),
    )
    out = []
    for c in picked:
        lab = datasets.column_label(cfg, c)
        s = df[c].dropna()
        if roles[c] == "category":
            vals = sorted(s.unique())
            _seed(pre + "f-" + c, vals)
            chosen = st.multiselect(lab, vals, key=pre + "f-" + c, format_func=fmt_cat)
            if set(chosen) != set(vals):
                out.append(
                    {"col": c, "values": [v.item() if hasattr(v, "item") else v for v in chosen]}
                )
        elif s.min() < s.max():
            lo, hi = float(s.min()), float(s.max())
            a, b = st.slider(lab, lo, hi, (lo, hi), key=pre + "f-" + c)
            if (a, b) != (lo, hi):
                out.append({"col": c, "min": a, "max": b})
    return out


def _option(o: Opt, df: pd.DataFrame, pre: str):
    key = pre + "o-" + o.name
    if o.type == "bool":
        _seed(key, o.default)
        return st.checkbox(o.label, key=key)
    if o.type == "int":
        _seed(key, int(o.default))
        return st.slider(o.label, int(o.lo), int(o.hi), key=key)
    if o.type == "float":
        _seed(key, float(o.default))
        return st.slider(o.label, float(o.lo), float(o.hi), key=key)
    if o.type == "choice":
        _seed(key, o.default)
        return st.selectbox(o.label, o.choices, key=key)
    _seed(key, list(df.columns[:6]))
    return st.multiselect(o.label, list(df.columns), key=key)


def _kpis(df: pd.DataFrame, pre: str, cfg) -> list[dict]:
    _seed(pre + "kpi-n", 3)
    n = st.number_input("Number of tiles", 1, 4, key=pre + "kpi-n")
    out = []
    for i in range(int(n)):
        c1, c2, c3, c4 = st.columns([2, 2, 1.3, 1.3])
        lab = c1.text_input("Label", key=pre + f"kpi-{i}-label")
        col = c2.selectbox(
            "Column", [None, *df.columns], key=pre + f"kpi-{i}-col",
            format_func=lambda c: "(count rows)" if c is None else datasets.column_label(cfg, c),
        )  # fmt: skip
        agg = c3.selectbox("Stat", KPI_AGGS, key=pre + f"kpi-{i}-agg")
        fmt = c4.selectbox("Format", KPI_FORMATS, key=pre + f"kpi-{i}-fmt")
        out.append({"label": lab, "column": col, "agg": agg, "fmt": fmt})
    return out


def page(cfg, data, dpi: int) -> None:
    st.title("Chart builder")
    if "b-pending" in st.session_state:
        _load_spec(st.session_state.pop("b-pending"))
    avail = [n for n in datasets.DATASETS if datasets.available(n, data)]
    if not avail:
        st.error("No data found. Run `tobacco-inspect run-all` first.")
        return
    left, right = st.columns([1, 2], gap="large")
    with left:
        with st.expander("Load a saved spec"):
            up = st.file_uploader("Spec JSON", type="json", key="b-upload")
            if up is not None and st.button("Load"):
                try:
                    st.session_state["b-pending"] = ChartSpec.from_json(up.read().decode("utf-8"))
                    st.rerun()
                except (SpecError, ValueError) as exc:
                    st.error(f"Could not load spec: {exc}")
        ds = st.selectbox(
            "Dataset", avail, key="b-dataset", format_func=lambda n: datasets.DATASETS[n].label
        )
        st.caption(f"One row = {datasets.DATASETS[ds].grain}")
        df = datasets.load(ds, data, cfg)
        kind_name = st.selectbox(
            "Chart type", list(KINDS), key="b-kind", format_func=lambda k: KINDS[k].label
        )
        kind, pre = KINDS[kind_name], f"b-{ds}-{kind_name}-"
        if kind.note:
            st.caption(kind.note)

        used: set[str] = set()
        picks: dict[str, str | None] = {}
        for name, fld in kind.fields.items():
            if fld.required:
                _seed(pre + name, _suggest(df, fld.type, used))
            opts = [None, *choices(df, fld.type)]
            val = st.selectbox(
                fld.label + (" *" if fld.required else ""), opts, key=pre + name,
                format_func=lambda c: _dash(None if c is None else datasets.column_label(cfg, c)),
            )  # fmt: skip
            picks[name] = val
            if val:
                used.add(val)

        agg, sort, top_n = "mean", "none", None
        if kind.uses_agg:
            _seed(pre + "agg", "mean")
            agg = st.selectbox("Aggregate", AGGS, key=pre + "agg")
        if kind.uses_sort:
            sort = st.radio("Sort", ["none", "desc", "asc"], horizontal=True, key=pre + "sort")
            _seed(pre + "topn", 0)
            n = st.number_input("Show top N (0 = all)", 0, 500, key=pre + "topn")
            top_n = int(n) or None
        filters = _filters(df, pre, cfg)
        options = {o.name: _option(o, df, pre) for o in kind.options}
        if kind_name == "kpi":
            options["kpis"] = _kpis(df, pre, cfg)

    spec = ChartSpec(ds, kind_name, agg=agg, sort=sort, top_n=top_n, filters=filters,
                     options=options, **picks)  # fmt: skip
    with right:
        try:
            fig = registry.render_spec(spec, data, cfg)
        except SpecError as exc:
            for problem in exc.problems:
                st.warning(problem)
            return
        text = text_editor(pre + "text", fig.default_text)
        if text:
            spec.text = text
            fig = registry.render_spec(spec, data, cfg, text=text)
        st.pyplot(fig, width="stretch")
        plotted = prepare(spec, data, cfg)
        download_buttons(f"{ds}_{kind_name}", fig, dpi, plotted, spec.to_json())
        with st.expander(f"Plotted data ({len(plotted)} rows)"):
            st.dataframe(plotted.head(500), hide_index=True)
