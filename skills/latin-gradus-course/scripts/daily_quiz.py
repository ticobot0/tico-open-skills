#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def default_db() -> Path:
    return Path.home() / ".openclaw" / "workspace" / "data" / "latin-gradus-course" / "latin.sqlite"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db()))
    ap.add_argument("--n", type=int, default=3, help="How many pending exercises to send")
    args = ap.parse_args()

    conn = sqlite3.connect(Path(args.db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    st = cur.execute("SELECT v FROM state WHERE k='active_chapter_id'").fetchone()
    if not st:
        raise SystemExit("No active chapter. Run start_chapter.py")
    chapter_id = st[0]

    ch = cur.execute("SELECT book, chapter_no, title FROM chapters WHERE id=?", (chapter_id,)).fetchone()
    if not ch:
        raise SystemExit("Active chapter not found in DB")

    rows = cur.execute(
        """
        SELECT e.ordinal, e.id as exercise_id, e.prompt, e.kind
        FROM progress p
        JOIN exercises e ON e.id=p.exercise_id
        WHERE p.chapter_id=? AND p.status='pending'
        ORDER BY e.ordinal ASC
        LIMIT ?
        """,
        (chapter_id, args.n),
    ).fetchall()

    pending_count = cur.execute(
        """SELECT COUNT(*) FROM progress WHERE chapter_id=? AND status='pending'""",
        (chapter_id,),
    ).fetchone()[0]

    done_count = cur.execute(
        """SELECT COUNT(*) FROM progress WHERE chapter_id=? AND status='done'""",
        (chapter_id,),
    ).fetchone()[0]

    conn.close()

    if not rows:
        print(f"Capítulo concluído ✅ ({done_count} exercícios). Pode avançar para o próximo.")
        return 0

    header = f"📚 Latim — {ch['book']} cap. {ch['chapter_no']}: {ch['title']}\nProgresso: {done_count} feitos • {pending_count} pendentes\n\n"
    body = "Responda numerando (1, 2, 3...).\n\n"

    ex_lines = []
    for r in rows:
        ex_lines.append(f"{r['ordinal']}) [{r['kind']}] {r['prompt']}")

    print(header + body + "\n\n".join(ex_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
