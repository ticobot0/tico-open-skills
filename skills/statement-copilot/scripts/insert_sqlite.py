#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
import hashlib
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
    ap.add_argument("--source-type", default="pdf")
    ap.add_argument("--source-path", default=None)
    ap.add_argument("--source-hash", default=None, help="sha256 of original file")
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

        # Upsert source (idempotent by account_id + content_hash)
        source_hash = args.source_hash
        if not source_hash:
            # fallback: hash JSON contents (not ideal, but keeps idempotency for repeated runs)
            source_hash = hashlib.sha256(json.dumps(doc, sort_keys=True).encode("utf-8")).hexdigest()

        cur.execute(
            "INSERT OR IGNORE INTO sources (id, account_id, source_type, file_path, content_hash, imported_at, metadata_json) VALUES (?,?,?,?,?,?,?)",
            (
                f"src:{issuer}:{source_hash[:16]}",
                account_id,
                args.source_type,
                args.source_path or "(unknown)",
                source_hash,
                now_iso(),
                None,
            ),
        )
        cur.execute(
            "SELECT id FROM sources WHERE account_id=? AND content_hash=?",
            (account_id, source_hash),
        )
        source_id = cur.fetchone()[0]

        # Determine period bounds (required by schema). If missing, derive from item dates.
        ps = st.get("period_start")
        pe = st.get("period_end")
        if not ps or not pe:
            dates = [it.get("posted_at") for it in st.get("items", []) if isinstance(it.get("posted_at"), str) and len(it.get("posted_at")) == 10]
            if dates:
                ps = min(dates)
                pe = max(dates)
            else:
                # last resort: use due_date's month (rough)
                dd = st.get("due_date")
                ps = dd[:8] + "01" if isinstance(dd, str) and len(dd) == 10 else "1970-01-01"
                pe = dd if isinstance(dd, str) and len(dd) == 10 else "1970-01-01"

        # Idempotent statement: prefer source_id match; fallback to unique period key.
        statement_id = None
        cur.execute("SELECT id FROM statements WHERE source_id=?", (source_id,))
        row = cur.fetchone()
        if row:
            statement_id = row[0]
        else:
            cur.execute(
                "SELECT id FROM statements WHERE account_id=? AND period_start=? AND period_end=?",
                (account_id, ps, pe),
            )
            row = cur.fetchone()
            if row:
                statement_id = row[0]

        if statement_id:
            # Replace items + refresh header fields
            cur.execute("DELETE FROM statement_items WHERE statement_id=?", (statement_id,))
            cur.execute(
                "UPDATE statements SET period_start=?, period_end=?, due_date=?, total_minor=?, currency=?, source_id=?, created_at=? WHERE id=?",
                (
                    ps,
                    pe,
                    st.get("due_date"),
                    st.get("total_minor"),
                    st.get("currency"),
                    source_id,
                    now_iso(),
                    statement_id,
                ),
            )
        else:
            statement_id = str(uuid.uuid4())
            # INSERT OR IGNORE to respect unique(account_id, period_start, period_end)
            cur.execute(
                "INSERT OR IGNORE INTO statements (id, account_id, period_start, period_end, due_date, total_minor, currency, source_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    statement_id,
                    account_id,
                    ps,
                    pe,
                    st.get("due_date"),
                    st.get("total_minor"),
                    st.get("currency"),
                    source_id,
                    now_iso(),
                ),
            )
            # If ignored (race/duplicate), fetch existing id
            cur.execute(
                "SELECT id FROM statements WHERE account_id=? AND period_start=? AND period_end=?",
                (account_id, ps, pe),
            )
            statement_id = cur.fetchone()[0]

        def fingerprint(it: dict) -> str:
            parts = [
                issuer,
                str(st.get("due_date") or ""),
                str(it.get("posted_at") or ""),
                str(it.get("description_raw") or ""),
                str(it.get("amount_minor") or ""),
                str(it.get("currency") or st.get("currency") or ""),
                str(it.get("direction") or ""),
                str(it.get("kind") or ""),
                str(it.get("installment_n") or ""),
                str(it.get("installment_total") or ""),
            ]
            return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

        for it in st.get("items", []):
            item_id = str(uuid.uuid4())
            fp = fingerprint(it)
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
                    fp,
                    now_iso(),
                ),
            )

        conn.commit()
        print(f"OK: upserted source_id={source_id} statement_id={statement_id} items={len(st.get('items', []))}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
