#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

SCHEMA_SQL = """
-- Note: this schema is designed to work whether you run daily or weekly.
-- We model spaced repetition by "run number" (execution count), not calendar days.

CREATE TABLE IF NOT EXISTS runs (
  run_id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_date TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

-- Legacy columns next_due/last_used are kept for backward compatibility.
CREATE TABLE IF NOT EXISTS words (
  word TEXT PRIMARY KEY,
  box INTEGER NOT NULL DEFAULT 1,

  -- Legacy (date-based). Kept, but not used by the new algorithm.
  next_due TEXT NOT NULL,
  last_used TEXT,

  -- New (run-based)
  next_due_run INTEGER,
  last_used_run INTEGER,

  times_used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  title TEXT NOT NULL,
  words_json TEXT NOT NULL,
  notion_url TEXT
);
"""

# Leitner-like intervals measured in *number of runs*.
# Example (weekly schedule): box 1 -> due next run; box 2 -> +2 runs; box 3 -> +4 runs...
INTERVAL_RUNS = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16}


@dataclass
class WordRow:
    word: str
    box: int
    next_due_run: int | None
    last_used_run: int | None
    times_used: int


def connect(db_path: str | Path) -> sqlite3.Connection:
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    # Lightweight migration: ensure new run-based columns exist even for older DBs.
    cur = conn.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(words)").fetchall()}
    if "next_due_run" not in cols:
        cur.execute("ALTER TABLE words ADD COLUMN next_due_run INTEGER")
    if "last_used_run" not in cols:
        cur.execute("ALTER TABLE words ADD COLUMN last_used_run INTEGER")

    # Initialize run-based scheduling if missing.
    # We set next_due_run=1 so everything becomes eligible on the first run-based execution.
    cur.execute("UPDATE words SET next_due_run=1 WHERE next_due_run IS NULL")
    conn.commit()

    return conn


def ensure_run(conn: sqlite3.Connection, run_date: str) -> int:
    """Get (or create) the run_id for a given ISO date (YYYY-MM-DD)."""
    cur = conn.cursor()
    existing = cur.execute("SELECT run_id FROM runs WHERE run_date=?", (run_date,)).fetchone()
    if existing:
        return int(existing[0])

    now = datetime.now().astimezone().isoformat()
    cur.execute("INSERT INTO runs(run_date, created_at) VALUES(?, ?)", (run_date, now))
    conn.commit()
    return int(cur.lastrowid)


def ensure_words(conn: sqlite3.Connection, words: Iterable[str], today_iso: str, current_run: int) -> None:
    cur = conn.cursor()
    for w in words:
        w = w.strip()
        if not w:
            continue
        # New words start due on the *next run*.
        # We keep legacy next_due/last_used filled for human readability, but use next_due_run.
        cur.execute(
            "INSERT OR IGNORE INTO words(word, box, next_due, last_used, next_due_run, last_used_run, times_used) "
            "VALUES(?, 1, ?, NULL, ?, NULL, 0)",
            (w, today_iso, current_run + 1),
        )
    conn.commit()


def select_words(conn: sqlite3.Connection, current_run: int, due: int, new: int) -> list[str]:
    cur = conn.cursor()

    due_rows = cur.execute(
        "SELECT word FROM words WHERE next_due_run <= ? ORDER BY times_used ASC, box ASC, RANDOM() LIMIT ?",
        (current_run, due),
    ).fetchall()
    due_words = [r["word"] for r in due_rows]

    new_rows = cur.execute(
        "SELECT word FROM words WHERE times_used = 0 ORDER BY RANDOM() LIMIT ?",
        (new,),
    ).fetchall()
    new_words = [r["word"] for r in new_rows]

    # If not enough due words, top up with least-used.
    need = max(0, (due + new) - (len(due_words) + len(new_words)))
    if need:
        more = cur.execute(
            "SELECT word FROM words ORDER BY times_used ASC, box ASC, RANDOM() LIMIT ?",
            (need,),
        ).fetchall()
        for r in more:
            w = r["word"]
            if w not in due_words and w not in new_words:
                due_words.append(w)

    # De-dupe preserve order.
    out: list[str] = []
    for w in due_words + new_words:
        if w not in out:
            out.append(w)
    return out[: (due + new)]


def mark_used(conn: sqlite3.Connection, words: list[str], today_iso: str, current_run: int) -> None:
    cur = conn.cursor()
    for w in words:
        row = cur.execute("SELECT box, times_used FROM words WHERE word=?", (w,)).fetchone()
        if not row:
            continue
        box = int(row[0])
        times_used = int(row[1])
        next_box = min(5, box + 1)
        interval_runs = INTERVAL_RUNS.get(next_box, 4)

        # Maintain both legacy (date-based) and new (run-based) fields.
        cur.execute(
            "UPDATE words "
            "SET box=?, times_used=?, last_used=?, next_due=?, last_used_run=?, next_due_run=? "
            "WHERE word=?",
            (
                next_box,
                times_used + 1,
                today_iso,
                today_iso,  # legacy: informational only
                current_run,
                current_run + interval_runs,
                w,
            ),
        )
    conn.commit()
