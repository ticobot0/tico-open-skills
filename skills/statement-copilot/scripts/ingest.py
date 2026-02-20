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

    # LLM-first parsing pipeline:
    # 1) extract PDF text (all pages)
    # 2) ask OpenClaw agent to return strict JSON
    # 3) validate, insert into SQLite
    # 4) print a concise summary

    try:
        from extract_pdf_text import extract_text  # type: ignore

        # Keep prompt size reasonable for LLM-first: start with first 3 pages.
        txt = extract_text(readable_path, max_pages=3)
    except Exception as e:
        print(f"ERROR: failed to extract PDF text: {e}", file=sys.stderr)
        return 4

    data_dir().mkdir(parents=True, exist_ok=True)
    text_out = data_dir() / f"{file_hash}.txt"
    text_out.write_text(txt, encoding="utf-8")

    # Call LLM parser
    try:
        import subprocess, json

        json_out = data_dir() / f"{file_hash}.parsed.json"
        categorized_out = data_dir() / f"{file_hash}.categorized.json"
        session_id = f"statement-copilot-{args.issuer}-{file_hash[:12]}"
        p = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "llm_parse.py"),
                "--issuer",
                args.issuer,
                "--text-file",
                str(text_out),
                "--session-id",
                session_id,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        json_out.write_text(p.stdout.strip() + "\n", encoding="utf-8")

        # Validate parse output
        p2 = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "validate_and_summarize.py"),
                "--json-file",
                str(json_out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if p2.returncode != 0:
            print("ERROR: LLM output failed validation.", file=sys.stderr)
            print(p2.stdout)
            print(p2.stderr, file=sys.stderr)
            print(f"Raw JSON saved at: {json_out}")
            return 5

        # Categorize items (LLM-assisted)
        pc = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "categorize.py"),
                "--issuer",
                args.issuer,
                "--in",
                str(json_out),
                "--out",
                str(categorized_out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if pc.returncode != 0:
            print("ERROR: categorization failed", file=sys.stderr)
            print(pc.stdout)
            print(pc.stderr, file=sys.stderr)
            print(f"Raw JSON saved at: {json_out}")
            return 8

        # Validate + summarize categorized output
        p2c = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "validate_and_summarize.py"),
                "--json-file",
                str(categorized_out),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if p2c.returncode != 0:
            print("ERROR: categorized output failed validation.", file=sys.stderr)
            print(p2c.stdout)
            print(p2c.stderr, file=sys.stderr)
            print(f"Categorized JSON saved at: {categorized_out}")
            return 9

        # Insert categorized
        p3 = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "insert_sqlite.py"),
                "--issuer",
                args.issuer,
                "--json-file",
                str(categorized_out),
                "--source-type",
                "pdf",
                "--source-path",
                str(pdf_path),
                "--source-hash",
                file_hash,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if p3.returncode != 0:
            print("ERROR: failed to insert into SQLite", file=sys.stderr)
            print(p3.stdout)
            print(p3.stderr, file=sys.stderr)
            return 6

        # Print summary
        print(p3.stdout.strip())
        print("\n--- SUMMARY ---\n")
        print(p2c.stdout.strip())
        return 0

    except subprocess.CalledProcessError as e:
        print("ERROR: llm_parse failed", file=sys.stderr)
        print(e.stdout)
        print(e.stderr, file=sys.stderr)
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
