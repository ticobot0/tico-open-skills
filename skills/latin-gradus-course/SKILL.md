---
name: latin-gradus-course
description: Daily Latin course coach based on Gradus Primus / Gradus Secundus. Use to manage chapter-by-chapter study, send daily exercises, quiz the user, and track progress in SQLite until the chapter is completed.
---

# Latin Gradus Course

A daily, chapter-based Latin course assistant.

## Data

SQLite DB (default): `{workspace}/data/latin-gradus-course/latin.sqlite`

## Workflow

1) Add/import a chapter (title + lesson text + exercises)
2) Start the chapter
3) Every day:
   - send the next exercise(s)
   - collect answers
   - grade (with explanations)
   - mark exercise as done when correct
4) Only advance to the next chapter when the current chapter is complete.

## Scripts

- `scripts/init_db.py` — create DB schema
- `scripts/add_chapter.py` — add a chapter + exercises (from a local markdown/text file)
- `scripts/start_chapter.py` — set the active chapter
- `scripts/daily_quiz.py` — generate today’s prompt (based on remaining exercises)
- `scripts/grade_answers.py` — grade answers and update progress

## Notes / constraints

- Do NOT embed copyrighted book content in this repo. Store chapter content locally under `{workspace}/data/latin-gradus-course/` and import it.
- Prefer short daily batches (e.g., 5–10 minutes).
