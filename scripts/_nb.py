"""Shared cell helpers for the notebook generators (scripts/build_notebook_0*.py)."""

from __future__ import annotations

import nbformat as nbf

cells: list = []


def md(text: str, tags=None):
    c = nbf.v4.new_markdown_cell(text.strip("\n"))
    if tags:
        c.metadata["tags"] = tags
    cells.append(c)


def code(text: str):
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))
