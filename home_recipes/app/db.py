import sqlite3
import threading
from pathlib import Path
from typing import Optional

from config import DB_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    servings    INTEGER,
    minutes     INTEGER,
    ingredients TEXT NOT NULL DEFAULT '[]',  -- JSON list of lines
    steps       TEXT NOT NULL DEFAULT '[]',  -- JSON list of lines
    tags        TEXT NOT NULL DEFAULT '[]',  -- JSON list
    source_url  TEXT NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,            -- unix seconds, UTC
    updated_at  INTEGER NOT NULL
);

-- One row each time a recipe is cooked; this is what the statistics are built from
CREATE TABLE IF NOT EXISTS cooked (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id  INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    cooked_at  INTEGER NOT NULL,
    user_name  TEXT
);

CREATE INDEX IF NOT EXISTS idx_cooked_at ON cooked(cooked_at);
CREATE INDEX IF NOT EXISTS idx_cooked_recipe ON cooked(recipe_id);
"""

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


def connect(path: Optional[Path] = None) -> None:
    global _conn
    if path is None:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        path = DB_DIR / "home_recipes.db"
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA journal_mode = WAL")
    _conn.executescript(SCHEMA)


def query(sql: str, args=()) -> list:
    with _lock:
        return [dict(r) for r in _conn.execute(sql, args)]


def execute(sql: str, args=()) -> sqlite3.Cursor:
    with _lock:
        cur = _conn.execute(sql, args)
        _conn.commit()
        return cur
