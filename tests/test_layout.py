from pathlib import Path
from unittest.mock import MagicMock, patch

from narrate.layout import (
    book_dir,
    deliver_to_jellyfin,
    install_book,
    is_remote_target,
    jellyfin_item_path,
    notify_jellyfin,
    publish_book,
    sanitize_name,
)


def test_sanitize_strips_slashes():
    assert sanitize_name('Foo / Bar: "Baz"') == "Foo Bar Baz"
    assert sanitize_name("   .") == "Untitled"


def test_install_book(tmp_path: Path):
    m4b = tmp_path / "in.m4b"
    m4b.write_bytes(b"fake")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"img")
    dest = install_book(
        library=tmp_path / "library",
        author="Edith Wren",
        title="River Book",
        m4b=m4b,
        cover=cover,
    )
    assert dest.name == "River Book.m4b"
    assert dest.exists()
    assert (dest.parent / "cover.jpg").exists()
    assert book_dir(tmp_path / "library", "Edith Wren", "River Book") == dest.parent


def test_jellyfin_item_path(tmp_path: Path):
    library = tmp_path / "library"
    installed = library / "Edith Wren" / "River Book" / "River Book.m4b"
    assert (
        jellyfin_item_path("/media/audiobooks", library, installed)
        == "/media/audiobooks/Edith Wren/River Book"
    )


def test_publish_book_rsyncs_author_title_folder(tmp_path: Path):
    library = tmp_path / "library"
    m4b = tmp_path / "in.m4b"
    m4b.write_bytes(b"fake")
    installed = install_book(
        library=library,
        author="Edith Wren",
        title="River Book",
        m4b=m4b,
        cover=None,
    )
    with patch("narrate.layout.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0, stderr="")
        dest = publish_book(
            library, installed, "media-server:/data/media/audiobooks"
        )
    assert dest == "media-server:/data/media/audiobooks/Edith Wren/River Book/"
    args = run.call_args[0][0]
    assert args[0] == "rsync"
    assert args[-1] == dest
    assert args[-2].endswith("Edith Wren/River Book/")


def test_is_remote_target():
    assert is_remote_target("media-server:/data/media/audiobooks")
    assert is_remote_target("user@media-server:media/audiobooks")
    assert not is_remote_target("/data/media/audiobooks")
    assert not is_remote_target("~/media/audiobooks")
    assert not is_remote_target("http://media-server:8096")
    assert not is_remote_target("")


def test_publish_book_local_copy_skips_ssh(tmp_path: Path):
    library = tmp_path / "library"
    dest_root = tmp_path / "media" / "audiobooks"
    m4b = tmp_path / "in.m4b"
    m4b.write_bytes(b"fake")
    installed = install_book(
        library=library,
        author="Edith Wren",
        title="River Book",
        m4b=m4b,
        cover=None,
    )
    with patch("narrate.layout.subprocess.run") as run:
        dest = publish_book(library, installed, str(dest_root))
    run.assert_not_called()
    copied = dest_root / "Edith Wren" / "River Book" / "River Book.m4b"
    assert Path(dest) == copied.parent
    assert copied.read_bytes() == b"fake"


def test_deliver_in_place_still_scans(tmp_path: Path):
    library = tmp_path / "media" / "audiobooks"
    m4b = tmp_path / "in.m4b"
    m4b.write_bytes(b"fake")
    installed = install_book(
        library=library,
        author="Edith Wren",
        title="River Book",
        m4b=m4b,
        cover=None,
    )
    with patch("narrate.layout.notify_jellyfin") as notify:
        note = deliver_to_jellyfin(
            library=library,
            installed=installed,
            publish_target=str(library),
            jellyfin_url="http://127.0.0.1:8096",
            jellyfin_api_key="secret",
            container_path="/media/audiobooks",
        )
    assert note["mode"] == "in-place"
    notify.assert_called_once()


def test_notify_jellyfin_posts_media_updated():
    with patch("narrate.layout.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.post.return_value = MagicMock(status_code=204, text="")
        notify_jellyfin(
            "http://media-server:8096",
            "secret",
            "/media/audiobooks/Edith Wren/River Book",
        )
        client.post.assert_called_once()
        url, kwargs = client.post.call_args[0][0], client.post.call_args[1]
        assert url == "http://media-server:8096/Library/Media/Updated"
        assert kwargs["headers"]["X-Emby-Token"] == "secret"
        assert kwargs["json"]["Updates"][0]["Path"] == (
            "/media/audiobooks/Edith Wren/River Book"
        )
