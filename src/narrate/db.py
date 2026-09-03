from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    importer TEXT NOT NULL,
    status TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_name TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL,
    voice TEXT NOT NULL,
    chars INTEGER NOT NULL DEFAULT 0,
    estimated_usd REAL NOT NULL DEFAULT 0,
    actual_usd REAL NOT NULL DEFAULT 0,
    chapter_count INTEGER NOT NULL DEFAULT 0,
    chapter_done INTEGER NOT NULL DEFAULT 0,
    chunk_done INTEGER NOT NULL DEFAULT 0,
    chunk_total INTEGER NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    output_path TEXT NOT NULL DEFAULT '',
    warning TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '{}'
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(SCHEMA)
    return conn


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    try:
        data["extra"] = json.loads(data.get("extra") or "{}")
    except json.JSONDecodeError:
        data["extra"] = {}
    return data
