#!/usr/bin/env python3

"""Generic post-processing for statement items.

Goal: keep scripts bank-agnostic.

- Enforces/repairs `item_type` (transaction vs statement_flow)
- Normalizes `kind`/`direction` when strong keyword signals exist
- Leaves original text intact

This improves:
- spend summaries (exclude statement_flow)
- reconciliation (include both)
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


RE_PAYMENT = re.compile(r"\b(PAGAMENTO|PAYMENT|PIX)\b", re.I)
RE_BALANCE = re.compile(r"\b(SALDO|BALANCE|EM\s+ABERTO|EM\s+ATRASO|ATRASO)\b", re.I)
RE_INTEREST = re.compile(r"\b(JUROS|INTEREST)\b", re.I)
RE_FEE = re.compile(r"\b(IOF|TARIFA|FEE|ENCARGO|MULTA)\b", re.I)


def decide_item_type(desc: str, kind: str | None) -> str:
    if RE_PAYMENT.search(desc) or RE_BALANCE.search(desc) or RE_INTEREST.search(desc) or RE_FEE.search(desc):
        return "statement_flow"
    # explicit non-spend kinds still flow
    if kind in {"payment", "interest", "fee", "adjustment"}:
        return "statement_flow"
    return "transaction"


def normalize_item(item: dict) -> dict:
    desc = str(item.get("description_raw") or "")
    kind = item.get("kind")
    direction = item.get("direction")

    item_type = item.get("item_type")
    if item_type not in {"transaction", "statement_flow"}:
        item_type = decide_item_type(desc, kind)

    # Force obvious mappings
    if RE_PAYMENT.search(desc):
        kind = "payment"
        direction = "inflow"
        item_type = "statement_flow"

    if RE_INTEREST.search(desc):
        kind = "interest"
        item_type = "statement_flow"

    if RE_FEE.search(desc):
        # keep interest separate if already set
        if kind not in {"interest", "payment"}:
            kind = "fee"
        item_type = "statement_flow"

    if RE_BALANCE.search(desc):
        # carried/late balances usually increase what you owe
        if kind not in {"payment"}:
            kind = kind or "adjustment"
            direction = direction or "outflow"
        item_type = "statement_flow"

    # Defaults
    if direction not in {"inflow", "outflow"}:
        direction = "outflow"

    if kind not in {"purchase", "refund", "fee", "interest", "adjustment", "payment"}:
        kind = "purchase" if item_type == "transaction" else "adjustment"

    item["item_type"] = item_type
    item["kind"] = kind
    item["direction"] = direction
    return item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    args = ap.parse_args()

    doc = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    st = doc.get("statement")
    items = st.get("items") if isinstance(st, dict) else None
    if not isinstance(items, list):
        raise SystemExit("Invalid input: statement.items must be a list")

    st["items"] = [normalize_item(it) for it in items]

    Path(args.out_path).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"OK: postprocessed {len(items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
