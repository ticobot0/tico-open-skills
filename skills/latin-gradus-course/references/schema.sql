-- latin-gradus-course schema

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS chapters (
  id TEXT PRIMARY KEY,
  book TEXT NOT NULL,              -- gradus_primus | gradus_secundus | other
  chapter_no INTEGER NOT NULL,
  title TEXT NOT NULL,
  source_path TEXT,                -- local path to imported content (not committed)
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exercises (
  id TEXT PRIMARY KEY,
  chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  prompt TEXT NOT NULL,
  answer_key TEXT,                 -- optional (may be null; use LLM grading)
  kind TEXT NOT NULL,              -- translation|grammar|vocab|reading|other
  created_at TEXT NOT NULL,
  UNIQUE(chapter_id, ordinal)
);

CREATE TABLE IF NOT EXISTS progress (
  id TEXT PRIMARY KEY,
  chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  exercise_id TEXT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
  status TEXT NOT NULL,            -- pending|done
  attempts INTEGER NOT NULL DEFAULT 0,
  last_attempt_at TEXT,
  last_feedback TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(chapter_id, exercise_id)
);

CREATE TABLE IF NOT EXISTS state (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);

-- k='active_chapter_id' => current chapter
