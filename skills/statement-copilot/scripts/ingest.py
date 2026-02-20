#!/usr/bin/env python3

"""Statement Copilot - ingest

MVP: handle PDF password detection/unlock, then (later) parse items.

Design goals:
- Never store PDF passwords.
- Fail fast with clear instructions when PDF is encrypted.
- Keep state in SQLite under workspace/data (not inside repo).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def workspace_dir() -> Path:
    # OpenClaw agents have a configured workspace; for CLI use, default to repo-relative guess.
    # Users can override via STATEMENT_COPILOT_WORKSPACE.
    env = os.getenv("STATEMENT_COPILOT_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()

    # Heuristic: repo lives under <workspace>/tico-open-skills/skills/statement-copilot
    # so go up 4 levels to reach <workspace>.
    return Path(__file__).resolve().parents[4]


def data_dir() -> Path:
    return workspace_dir() / "data" / "statement-copilot"


def db_path() -> Path:
    return data_dir() / "financas.sqlite"


def schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "references" / "schema.sql"


def ensure_db() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    p = db_path()
    conn = sqlite3.connect(p)
    try:
        with open(schema_path(), "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


@dataclass
class PdfOpenResult:
    encrypted: bool
    ok: bool
    error: str | None = None


def tmp_dir() -> Path:
    return data_dir() / "tmp"


def unlocked_pdf_path_for(hash_hex: str) -> Path:
    return tmp_dir() / f"{hash_hex}.unlocked.pdf"


def ensure_unlocked_pdf(pdf_path: Path, password: str | None) -> tuple[PdfOpenResult, Path]:
    """Return a path that is safe to read (original if not encrypted, else a temp unlocked copy)."""

    try:
        from pypdf import PdfReader, PdfWriter  # type: ignore
    except Exception:
        return (
            PdfOpenResult(
                encrypted=False,
                ok=False,
                error="Missing dependency: pypdf. Create a venv and install: pip install pypdf",
            ),
            pdf_path,
        )

    reader = PdfReader(str(pdf_path))
    if not reader.is_encrypted:
        return (PdfOpenResult(encrypted=False, ok=True), pdf_path)

    if not password:
        return (
            PdfOpenResult(
                encrypted=True,
                ok=False,
                error="PDF is password-protected. Re-run with --password or set STATEMENT_PDF_PASSWORD.",
            ),
            pdf_path,
        )

    try:
        res = reader.decrypt(password)
        if res == 0:
            return (
                PdfOpenResult(
                    encrypted=True,
                    ok=False,
                    error="Invalid PDF password (decrypt returned 0).",
                ),
                pdf_path,
            )

        # Write unlocked copy (idempotent by sha256)
        tmp_dir().mkdir(parents=True, exist_ok=True)
        h = sha256_file(pdf_path)
        out = unlocked_pdf_path_for(h)
        if not out.exists():
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            with out.open("wb") as f:
                writer.write(f)

        return (PdfOpenResult(encrypted=True, ok=True), out)
    except Exception as e:
        return (PdfOpenResult(encrypted=True, ok=False, error=f"Failed to decrypt PDF: {e}"), pdf_path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issuer", required=True, help="e.g. itau, nubank")
    ap.add_argument("--file", required=True, help="Path to statement PDF")
    ap.add_argument(
        "--password",
        default=None,
        help="PDF password (will not be stored). Can also be provided via STATEMENT_PDF_PASSWORD.",
    )
    ap.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify/unlock PDF (no parsing yet).",
    )
    args = ap.parse_args()

    pdf_path = Path(args.file).expanduser().resolve()
    if not pdf_path.exists():
        print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
        return 2

    password = args.password or os.getenv("STATEMENT_PDF_PASSWORD")

    # DB init (safe even if verify-only)
    ensure_db()

    # Verify / unlock (write unlocked temp copy when needed)
    r, readable_path = ensure_unlocked_pdf(pdf_path, password)
    if not r.ok:
        print(f"ERROR: {r.error}", file=sys.stderr)
        return 3

    file_hash = sha256_file(pdf_path)
    enc = "encrypted" if r.encrypted else "not-encrypted"
    if readable_path != pdf_path:
        print(
            f"OK: PDF opened ({enc}); sha256={file_hash[:12]}…; unlocked_copy={readable_path}")
    else:
        print(f"OK: PDF opened ({enc}); sha256={file_hash[:12]}…")

    if args.verify_only:
        return 0

    # Next step: parse from readable_path
    print(f"NOTE: parsing not implemented yet. Ready-to-parse path: {readable_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
