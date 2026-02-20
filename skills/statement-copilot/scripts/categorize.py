#!/usr/bin/env python3

"""Categorize statement items (LLM-assisted).

Reads the parsed JSON (statement schema) and fills `category` for each item.
Uses OpenClaw model engine via `openclaw agent --json`.

Design:
- Controlled taxonomy (small set of categories).
- Batch classification to reduce tokens.
- Safe defaults: unknown -> "other".
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CATEGORIES = [
    "groceries",
    "restaurants",
    "delivery",
    "transport",
    "fuel",
    "health",
    "education",
    "shopping",
    "subscriptions",
    "entertainment",
    "travel",
    "bills",
    "fees_taxes",
    "cashback_refund",
    "other",
]

SYSTEM = (
    "You are a strict JSON classifier. "
    "Classify each transaction into exactly one category from the allowed list. "
    "Return ONLY JSON."
)


def run_agent(message: str, session_id: str) -> str:
    cmd = [
        "openclaw",
        "agent",
        "--json",
        "--thinking",
        "minimal",
        "--timeout",
        "600",
        "--session-id",
        session_id,
        "--message",
        message,
    ]
    p = subprocess.run(cmd, check=True, capture_output=True, text=True)
    data = json.loads(p.stdout)
    r = data.get("result") or {}
    payloads = r.get("payloads") or []
    if payloads and isinstance(payloads[0], dict) and isinstance(payloads[0].get("text"), str):
        return payloads[0]["text"].strip()
    # fallback
    return json.dumps(data)


def chunk(lst: list[dict], n: int) -> list[list[dict]]:
    return [lst[i : i + n] for i in range(0, len(lst), n)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input parsed JSON")
    ap.add_argument("--out", dest="out_path", required=True, help="Output JSON with categories")
    ap.add_argument("--issuer", required=True)
    ap.add_argument("--batch", type=int, default=30)
    args = ap.parse_args()

    doc = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    st = doc.get("statement")
    items = st.get("items") if isinstance(st, dict) else None
    if not isinstance(items, list):
        raise SystemExit("Invalid input: statement.items must be a list")

    session_id = f"statement-copilot-cat-{args.issuer}"

    allowed = ", ".join(CATEGORIES)

    out_items: list[dict] = []
    for b in chunk(items, args.batch):
        payload = [
            {
                "idx": i,
                "posted_at": it.get("posted_at"),
                "description": it.get("description_raw"),
                "kind": it.get("kind"),
                "direction": it.get("direction"),
                "amount_minor": it.get("amount_minor"),
                "currency": it.get("currency"),
            }
            for i, it in enumerate(b)
        ]

        prompt = (
            SYSTEM
            + "\n\nAllowed categories: ["
            + allowed
            + "]\n\nInput: "
            + json.dumps(payload, ensure_ascii=False)
            + "\n\nReturn JSON array of same length, each element: {\"idx\": <idx>, \"category\": <one of allowed>}"
        )

        raw = run_agent(prompt, session_id=session_id)
        try:
            cats = json.loads(raw)
        except Exception:
            # If model returned extra text, fail fast.
            raise SystemExit(f"Categorization returned non-JSON: {raw[:200]}")

        if not isinstance(cats, list) or len(cats) != len(payload):
            raise SystemExit("Categorization output length mismatch")

        # apply
        for j, it in enumerate(b):
            c = cats[j]
            cat = (c or {}).get("category")
            if cat not in CATEGORIES:
                cat = "other"
            it["category"] = cat
            out_items.append(it)

    st["items"] = out_items
    Path(args.out_path).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    print(f"OK: categorized {len(out_items)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
