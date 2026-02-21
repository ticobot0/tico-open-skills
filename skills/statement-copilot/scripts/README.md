Scripts in this skill:

- ingest.py: end-to-end pipeline (PDF → extract text → LLM parse → postprocess → categorize → validate/summarize → insert SQLite)
- extract_pdf_text.py: text extraction from PDF
- llm_parse.py: LLM-first JSON extraction via OpenClaw model engine
- postprocess_items.py: generic item cleanup (transaction vs statement_flow)
- categorize.py: LLM-assisted categorization + heuristic overrides
- validate_and_summarize.py: strict-ish schema validation + concise summary output
- insert_sqlite.py: upsert into SQLite (idempotent)
- chart_theme.py: apply the default dark theme (seaborn-first) + category palette
- spend_by_category_chart.py: generate a spend-by-category chart PNG
  - Examples:
    - Both cards (default mono+accent):
      `python3 spend_by_category_chart.py --month 2026-01 --hide-x-axis --out /tmp/spend.png`
    - Single card:
      `python3 spend_by_category_chart.py --month 2026-01 --account acc:nubank --hide-x-axis --out /tmp/nubank.png`
    - Tuning:
      `--top 8` (group the rest into `other`), `--highlight groceries|top1`, `--no-labels`, `--style mono|category`
