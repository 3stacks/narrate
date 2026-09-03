import os
from pathlib import Path

from narrate.config import load_settings


def test_jellyfin_env_drop_in(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("NARRATE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("JELLYFIN_RSYNC_TARGET", "media-server:/data/media/audiobooks")
    monkeypatch.setenv("JELLYFIN_CONTAINER_PATH", "/media/audiobooks")
    monkeypatch.setenv("JELLYFIN_URL", "http://media-server:8096")
    monkeypatch.setenv("JELLYFIN_API_KEY", "secret")
    monkeypatch.delenv("NARRATE_PUBLISH_TARGET", raising=False)
    settings = load_settings()
    assert settings.publish_target == "media-server:/data/media/audiobooks"
    assert settings.jellyfin_container_path == "/media/audiobooks"
    assert settings.jellyfin_url == "http://media-server:8096"
    assert settings.jellyfin_api_key == "secret"


def test_local_mini_env(monkeypatch, tmp_path: Path):
    media = tmp_path / "media" / "audiobooks"
    monkeypatch.setenv("NARRATE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("NARRATE_LIBRARY_DIR", str(media))
    monkeypatch.setenv("JELLYFIN_RSYNC_TARGET", "")
    monkeypatch.setenv("NARRATE_PUBLISH_TARGET", "")
    monkeypatch.setenv("JELLYFIN_URL", "http://127.0.0.1:8096")
    monkeypatch.setenv("NARRATE_HOST", "0.0.0.0")
    settings = load_settings()
    assert settings.library_dir == media.resolve()
    assert settings.publish_target == ""
    assert settings.jellyfin_url == "http://127.0.0.1:8096"
    assert settings.host == "0.0.0.0"
