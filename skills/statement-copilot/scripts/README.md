Scripts in this skill:

- ingest.py: end-to-end pipeline (PDF → extract text → LLM parse → postprocess → categorize → validate/summarize → insert SQLite)
- extract_pdf_text.py: text extraction from PDF
- llm_parse.py: LLM-first JSON extraction via OpenClaw model engine
- postprocess_items.py: generic item cleanup (transaction vs statement_flow)
- categorize.py: LLM-assisted categorization + heuristic overrides
- validate_and_summarize.py: strict-ish schema validation + concise summary output
- insert_sqlite.py: upsert into SQLite (idempotent)
