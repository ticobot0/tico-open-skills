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
    ap.add_argument("--chapter-id", required=True)
    args = ap.parse_args()

    conn = sqlite3.connect(Path(args.db))
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO state(k,v) VALUES('active_chapter_id', ?)", (args.chapter_id,))
    conn.commit()
    conn.close()

    print(f"OK: active chapter = {args.chapter_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
