#!/usr/bin/env python3

"""Itaú PDF extractor (phase 1)

Extracts statement header fields (due date, total, issuer/account hints) from a decrypted PDF.
This is a lab helper; ingest.py will call this once stabilized.

Assumptions: PDF text is selectable (not OCR).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class ItauHeader:
    card_holder: str | None
    due_date: str | None  # YYYY-MM-DD
    total_minor: int | None
    currency: str


_re_total_due = re.compile(
    r"R\$\s*([0-9\.]+,[0-9]{2})\s+([0-9]{2}/[0-9]{2}/[0-9]{4})",
    re.MULTILINE,
)
_re_holder = re.compile(r"Titular\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ ]{5,})")


def brl_to_minor(s: str) -> int:
    # '6.554,29' -> 655429
    s = s.replace(".", "").replace(",", ".")
    return int(round(float(s) * 100))


def ddmmyyyy_to_iso(s: str) -> str:
    dd, mm, yyyy = s.split("/")
    return f"{yyyy}-{mm}-{dd}"


def extract_header(text: str) -> ItauHeader:
    holder = None
    m = _re_holder.search(text)
    if m:
        holder = m.group(1).strip()

    due_date = None
    total_minor = None

    m2 = _re_total_due.search(text)
    if m2:
        total_minor = brl_to_minor(m2.group(1))
        due_date = ddmmyyyy_to_iso(m2.group(2))

    # Itaú statements are typically BRL; keep as value, not hardcoded elsewhere.
    return ItauHeader(card_holder=holder, due_date=due_date, total_minor=total_minor, currency="BRL")


def extract_text_first_pages(pdf_path: Path, max_pages: int = 2) -> str:
    import pdfplumber  # type: ignore

    chunks: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i in range(min(max_pages, len(pdf.pages))):
            chunks.append(pdf.pages[i].extract_text() or "")
    return "\n".join(chunks)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to decrypted Itaú statement PDF")
    args = ap.parse_args()

    p = Path(args.pdf).expanduser().resolve()
    txt = extract_text_first_pages(p)
    h = extract_header(txt)

    print("holder:", h.card_holder)
    print("due_date:", h.due_date)
    print("total_minor:", h.total_minor)
    print("currency:", h.currency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
