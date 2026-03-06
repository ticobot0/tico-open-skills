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
    args = ap.parse_args()

    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).resolve().parent.parent / "references" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db)
    conn.executescript(schema)
    conn.commit()
    conn.close()

    print(f"OK: initialized {db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
