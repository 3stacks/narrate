from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from narrate.voices import DEFAULT_MODEL, DEFAULT_VOICE

ROOT = Path(__file__).resolve().parents[2]


def _load_env() -> None:
    load_dotenv(ROOT / ".env")
    data = os.environ.get("NARRATE_DATA_DIR")
    if data:
        load_dotenv(Path(data) / ".env", override=False)


_load_env()


def _path(value: str, default: Path) -> Path:
    raw = os.environ.get(value)
    if not raw:
        return default
    path = Path(raw).expanduser()
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    users: tuple[str, ...]
    data_dir: Path
    library_dir: Path
    publish_target: str
    jellyfin_url: str
    jellyfin_api_key: str
    jellyfin_container_path: str
    host: str
    port: int
    basic_auth: str
    default_model: str
    default_voice: str

    @property
    def db_path(self) -> Path:
        return self.data_dir / "narrate.db"

    @property
    def inbox_dir(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.library_dir, self.inbox_dir, self.jobs_dir):
            path.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    data_dir = _path("NARRATE_DATA_DIR", ROOT / "data")
    users = tuple(
        name.strip()
        for name in os.environ.get("NARRATE_USERS", "me").split(",")
        if name.strip()
    ) or ("me",)
    rsync_target = (
        os.environ.get("JELLYFIN_RSYNC_TARGET")
        or os.environ.get("NARRATE_PUBLISH_TARGET")
        or ""
    ).strip()
    return Settings(
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        users=users,
        data_dir=data_dir,
        library_dir=_path("NARRATE_LIBRARY_DIR", data_dir / "library"),
        publish_target=rsync_target,
        jellyfin_url=os.environ.get("JELLYFIN_URL", "").strip(),
        jellyfin_api_key=os.environ.get("JELLYFIN_API_KEY", "").strip(),
        jellyfin_container_path=os.environ.get(
            "JELLYFIN_CONTAINER_PATH", "/media/audiobooks"
        ).strip(),
        host=os.environ.get("NARRATE_HOST", "127.0.0.1"),
        port=int(os.environ.get("NARRATE_PORT", "3841")),
        basic_auth=os.environ.get("NARRATE_BASIC_AUTH", "").strip(),
        default_model=os.environ.get("NARRATE_DEFAULT_MODEL", DEFAULT_MODEL),
        default_voice=os.environ.get("NARRATE_DEFAULT_VOICE", DEFAULT_VOICE),
    )
