"""SQLite schema and connection handling.

The schema is created on first use and versioned, so later phases can migrate without
guessing. Data files live outside version control (see .gitignore).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    brief TEXT NOT NULL,
    queries TEXT NOT NULL,
    attributes TEXT NOT NULL,
    exclude TEXT NOT NULL,
    warnings TEXT NOT NULL DEFAULT '[]',
    errors TEXT NOT NULL DEFAULT '[]',
    refined_from TEXT,
    refinement_mode TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    session_id TEXT NOT NULL REFERENCES search_sessions(id) ON DELETE CASCADE,
    candidate_id TEXT NOT NULL,
    title TEXT NOT NULL,
    page_url TEXT NOT NULL,
    source TEXT NOT NULL,
    query TEXT NOT NULL DEFAULT '',
    snippet TEXT NOT NULL DEFAULT '',
    creator TEXT,
    metadata_confidence TEXT NOT NULL DEFAULT 'low',
    status TEXT NOT NULL DEFAULT 'ok',
    exclusion_reason TEXT,
    image_json TEXT,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (session_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS evaluations (
    session_id TEXT NOT NULL REFERENCES search_sessions(id) ON DELETE CASCADE,
    candidate_id TEXT NOT NULL,
    method TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (session_id, candidate_id, method)
);

CREATE TABLE IF NOT EXISTS references_ (
    reference_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    page_url TEXT NOT NULL UNIQUE,
    image_url TEXT,
    title TEXT NOT NULL,
    creator TEXT,
    why_selected TEXT,
    problem TEXT,
    method TEXT,
    transferable_lesson TEXT,
    cautions TEXT,
    analysis_origin TEXT NOT NULL DEFAULT 'model_observation',
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS project_references (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    reference_id TEXT NOT NULL REFERENCES references_(reference_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (project_id, reference_id)
);

CREATE INDEX IF NOT EXISTS idx_candidates_page ON candidates(page_url);
CREATE INDEX IF NOT EXISTS idx_references_source ON references_(source);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            connection = sqlite3.connect(self.path, check_same_thread=False)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            self._connection = connection
        return self._connection

    def initialize(self) -> None:
        connection = self.connection
        with connection:
            connection.executescript(SCHEMA)
            row = connection.execute("SELECT version FROM schema_version").fetchone()
            if row is None:
                connection.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            elif row["version"] != SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {row['version']} does not match the expected "
                    f"{SCHEMA_VERSION}: {self.path}"
                )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
