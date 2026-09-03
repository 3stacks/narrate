from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from narrate.config import load_settings
from narrate.db import connect
from narrate.jobs import create_job, get_job, list_jobs
from narrate.pipeline import preview_book, run_job
from narrate.tts import resolve_voice
from narrate.voices import public_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="narrate",
        description="Turn owned EPUB/PDF books into Jellyfin-ready M4B audiobooks.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run the import web UI")
    serve.set_defaults(func=cmd_serve)

    preview = sub.add_parser("preview", help="Show chapters and cost without generating")
    preview.add_argument("file", type=Path)
    preview.add_argument("--model", default=None)
    preview.set_defaults(func=cmd_preview)

    import_cmd = sub.add_parser("import", help="Queue and generate an audiobook")
    import_cmd.add_argument("file", type=Path)
    import_cmd.add_argument("--who", default=None)
    import_cmd.add_argument("--model", default=None)
    import_cmd.add_argument("--voice", default=None)
    import_cmd.add_argument("--yes", action="store_true", help="Skip the cost confirm prompt")
    import_cmd.set_defaults(func=cmd_import)

    jobs = sub.add_parser("jobs", help="List recent jobs")
    jobs.set_defaults(func=cmd_jobs)

    retry = sub.add_parser("retry", help="Re-queue a failed or interrupted job")
    retry.add_argument("id", type=int)
    retry.set_defaults(func=cmd_retry)

    voices = sub.add_parser("voices", help="List TTS models and voices")
    voices.set_defaults(func=cmd_voices)

    args = parser.parse_args(argv)
    return args.func(args)


def cmd_serve(_args: argparse.Namespace) -> int:
    from narrate.server import serve

    serve()
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    settings = load_settings()
    model = args.model or settings.default_model
    data = preview_book(args.file.expanduser().resolve(), model)
    print(json.dumps(data, indent=2))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    settings = load_settings()
    settings.ensure_dirs()
    src = args.file.expanduser().resolve()
    if not src.exists():
        print(f"File not found: {src}", file=sys.stderr)
        return 1
    model_id = args.model or settings.default_model
    from narrate.voices import get_model

    model = get_model(model_id)
    voice = resolve_voice(model, args.voice or settings.default_voice)
    preview = preview_book(src, model.id)
    print(
        f"{preview['title']} / {preview['author']}\n"
        f"{preview['chapter_count']} chapters, {preview['chars']} chars, "
        f"about ${preview['estimated_usd']:.2f} on {model.label}"
    )
    if preview.get("warning"):
        print(f"Note: {preview['warning']}")
    if not args.yes:
        answer = input("Generate this audiobook? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return 1

    stored = settings.inbox_dir / src.name
    if src != stored:
        shutil.copy2(src, stored)
    conn = connect(settings.db_path)
    job_id = create_job(
        conn,
        importer=args.who or settings.users[0],
        source_path=str(stored),
        source_name=src.name,
        author=preview["author"],
        title=preview["title"],
        model=model.id,
        voice=voice,
        chars=preview["chars"],
        estimated_usd=preview["estimated_usd"],
        chapter_count=preview["chapter_count"],
        chunk_total=preview["chunk_total"],
        warning=preview.get("warning") or "",
    )
    print(f"Job {job_id} queued.")
    path = run_job(conn, settings, job_id)
    print(f"Wrote {path}")
    return 0


def cmd_jobs(_args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = connect(settings.db_path)
    for job in list_jobs(conn):
        print(
            f"#{job['id']:<4} {job['status']:<8} {job['importer']:<10} "
            f"{job['title'] or job['source_name']}  ${job['estimated_usd']:.2f}"
        )
    return 0


def cmd_retry(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = connect(settings.db_path)
    job = get_job(conn, args.id)
    if not job:
        print("No such job", file=sys.stderr)
        return 1
    from narrate.jobs import update_job

    update_job(conn, args.id, status="queued", error="")
    path = run_job(conn, settings, args.id)
    print(f"Wrote {path}")
    return 0


def cmd_voices(_args: argparse.Namespace) -> int:
    print(json.dumps(public_catalog(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
