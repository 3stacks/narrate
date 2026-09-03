from fastapi.testclient import TestClient

from narrate.config import Settings
from narrate.server import create_app
from narrate.voices import DEFAULT_MODEL, DEFAULT_VOICE


def test_meta_endpoint(tmp_path):
    settings = Settings(
        openrouter_api_key="",
        users=("Sam", "Alex"),
        data_dir=tmp_path,
        library_dir=tmp_path / "library",
        publish_target="",
        jellyfin_url="",
        jellyfin_api_key="",
        jellyfin_container_path="/media/audiobooks",
        host="127.0.0.1",
        port=3841,
        basic_auth="",
        default_model=DEFAULT_MODEL,
        default_voice=DEFAULT_VOICE,
    )
    client = TestClient(create_app(settings))
    meta = client.get("/api/meta").json()
    assert meta["users"] == ["Sam", "Alex"]
    assert meta["has_key"] is False
    assert meta["models"][0]["id"] == DEFAULT_MODEL
    page = client.get("/")
    assert page.status_code == 200
    assert "narrate" in page.text
