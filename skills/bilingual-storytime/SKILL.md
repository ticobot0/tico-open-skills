---
name: bilingual-storytime
description: Scheduled automation to generate toddler-friendly bilingual (pt-BR + embedded English words) stories starring Tico and Nino. Uses a 300-word list plus spaced repetition (SQLite) to choose which English words to practice, then publishes the story to Notion for Marcus.
---

# bilingual-storytime

Generate a scheduled bedtime story in **Portuguese** with **strategically embedded English words** to help toddlers absorb vocabulary.

## What this skill includes

- A **300-word list**: `references/top_300_english_words.txt`
- A **SQLite spaced-repetition DB** (Leitner-like buckets; run-based scheduling works well for weekly cadence)
- Scripts to:
  - pick the day’s target words
  - generate a strong prompt for the model
  - publish the finished story to a Notion database

## Files

- `scripts/story_db.py`: SQLite schema + spaced repetition selection
- `scripts/run_daily_story.py`: selects words + writes a stub/meta
- `scripts/generate_story_prompt.py`: builds the writing prompt
- `scripts/publish_to_notion.py`: posts markdown into a Notion database
- `references/top_300_english_words.txt`: vocabulary source

## Runtime workflow (recommended)

### 0) One-time: decide where the DB lives

Default DB path (workspace):
- `./data/bilingual-storytime.sqlite3`

### 1) Each run: select words + create prompt

```bash
python3 {baseDir}/scripts/run_daily_story.py \
  --db ./data/bilingual-storytime.sqlite3 \
  --words-file {baseDir}/references/top_300_english_words.txt \
  --out-dir ./out/bilingual-storytime \
  --due 6 --new 2 --minutes 5
```

This prints JSON with `target_words` and writes:
- `./out/bilingual-storytime/YYYY-MM-DD-meta.json`
- `./out/bilingual-storytime/YYYY-MM-DD-story.md` (stub)

Generate the writing prompt:

```bash
python3 {baseDir}/scripts/generate_story_prompt.py \
  --words-json '["the","and",...]' \
  --minutes 5
```

### 2) Write the final story (agent)

- Use the prompt to write the full Markdown story.
- Keep it safe, warm, funny, simple, with repetition and a mini practice section.
- Ensure every target word appears inside at least one **complete English sentence**.
- After each English sentence, add the pronunciation in parentheses as a pt-BR approximation for a Brazilian Portuguese reader (no phonetic symbols).
- Add a final **Glossário** section with sentence + pronunciation + translation/idea for each word.

### 3) Publish to Notion

```bash
python3 {baseDir}/scripts/publish_to_notion.py \
  --parent-page-id <NOTION_PARENT_PAGE_ID> \
  --md ./out/bilingual-storytime/YYYY-MM-DD-story.md \
  --date YYYY-MM-DD
```

## Automation hook (cron)

Use OpenClaw cron to run on your preferred schedule (e.g., weekly).
The cron job should:
1) run `run_daily_story.py`
2) generate prompt
3) write story
4) publish to Notion

(We’ll wire this up in the main OpenClaw config via `cron` tool.)
