#!/usr/bin/env python3
"""End-to-end daily run:
- load 300 words
- pick due words (spaced repetition) from sqlite
- generate an LLM prompt
- write markdown output to a file
- (optional) publish to Notion database

This script does NOT call the LLM itself; it produces a prompt and a stub output.
The OpenClaw agent should run this script, then write the final story, then publish.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from story_db import connect, ensure_run, ensure_words, select_words, mark_used


def load_words(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8").splitlines()
    words = []
    for w in raw:
        w = w.strip()
        if not w or w.startswith("#"):
            continue
        # strip quotes
        w = w.strip('"')
        if w and w not in words:
            words.append(w)
    return words


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="./data/bilingual-storytime.sqlite3")
    ap.add_argument("--words-file", default="./skills/bilingual-storytime/references/top_300_english_words.txt")
    ap.add_argument("--out-dir", default="./out/bilingual-storytime")
    ap.add_argument("--due", type=int, default=6)
    ap.add_argument("--new", type=int, default=2)
    ap.add_argument("--minutes", type=int, default=5)
    args = ap.parse_args()

    now = datetime.now().astimezone()
    today_iso = now.strftime("%Y-%m-%d")

    db_path = Path(args.db)
    words_file = Path(args.words_file)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    words = load_words(words_file)
    if len(words) < 50:
        raise SystemExit(f"words file looks too small: {words_file} ({len(words)} words)")

    conn = connect(db_path)
    current_run = ensure_run(conn, run_date=today_iso)

    ensure_words(conn, words, today_iso=today_iso, current_run=current_run)

    chosen = select_words(conn, current_run=current_run, due=args.due, new=args.new)
    # mark used now (we assume the story will use them)
    mark_used(conn, chosen, today_iso=today_iso, current_run=current_run)

    meta = {
        "generated_at": now.isoformat(),
        "date": today_iso,
        "run_id": current_run,
        "target_words": chosen,
        "minutes": args.minutes,
    }

    meta_path = out_dir / f"{today_iso}-meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # The agent will turn this into the final story.
    stub_md = out_dir / f"{today_iso}-story.md"
    stub_md.write_text(
        "# História bilíngue — Tico e Nino\n\n"
        f"(Gerado em {now.isoformat()})\n\n"
        "**Palavras de hoje (inglês):** "
        + ", ".join(chosen)
        + "\n\n"
        "---\n\n"
        "(A ser escrito pelo agente a partir do prompt gerado.)\n\n"
        "## Prática rápida\n\n"
        "(5 prompts curtos)\n\n"
        "## Glossário\n\n"
        "(1 item por palavra: frase em inglês + pronúncia + tradução/ideia)\n\n"
        "## Palavras de hoje\n\n"
        + "\n".join([f"- {w}" for w in chosen])
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps({"meta": str(meta_path), "stub": str(stub_md), "target_words": chosen}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
