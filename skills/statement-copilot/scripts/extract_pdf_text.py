#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path


def extract_text(pdf_path: Path, max_pages: int | None = None) -> str:
    import pdfplumber  # type: ignore

    out: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        n = len(pdf.pages)
        stop = min(n, max_pages) if max_pages else n
        for i in range(stop):
            out.append(f"\n\n===== PAGE {i+1}/{n} =====\n")
            out.append(pdf.pages[i].extract_text() or "")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--max-pages", type=int, default=0)
    args = ap.parse_args()

    p = Path(args.pdf).expanduser().resolve()
    txt = extract_text(p, max_pages=args.max_pages or None)
    print(txt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
