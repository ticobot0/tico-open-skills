#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_db() -> Path:
    return Path.home() / ".openclaw" / "workspace" / "data" / "latin-gradus-course" / "latin.sqlite"


@dataclass
class Exercise:
    prompt: str
    kind: str = "other"
    answer_key: str | None = None


def parse_jsonl(p: Path) -> list[Exercise]:
    """Expect JSONL with fields: prompt (required), kind (optional), answer_key (optional)."""
    out: list[Exercise] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out.append(
            Exercise(
                prompt=str(obj["prompt"]).strip(),
                kind=str(obj.get("kind") or "other"),
                answer_key=(str(obj["answer_key"]).strip() if obj.get("answer_key") else None),
            )
        )
    return out


def stable_id(*parts: str) -> str:
    h = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(default_db()))
    ap.add_argument("--book", required=True, help="gradus_primus|gradus_secundus|other")
    ap.add_argument("--chapter-no", type=int, required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--exercises-jsonl", required=True, help="Path to JSONL exercises")
    ap.add_argument("--source-path", default=None, help="Optional: local path to chapter content")
    args = ap.parse_args()

    db = Path(args.db)
    ex_path = Path(args.exercises_jsonl)
    exercises = parse_jsonl(ex_path)
    if not exercises:
        raise SystemExit("No exercises found")

    chapter_id = f"ch:{args.book}:{args.chapter_no}:{stable_id(args.title)}"

    conn = sqlite3.connect(db)
    cur = conn.cursor()

    cur.execute(
        """INSERT OR REPLACE INTO chapters(id, book, chapter_no, title, source_path, created_at)
           VALUES(?,?,?,?,?,?)""",
        (chapter_id, args.book, args.chapter_no, args.title, args.source_path, utc_now()),
    )

    # Upsert exercises by ordinal
    for idx, ex in enumerate(exercises, start=1):
        ex_id = f"ex:{chapter_id}:{idx}"
        cur.execute(
            """INSERT OR REPLACE INTO exercises(id, chapter_id, ordinal, prompt, answer_key, kind, created_at)
               VALUES(?,?,?,?,?,?,?)""",
            (ex_id, chapter_id, idx, ex.prompt, ex.answer_key, ex.kind, utc_now()),
        )
        # Ensure progress row exists
        cur.execute(
            """INSERT OR IGNORE INTO progress(id, chapter_id, exercise_id, status, attempts, created_at, updated_at)
               VALUES(?,?,?,?,0,?,?)""",
            (f"pr:{ex_id}", chapter_id, ex_id, "pending", utc_now(), utc_now()),
        )

    conn.commit()
    conn.close()

    print(f"OK: added chapter {chapter_id} exercises={len(exercises)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
