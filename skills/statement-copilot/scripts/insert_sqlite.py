#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def workspace_dir() -> Path:
    env = os.getenv("STATEMENT_COPILOT_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def db_path() -> Path:
    return workspace_dir() / "data" / "statement-copilot" / "financas.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issuer", required=True)
    ap.add_argument("--json-file", required=True)
    ap.add_argument("--account-label", default=None)
    args = ap.parse_args()

    doc = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    st = doc["statement"]

    issuer = args.issuer
    account_id = f"acc:{issuer}"  # v0.1: single account per issuer

    conn = sqlite3.connect(db_path())
    try:
        cur = conn.cursor()

        # Upsert account
        cur.execute(
            "INSERT OR IGNORE INTO accounts (id, issuer, label, home_currency, created_at) VALUES (?,?,?,?,?)",
            (account_id, issuer, args.account_label or issuer, st.get("currency") or "BRL", now_iso()),
        )

        source_id = None

        statement_id = str(uuid.uuid4())
        cur.execute(
            "INSERT OR REPLACE INTO statements (id, account_id, period_start, period_end, due_date, total_minor, currency, source_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                statement_id,
                account_id,
                st.get("period_start"),
                st.get("period_end"),
                st.get("due_date"),
                st.get("total_minor"),
                st.get("currency"),
                source_id,
                now_iso(),
            ),
        )

        for it in st.get("items", []):
            item_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO statement_items (id, statement_id, posted_at, description_raw, merchant_norm, amount_minor, currency, direction, kind, installment_n, installment_total, category, orig_amount_minor, orig_currency, fx_rate, fingerprint, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    item_id,
                    statement_id,
                    it.get("posted_at"),
                    it.get("description_raw") or "",
                    it.get("merchant_norm"),
                    it.get("amount_minor"),
                    it.get("currency") or st.get("currency"),
                    it.get("direction") or "outflow",
                    it.get("kind") or "purchase",
                    it.get("installment_n"),
                    it.get("installment_total"),
                    it.get("category"),
                    it.get("orig_amount_minor"),
                    it.get("orig_currency"),
                    it.get("fx_rate"),
                    it.get("fingerprint") or item_id,
                    now_iso(),
                ),
            )

        conn.commit()
        print(f"OK: inserted statement_id={statement_id} items={len(st.get('items', []))}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
