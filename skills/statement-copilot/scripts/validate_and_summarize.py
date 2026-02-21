#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


ALLOWED_DIRECTIONS = {"inflow", "outflow"}
ALLOWED_KINDS = {"purchase", "refund", "fee", "interest", "adjustment", "payment"}
ALLOWED_ITEM_TYPES = {"transaction", "statement_flow"}


def is_iso_date(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]


def validate(doc: dict) -> ValidationResult:
    errors: list[str] = []

    st = (doc or {}).get("statement")
    if not isinstance(st, dict):
        return ValidationResult(False, ["missing statement object"])

    for k in ("issuer", "currency", "total_minor", "items"):
        if k not in st:
            errors.append(f"statement missing field: {k}")

    cur = st.get("currency")
    if not isinstance(cur, str) or len(cur) != 3:
        errors.append("statement.currency must be ISO-4217 (3 letters)")

    tm = st.get("total_minor")
    if not isinstance(tm, int):
        errors.append("statement.total_minor must be int")

    for d in ("period_start", "period_end", "due_date"):
        v = st.get(d)
        if v is not None and (not isinstance(v, str) or not is_iso_date(v)):
            errors.append(f"statement.{d} must be YYYY-MM-DD or null")

    items = st.get("items")
    if not isinstance(items, list):
        errors.append("statement.items must be list")
        items = []

    for i, it in enumerate(items[:5000]):
        if not isinstance(it, dict):
            errors.append(f"item[{i}] not object")
            continue
        if not isinstance(it.get("amount_minor"), int):
            errors.append(f"item[{i}].amount_minor must be int")
        ic = it.get("currency")
        if not isinstance(ic, str) or len(ic) != 3:
            errors.append(f"item[{i}].currency must be ISO-4217")
        itype = it.get("item_type")
        if itype is not None and itype not in ALLOWED_ITEM_TYPES:
            errors.append(f"item[{i}].item_type invalid")

        dr = it.get("direction")
        if dr not in ALLOWED_DIRECTIONS:
            errors.append(f"item[{i}].direction invalid")
        kd = it.get("kind")
        if kd not in ALLOWED_KINDS:
            errors.append(f"item[{i}].kind invalid")
        pd = it.get("posted_at")
        if pd is not None and (not isinstance(pd, str) or not is_iso_date(pd)):
            errors.append(f"item[{i}].posted_at must be YYYY-MM-DD or null")

    return ValidationResult(ok=(len(errors) == 0), errors=errors)


def summarize(doc: dict) -> str:
    st = doc["statement"]
    items = st.get("items", [])

    total = st.get("total_minor")
    currency = st.get("currency")
    due = st.get("due_date")

    def fmt_minor(x: int) -> str:
        s = f"{abs(x)/100:,.2f}"
        # en-US to pt-BR-ish
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        sign = "-" if x < 0 else ""
        return sign + s

    def is_tx(it: dict) -> bool:
        # Default to transaction if field missing (backward compatibility)
        return it.get("item_type", "transaction") == "transaction"

    tx_items = [it for it in items if isinstance(it, dict) and is_tx(it)]
    flow_items = [it for it in items if isinstance(it, dict) and not is_tx(it)]

    # top 5 expenses (transactions only)
    expenses = [it for it in tx_items if it.get("direction") == "outflow" and isinstance(it.get("amount_minor"), int)]
    expenses_sorted = sorted(expenses, key=lambda it: it.get("amount_minor", 0), reverse=True)
    top = expenses_sorted[:5]

    # category rollup (top 6 by spend) - transactions only
    cat_totals: dict[str, int] = {}
    for it in expenses:
        cat = it.get("category") or "uncategorized"
        if not isinstance(cat, str):
            cat = "uncategorized"
        cat_totals[cat] = cat_totals.get(cat, 0) + int(it.get("amount_minor"))
    top_cats = sorted(cat_totals.items(), key=lambda kv: kv[1], reverse=True)[:6]

    lines = []
    lines.append(f"Issuer: {st.get('issuer')}")
    lines.append(f"Due date: {due}")
    lines.append(f"Total: {currency} {fmt_minor(total)}" if isinstance(total, int) else f"Total: {total}")
    lines.append("")
    if top_cats:
        lines.append("Top categories:")
        for cat, amt in top_cats:
            lines.append(f"- {cat}: {currency} {fmt_minor(amt)}")
        lines.append("")

    lines.append("Top expenses (transactions):")
    for it in top:
        cat = it.get("category") or "uncategorized"
        lines.append(
            f"- {it.get('posted_at')} | {it.get('description_raw')} | {cat} | {it.get('currency')} {fmt_minor(int(it.get('amount_minor')))}"
        )

    # Show a small summary of statement flows
    if flow_items:
        lines.append("")
        lines.append("Statement flows (top 5 by absolute value):")
        flows_sorted = sorted(
            [it for it in flow_items if isinstance(it.get('amount_minor'), int)],
            key=lambda it: abs(int(it.get('amount_minor'))),
            reverse=True,
        )[:5]
        for it in flows_sorted:
            lines.append(
                f"- {it.get('posted_at')} | {it.get('description_raw')} | {it.get('kind')} | {it.get('direction')} | {it.get('currency')} {fmt_minor(int(it.get('amount_minor')))}"
            )

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-file", required=True)
    args = ap.parse_args()

    doc = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    vr = validate(doc)
    if not vr.ok:
        print("INVALID")
        for e in vr.errors[:50]:
            print("-", e)
        return 2

    print(summarize(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
