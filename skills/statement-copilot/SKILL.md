---
name: statement-copilot
description: Ingest and analyze credit card statements (CSV/PDF) into SQLite for spend insights.
---

# Statement Copilot

Lab skill for a B2C personal finance MVP.

## What it does (MVP)

- Ingest credit card statements (initially Nubank/Itaú via PDF exports)
- Detect password-protected PDFs and require a password to unlock
- Extract full statement data using LLM-first parsing (OpenClaw model engine)
- Validate JSON strictly and store statements + items in SQLite (single DB)
- Generate a concise markdown summary (totals, top expenses; IOF modeled as its own fee line)

## Data storage

By default, store data under:

- DB: `{workspace}/data/statement-copilot/financas.sqlite`
- Uploads: `{workspace}/data/statement-copilot/uploads/`

(We keep DB and uploads out of the skill folder to avoid accidental open-source leaks.)

## Commands (planned)

- Ingest a statement file:

```bash
python3 {baseDir}/scripts/ingest.py --issuer itau --file /path/to/statement.pdf --verify-only

# password-protected PDF
python3 {baseDir}/scripts/ingest.py --issuer itau --file /path/to/statement.pdf --password "1234" --verify-only
# or via env
STATEMENT_PDF_PASSWORD="1234" python3 {baseDir}/scripts/ingest.py --issuer itau --file /path/to/statement.pdf --verify-only
```

- Summarize latest statement:

```bash
python3 {baseDir}/scripts/summarize.py --issuer nubank --period 2026-02
```

## Notes

- Multi-currency supported per item via `currency` + optional origin fields (`orig_currency`, `orig_amount_minor`, `fx_rate`).
- IOF is modeled as its own statement item (kind=`fee`).
- Secrets: none. Any future Open Banking tokens must come from OpenClaw config/env, never committed.

## TODO (roadmap)

- [ ] Add reconciliation check: warn if statement `total` doesn’t match the computed sum of items (transactions + statement flows).
