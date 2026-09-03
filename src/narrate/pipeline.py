from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from narrate.config import Settings
from narrate.extract import Book, extract_book
from narrate.jobs import get_job, update_job
from narrate.layout import deliver_to_jellyfin, install_book
from narrate.mux import concat_audio, write_m4b
from narrate.textutil import chunk_text
from narrate.tts import resolve_voice, synthesize_chunk
from narrate.voices import estimate_usd, get_model


def preview_book(path: Path, model_id: str) -> dict:
    book = extract_book(path)
    model = get_model(model_id)
    chunks = sum(len(chunk_text(ch.text, model.max_chars)) for ch in book.chapters)
    return {
        "title": book.title,
        "author": book.author,
        "source_kind": book.source_kind,
        "chars": book.chars,
        "chapter_count": len(book.chapters),
        "chunk_total": chunks,
        "estimated_usd": estimate_usd(model_id, book.chars),
        "warning": book.warning,
        "has_cover": bool(book.cover_bytes),
        "chapters": [
            {"title": chapter.title, "chars": chapter.chars}
            for chapter in book.chapters
        ],
    }


def run_job(conn: sqlite3.Connection, settings: Settings, job_id: int) -> Path:
    job = get_job(conn, job_id)
    if not job:
        raise RuntimeError(f"Job {job_id} not found")
    settings.ensure_dirs()
    update_job(conn, job_id, status="running", error="")

    source = Path(job["source_path"])
    book = extract_book(source)
    model = get_model(job["model"])
    voice = resolve_voice(model, job["voice"])
    work = settings.jobs_dir / str(job_id)
    work.mkdir(parents=True, exist_ok=True)
    cover_path = _write_cover(work, book)

    update_job(
        conn,
        job_id,
        author=book.author,
        title=book.title,
        chars=book.chars,
        chapter_count=len(book.chapters),
        estimated_usd=estimate_usd(model.id, book.chars),
        warning=book.warning,
    )

    chapter_files: list[tuple[str, Path]] = []
    chunk_done = 0
    chunk_total = sum(len(chunk_text(ch.text, model.max_chars)) for ch in book.chapters)
    update_job(conn, job_id, chunk_total=chunk_total)

    try:
        for index, chapter in enumerate(book.chapters):
            chapter_path = work / f"chapter-{index:03d}.m4a"
            chunks = chunk_text(chapter.text, model.max_chars)
            chunk_paths: list[Path] = []
            for chunk_index, chunk in enumerate(chunks):
                audio = work / f"chapter-{index:03d}-chunk-{chunk_index:03d}.mp3"
                if not audio.exists() or audio.stat().st_size < 200:
                    synthesize_chunk(
                        api_key=settings.openrouter_api_key,
                        model_id=model.id,
                        voice=voice,
                        text=chunk,
                        dest=audio,
                    )
                chunk_paths.append(audio)
                chunk_done += 1
                update_job(
                    conn,
                    job_id,
                    chapter_done=index,
                    chunk_done=chunk_done,
                    chunk_total=chunk_total,
                )
            if not chapter_path.exists() or chapter_path.stat().st_size < 200:
                concat_audio(chunk_paths, chapter_path)
            chapter_files.append((chapter.title, chapter_path))
            update_job(conn, job_id, chapter_done=index + 1)

        m4b = work / "book.m4b"
        write_m4b(
            chapters=chapter_files,
            dest=m4b,
            title=book.title,
            author=book.author,
            cover=cover_path,
        )
        installed = install_book(
            library=settings.library_dir,
            author=book.author,
            title=book.title,
            m4b=m4b,
            cover=cover_path,
        )
        extra = {"library": str(installed.parent)}
        warning = book.warning
        try:
            publish_note = _drop_into_jellyfin(settings, installed)
            if publish_note:
                extra["jellyfin"] = publish_note
        except Exception as exc:
            warning = "; ".join(
                part for part in (warning, f"Jellyfin drop-in failed: {exc}") if part
            )

        update_job(
            conn,
            job_id,
            status="done",
            output_path=str(installed),
            actual_usd=estimate_usd(model.id, book.chars),
            extra=json.dumps(extra),
            warning=warning,
        )
        return installed
    except Exception as exc:
        update_job(conn, job_id, status="error", error=str(exc)[:1000])
        raise


def _drop_into_jellyfin(settings: Settings, installed: Path) -> dict:
    return deliver_to_jellyfin(
        library=settings.library_dir,
        installed=installed,
        publish_target=settings.publish_target,
        jellyfin_url=settings.jellyfin_url,
        jellyfin_api_key=settings.jellyfin_api_key,
        container_path=settings.jellyfin_container_path,
    )


def _write_cover(work: Path, book: Book) -> Path | None:
    if not book.cover_bytes:
        return None
    suffix = ".png" if "png" in book.cover_mime else ".jpg"
    path = work / f"cover{suffix}"
    path.write_bytes(book.cover_bytes)
    return path
