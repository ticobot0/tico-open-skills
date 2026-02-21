#!/usr/bin/env python3

"""Generate a spend-by-category bar chart (seaborn default).

This reads from the SQLite DB and outputs a PNG.

Example:
  python3 spend_by_category_chart.py --month 2026-01 --out /tmp/spend.png
  python3 spend_by_category_chart.py --month 2026-01 --style mono --highlight groceries --out /tmp/spend.png
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from chart_theme import set_theme, category_palette


def parse_month(s: str) -> tuple[str, str]:
    # returns [start, end) ISO date strings
    if len(s) != 7 or s[4] != "-":
        raise ValueError("month must be YYYY-MM")
    y = int(s[:4])
    m = int(s[5:7])
    if not (1 <= m <= 12):
        raise ValueError("invalid month")
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y+1:04d}-01-01"
    else:
        end = f"{y:04d}-{m+1:02d}-01"
    return start, end


def fmt_brl(minor: int) -> str:
    v = minor / 100.0
    # BR formatting without locale deps
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(Path.home() / ".openclaw" / "workspace" / "data" / "statement-copilot" / "financas.sqlite"))
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--out", required=True)
    ap.add_argument("--account", default=None, help="Optional: acc:nubank / acc:itau")
    ap.add_argument("--style", default="mono", choices=["mono", "category"], help="Color style")
    ap.add_argument(
        "--highlight",
        default="top1",
        help="Category to highlight (e.g. groceries) or 'top1' (default)",
    )
    ap.add_argument("--top", type=int, default=8, help="Top N categories (rest grouped as 'other')")
    ap.add_argument(
        "--no-labels",
        action="store_true",
        help="Hide value/% labels at the end of bars (labels are on by default)",
    )
    ap.add_argument(
        "--show-subtitle",
        action="store_true",
        help="Show subtitle with totals/top-N (off by default)",
    )
    ap.add_argument(
        "--hide-x-axis",
        action="store_true",
        help="Hide X axis ticks/labels/spine (recommended for minimalist charts)",
    )
    args = ap.parse_args()

    start, end = parse_month(args.month)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    params = [start, end]
    acc_where = ""
    if args.account:
        acc_where = " AND s.account_id = ?"
        params.append(args.account)

    rows = cur.execute(
        f"""
        SELECT COALESCE(si.category, 'uncategorized') AS category,
               SUM(si.amount_minor) AS total_minor
        FROM statement_items si
        JOIN statements s ON s.id = si.statement_id
        WHERE si.kind='purchase'
          AND si.direction='outflow'
          AND si.posted_at >= ? AND si.posted_at < ?
          {acc_where}
        GROUP BY COALESCE(si.category, 'uncategorized')
        ORDER BY total_minor DESC
        """,
        params,
    ).fetchall()

    if not rows:
        raise SystemExit("No rows for that month")

    theme = set_theme()
    ui = theme.get("ui") or {}
    accents = theme.get("accents") or {}
    palette = category_palette(theme)

    # top N + group rest into 'other'
    rows_sorted = list(rows)
    total_minor_all = sum(int(r["total_minor"]) for r in rows_sorted)

    top_n = max(1, int(args.top))
    top_rows = rows_sorted[:top_n]
    rest = rows_sorted[top_n:]
    rest_minor = sum(int(r["total_minor"]) for r in rest)

    cats = [r["category"] for r in top_rows]
    vals = [int(r["total_minor"]) for r in top_rows]
    if rest_minor > 0:
        # If "other" is already present (as a real category), merge rest into it.
        if "other" in cats:
            idx = cats.index("other")
            vals[idx] += rest_minor
        else:
            cats.append("other")
            vals.append(rest_minor)

    import pandas as pd  # type: ignore
    import seaborn as sns  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore

    df = pd.DataFrame({"category": cats, "total_minor": vals})
    # Ensure bars are always ordered by spend (desc), even after merging "other".
    df = df.sort_values("total_minor", ascending=False).reset_index(drop=True)

    df["pct"] = df["total_minor"].map(lambda v: (v / total_minor_all) if total_minor_all else 0.0)
    df["label"] = df.apply(lambda r: f"{fmt_brl(int(r.total_minor))}  ({r.pct*100:.0f}%)", axis=1)

    # highlight decision
    highlight = args.highlight
    if highlight == "top1":
        highlight = df.iloc[0]["category"]

    accent = accents.get("primary", "#22D3EE")
    mono = ui.get("mono_bar", "#B6BBC6")
    mono_dim = ui.get("mono_bar_dim", "#7A8191")

    if args.style == "mono":
        # Default: monochrome bars; one accent highlight.
        df["color"] = df["category"].map(lambda c: accent if c == highlight else mono_dim)
        # Keep grouped "other" slightly dimmer but not black.
        df.loc[df["category"] == "other", "color"] = mono_dim
    else:
        df["color"] = df["category"].map(lambda c: palette.get(c, palette.get("other", mono_dim)))

    # seaborn: avoid deprecated palette usage by using hue
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(
        data=df,
        y="category",
        x="total_minor",
        hue="category",
        palette=dict(zip(df["category"].tolist(), df["color"].tolist())),
        dodge=False,
        legend=False,
        errorbar=None,  # disable confidence interval line
        ax=ax,
        orient="h",
        edgecolor="none",
        linewidth=0,
    )

    # Title = conclusion-ish; keep it generic but useful
    title = f"Janeiro {args.month[:4]} — gastos por categoria"
    if args.account:
        title += f" ({args.account})"
    ax.set_title(title)

    if args.show_subtitle:
        subtitle = f"Total: {fmt_brl(total_minor_all)} • Top {top_n}{' + outros' if rest_minor>0 else ''}"
        ax.text(
            0,
            1.02,
            subtitle,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            color=ui.get("text_secondary", "#B6BBC6"),
            fontsize=10,
        )

    ax.set_xlabel("")
    ax.set_ylabel("")

    # labels (on by default)
    if not args.no_labels:
        xmax = max(vals) if vals else 0
        # Extend the plotting area so right-side labels stay inside the panel.
        ax.set_xlim(0, max(1, xmax) * 1.22)
        for i, (v, label) in enumerate(zip(df["total_minor"].tolist(), df["label"].tolist())):
            ax.text(
                v + max(1, xmax) * 0.02,
                i,
                label,
                va="center",
                color=ui.get("text_primary", "#F2F4F8"),
            )

    # Minimal grid / axes
    ax.grid(False)
    sns.despine(ax=ax, left=True, bottom=True)

    if args.hide_x_axis:
        ax.get_xaxis().set_visible(False)
        ax.spines["bottom"].set_visible(False)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=180)
    print(f"OK: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
