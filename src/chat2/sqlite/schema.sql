-- Generic store schema for chat2 primitives.
-- Two tables, one per data shape:
--   kv   -> documents (read/write whole value)
--   logs -> append-only line streams
-- Generic only: no chat/embedding vocabulary.

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

-- documents
CREATE TABLE kv (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL          -- ISO-8601 UTC
);

-- append-only logs
CREATE TABLE logs (
    key  TEXT NOT NULL,
    seq  INTEGER NOT NULL,
    line TEXT NOT NULL,
    PRIMARY KEY (key, seq)
);

-- schema version (SQLite's built-in hook)
PRAGMA user_version = 1;
