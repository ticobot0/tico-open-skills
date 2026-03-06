#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db() -> Path:
    return Path.home() / ".openclaw" / "workspace" / "data" / "latin-gradus-course" / "latin.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db()))
    ap.add_argument("--answers-json", required=True, help="JSON mapping ordinal->answer string")
    ap.add_argument("--auto-done", action="store_true", help="Mark items done if they have any answer (placeholder mode)")
    args = ap.parse_args()

    answers = json.loads(Path(args.answers_json).read_text(encoding="utf-8"))
    if not isinstance(answers, dict):
        raise SystemExit("answers-json must be a JSON object {ordinal: answer}")

    conn = sqlite3.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    st = cur.execute("SELECT v FROM state WHERE k='active_chapter_id'").fetchone()
    if not st:
        raise SystemExit("No active chapter")
    chapter_id = st[0]

    # map ordinal -> exercise_id
    ex_rows = cur.execute(
        "SELECT id, ordinal, prompt FROM exercises WHERE chapter_id=?",
        (chapter_id,),
    ).fetchall()
    by_ord = {int(r["ordinal"]): r for r in ex_rows}

    updated = 0
    for k, ans in answers.items():
        try:
            ordinal = int(k)
        except Exception:
            continue
        ex = by_ord.get(ordinal)
        if not ex:
            continue

        status = "pending"
        feedback = "Recebido. (Grading automático ainda não implementado)"
        if args.auto_done and str(ans).strip():
            status = "done"
            feedback = "✅ Marcado como feito (modo placeholder)."

        pr_id = f"pr:ex:{chapter_id}:{ordinal}"
        cur.execute(
            """
            UPDATE progress
               SET status=?,
                   attempts=attempts+1,
                   last_attempt_at=?,
                   last_feedback=?,
                   updated_at=?
             WHERE chapter_id=? AND exercise_id=?
            """,
            (status, utc_now(), feedback, utc_now(), chapter_id, ex["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()

    print(f"OK: updated {updated} answers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
