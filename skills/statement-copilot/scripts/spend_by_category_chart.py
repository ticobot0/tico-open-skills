#!/usr/bin/env python3

"""Generate a spend-by-category bar chart (seaborn default).

This reads from the SQLite DB and outputs a PNG.

Example:
  python3 spend_by_category_chart.py --month 2026-01 --out /tmp/spend.png
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
    palette = category_palette(theme)

    cats = [r["category"] for r in rows]
    vals = [int(r["total_minor"]) for r in rows]

    import pandas as pd  # type: ignore
    import seaborn as sns  # type: ignore
    import matplotlib.pyplot as plt  # type: ignore

    df = pd.DataFrame({"category": cats, "total_minor": vals})
    df["total"] = df["total_minor"].map(fmt_brl)

    # map bar colors by category, fallback to palette default
    colors = [palette.get(c, palette.get("other", "#6B7280")) for c in df["category"].tolist()]

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=df, y="category", x="total_minor", ax=ax, palette=colors, orient="h")

    ax.set_title(f"Spend by category — {args.month}")
    ax.set_xlabel("")
    ax.set_ylabel("")

    # labels
    xmax = max(vals)
    for i, (v, label) in enumerate(zip(vals, df["total"].tolist())):
        ax.text(v + xmax * 0.01, i, label, va="center")

    # make it clean
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    sns.despine(ax=ax, left=True, bottom=False)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    print(f"OK: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
