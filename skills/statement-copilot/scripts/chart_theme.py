#!/usr/bin/env python3

"""Seaborn-first chart theme for statement-copilot.

Usage:
    from chart_theme import set_theme, category_palette
    set_theme()

This is intentionally bank-agnostic: colors are keyed by our taxonomy categories.
"""

from __future__ import annotations

import json
from pathlib import Path


def _theme_path() -> Path:
    return Path(__file__).resolve().parent.parent / "references" / "chart_theme.json"


def load_theme() -> dict:
    return json.loads(_theme_path().read_text(encoding="utf-8"))


def category_palette(theme: dict | None = None) -> dict[str, str]:
    theme = theme or load_theme()
    return dict(theme.get("category_colors") or {})


def set_theme(theme: dict | None = None) -> dict:
    """Apply seaborn/matplotlib settings. Returns the theme dict."""

    theme = theme or load_theme()
    ui = theme.get("ui") or {}

    # Seaborn is the default; fall back gracefully if absent.
    try:
        import seaborn as sns  # type: ignore

        # Base seaborn theme
        sns.set_theme(
            context="notebook",
            style="darkgrid",
            font="DejaVu Sans",
            rc={
                "figure.facecolor": ui.get("bg", "#2F3136"),
                "axes.facecolor": ui.get("panel", "#26282D"),
                "axes.edgecolor": ui.get("axes", "#8E94A3"),
                "axes.labelcolor": ui.get("text_secondary", "#B6BBC6"),
                "text.color": ui.get("text_primary", "#F2F4F8"),
                "xtick.color": ui.get("text_secondary", "#B6BBC6"),
                "ytick.color": ui.get("text_secondary", "#B6BBC6"),
                "grid.color": ui.get("grid", "#3B3E45"),
                "grid.linewidth": 0.8,
                "axes.grid": True,
                "axes.axisbelow": True,
                "legend.frameon": False,
            },
        )
    except ModuleNotFoundError:
        pass

    # Matplotlib rcParams (also covers non-seaborn usage)
    try:
        import matplotlib as mpl  # type: ignore

        mpl.rcParams.update(
            {
                "figure.facecolor": ui.get("bg", "#2F3136"),
                "savefig.facecolor": ui.get("bg", "#2F3136"),
                "axes.facecolor": ui.get("panel", "#26282D"),
                "axes.edgecolor": ui.get("axes", "#8E94A3"),
                "axes.labelcolor": ui.get("text_secondary", "#B6BBC6"),
                "text.color": ui.get("text_primary", "#F2F4F8"),
                "xtick.color": ui.get("text_secondary", "#B6BBC6"),
                "ytick.color": ui.get("text_secondary", "#B6BBC6"),
                "grid.color": ui.get("grid", "#3B3E45"),
                "axes.titlecolor": ui.get("text_primary", "#F2F4F8"),
            }
        )
    except ModuleNotFoundError:
        pass

    return theme
