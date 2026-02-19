-- Statement Copilot (SQLite) - schema v0.1

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  issuer TEXT NOT NULL,
  label TEXT,
  home_currency TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  imported_at TEXT NOT NULL,
  metadata_json TEXT,
  FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS statements (
  id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  due_date TEXT,
  total_minor INTEGER NOT NULL,
  currency TEXT NOT NULL,
  source_id TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(account_id) REFERENCES accounts(id),
  FOREIGN KEY(source_id) REFERENCES sources(id),
  UNIQUE(account_id, period_start, period_end)
);

CREATE TABLE IF NOT EXISTS statement_items (
  id TEXT PRIMARY KEY,
  statement_id TEXT NOT NULL,
  posted_at TEXT,
  description_raw TEXT NOT NULL,
  merchant_norm TEXT,
  amount_minor INTEGER NOT NULL,
  currency TEXT NOT NULL,
  direction TEXT NOT NULL, -- inflow|outflow
  kind TEXT NOT NULL,      -- purchase|refund|fee|interest|adjustment|payment
  installment_n INTEGER,
  installment_total INTEGER,
  category TEXT,
  orig_amount_minor INTEGER,
  orig_currency TEXT,
  fx_rate REAL,
  fingerprint TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(statement_id) REFERENCES statements(id)
);

CREATE INDEX IF NOT EXISTS idx_statement_items_statement_id ON statement_items(statement_id);
CREATE INDEX IF NOT EXISTS idx_statement_items_fingerprint ON statement_items(fingerprint);
