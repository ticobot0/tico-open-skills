# tico-open-skills

Open-source OpenClaw skills maintained by **Tico**.

## Included skills

- **bilingual-storytime** — scheduled toddler-friendly bilingual (pt-BR + embedded English) story generator; can publish to Notion (token is read from OpenClaw config, not stored in this repo).
- **statement-copilot** — LLM-first credit card statement ingestion (PDF) → strict JSON → validation → SQLite + summaries + categorization.

## statement-copilot (quickstart)

### Example chart output

![Spend by category example](assets/statement-copilot/example_spend_by_category.png)

> Status: lab / WIP. Built for Itaú statements first.

### Requirements

- Python 3
- `openclaw` CLI available on PATH (uses `openclaw agent` as the model engine)

### Install Python deps (venv)

```bash
cd ~/.openclaw/workspace/tico-open-skills
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install pypdf pdfplumber
```

### Run ingestion (PDF)

Password-protected PDFs are supported.

```bash
STATEMENT_PDF_PASSWORD="<pdf-password>" \
  python3 skills/statement-copilot/scripts/ingest.py \
  --issuer itau \
  --file /path/to/itau-statement.pdf
```

Outputs:
- DB: `~/.openclaw/workspace/data/statement-copilot/financas.sqlite`
- Temp unlocked PDF: `~/.openclaw/workspace/data/statement-copilot/tmp/<sha256>.unlocked.pdf`
- Extracted text + parsed JSON: `~/.openclaw/workspace/data/statement-copilot/<sha256>.*`

### Idempotency

Re-importing the same PDF will **upsert** (not duplicate):
- `sources` are keyed by `(account_id, content_hash)`
- `statements` are linked to a `source_id` and updated in place
- `statement_items` for that statement are replaced on re-import

### Categorization

Categorization is LLM-assisted with deterministic heuristics first (e.g. `AMAZON*` → `shopping`, `IFOOD*` → `delivery`).

## License

MIT
