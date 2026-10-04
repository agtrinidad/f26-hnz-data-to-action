# 10. A declarative chart spec behind the dashboard Builder

Status: accepted (2026-10-03). Extends [ADR 0009](0009-viz-registry-and-dashboard.md).

## Context
The gallery (ADR 0009) only shows figures someone has coded. The team wants to make the common charts for this dataset without writing code, while keeping a small codebase that a new student team can maintain.

## Decision
1. **A chart is a `ChartSpec`**: dataset, kind, up to five column fields, aggregation, sort, top N, filters, per-kind options and text overrides. It serializes to JSON, so a chart designed in the Builder can be re-rendered by `tobacco-inspect viz --spec` and stored as a Gallery preset.
2. **Ten kinds** cover the dataset's common needs: bar, line, scatter, histogram, box, heatmap, concentration curve, map (points, tract choropleth, density), KPI tiles and ranked table. Facets are an option on the axes kinds. Dot-plus-interval and dumbbell charts are deferred (the two interval figures stay hand-coded).
3. **Each kind declares its fields and options**, and the Builder form is generated from that declaration. Adding a kind needs no UI code. Datasets are registered functions with column roles inferred from dtype and cardinality (`viz.columns` gives display names).
4. **Validation returns readable messages** (`SpecError.problems`) instead of tracebacks; the page shows them inline.
5. The grain of each dataset is shown (345 locations vs 467 licenses) because mixing them is the easiest way to mislead.

## Consequences
No new dependencies. Out of scope on purpose: dual axes, custom colors, free-form expressions, interactive charts, uploaded data. If a request needs one of these, add a hand-coded gallery figure first and promote it to a kind only after a third use.
