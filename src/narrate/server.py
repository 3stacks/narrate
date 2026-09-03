from __future__ import annotations

import secrets
import shutil
import threading
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from narrate.config import Settings, load_settings
from narrate.db import connect
from narrate.jobs import create_job, get_job, list_jobs, next_queued, requeue_stale, update_job
from narrate.pipeline import preview_book, run_job
from narrate.tts import resolve_voice
from narrate.voices import get_model, public_catalog

WEB = Path(__file__).parent / "web"
_worker_lock = threading.Lock()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.ensure_dirs()
    conn = connect(settings.db_path)
    requeue_stale(conn)

    app = FastAPI(title="narrate", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.conn = conn
    security = HTTPBasic(auto_error=False)

    def require_auth(
        credentials: HTTPBasicCredentials | None = Depends(security),
    ) -> None:
        expected = settings.basic_auth
        if not expected:
            return
        if ":" not in expected:
            raise HTTPException(status_code=500, detail="NARRATE_BASIC_AUTH must be user:password")
        user, password = expected.split(":", 1)
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail="auth required",
                headers={"WWW-Authenticate": "Basic"},
            )
        ok_user = secrets.compare_digest(credentials.username, user)
        ok_pass = secrets.compare_digest(credentials.password, password)
        if not (ok_user and ok_pass):
            raise HTTPException(
                status_code=401,
                detail="bad credentials",
                headers={"WWW-Authenticate": "Basic"},
            )

    @app.get("/")
    def index(_: None = Depends(require_auth)) -> FileResponse:
        return FileResponse(WEB / "index.html")

    @app.get("/api/meta")
    def meta(_: None = Depends(require_auth)) -> dict:
        return {
            "users": list(settings.users),
            "default_model": settings.default_model,
            "default_voice": settings.default_voice,
            "models": public_catalog(),
            "has_key": bool(settings.openrouter_api_key),
            "publish_target": bool(settings.publish_target),
            "jellyfin_url": bool(settings.jellyfin_url),
            "library_dir": str(settings.library_dir),
        }

    @app.post("/api/preview")
    async def preview(
        file: UploadFile = File(...),
        model: str = Form(""),
        _: None = Depends(require_auth),
    ) -> dict:
        model_id = model or settings.default_model
        get_model(model_id)
        stored = _save_upload(settings, file)
        try:
            data = preview_book(stored, model_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        data["stored_as"] = stored.name
        return data

    @app.post("/api/jobs")
    async def enqueue(
        file: UploadFile = File(...),
        who: str = Form(""),
        model: str = Form(""),
        voice: str = Form(""),
        _: None = Depends(require_auth),
    ) -> dict:
        if not settings.openrouter_api_key:
            raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY is not set")
        model_id = model or settings.default_model
        spec = get_model(model_id)
        try:
            chosen_voice = resolve_voice(spec, voice or settings.default_voice)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        importer = (who or settings.users[0]).strip() or settings.users[0]
        stored = _save_upload(settings, file)
        try:
            preview = preview_book(stored, model_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        job_id = create_job(
            conn,
            importer=importer,
            source_path=str(stored),
            source_name=file.filename or stored.name,
            author=preview["author"],
            title=preview["title"],
            model=model_id,
            voice=chosen_voice,
            chars=preview["chars"],
            estimated_usd=preview["estimated_usd"],
            chapter_count=preview["chapter_count"],
            chunk_total=preview["chunk_total"],
            warning=preview.get("warning") or "",
        )
        return get_job(conn, job_id) or {"id": job_id}

    @app.get("/api/jobs")
    def jobs(_: None = Depends(require_auth)) -> dict:
        return {"jobs": list_jobs(conn)}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: int, _: None = Depends(require_auth)) -> dict:
        found = get_job(conn, job_id)
        if not found:
            raise HTTPException(status_code=404, detail="job not found")
        return found

    @app.post("/api/jobs/{job_id}/retry")
    def retry(job_id: int, _: None = Depends(require_auth)) -> dict:
        found = get_job(conn, job_id)
        if not found:
            raise HTTPException(status_code=404, detail="job not found")
        update_job(conn, job_id, status="queued", error="")
        return get_job(conn, job_id) or found

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


def _save_upload(settings: Settings, file: UploadFile) -> Path:
    name = Path(file.filename or "book").name
    if not name.lower().endswith((".epub", ".pdf")):
        raise HTTPException(status_code=400, detail="Upload an EPUB or PDF")
    dest = settings.inbox_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return dest


def _worker(settings: Settings) -> None:
    conn = connect(settings.db_path)
    while True:
        job = next_queued(conn)
        if not job:
            time.sleep(1.5)
            continue
        with _worker_lock:
            try:
                run_job(conn, settings, int(job["id"]))
            except Exception:
                time.sleep(2)


def serve() -> None:
    import uvicorn

    settings = load_settings()
    settings.ensure_dirs()
    thread = threading.Thread(target=_worker, args=(settings,), daemon=True)
    thread.start()
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
