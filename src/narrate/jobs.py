from __future__ import annotations

import json
import sqlite3
from typing import Any

from narrate.db import now, row_to_dict


def create_job(
    conn: sqlite3.Connection,
    *,
    importer: str,
    source_path: str,
    source_name: str,
    author: str,
    title: str,
    model: str,
    voice: str,
    chars: int,
    estimated_usd: float,
    chapter_count: int,
    chunk_total: int,
    warning: str = "",
    extra: dict | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO jobs (
            created_at, importer, status, source_path, source_name,
            author, title, model, voice, chars, estimated_usd,
            chapter_count, chunk_total, warning, extra
        ) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now(),
            importer,
            source_path,
            source_name,
            author,
            title,
            model,
            voice,
            chars,
            estimated_usd,
            chapter_count,
            chunk_total,
            warning,
            json.dumps(extra or {}),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [row_to_dict(row) for row in rows if row_to_dict(row)]


def next_queued(conn: sqlite3.Connection) -> dict[str, Any] | None:
    return row_to_dict(
        conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY id ASC LIMIT 1"
        ).fetchone()
    )


def update_job(conn: sqlite3.Connection, job_id: int, **fields: Any) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{key} = ?" for key in fields)
    conn.execute(
        f"UPDATE jobs SET {assignments} WHERE id = ?",
        [*fields.values(), job_id],
    )
    conn.commit()


def requeue_stale(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'queued', error = 'Interrupted. Will resume.' "
        "WHERE status = 'running'"
    )
    conn.commit()
