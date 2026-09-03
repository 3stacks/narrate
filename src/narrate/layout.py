from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import httpx

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_name(name: str) -> str:
    cleaned = _BAD.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or "Untitled"


def book_dir(library: Path, author: str, title: str) -> Path:
    return library / sanitize_name(author) / sanitize_name(title)


def install_book(
    *,
    library: Path,
    author: str,
    title: str,
    m4b: Path,
    cover: Path | None = None,
) -> Path:
    dest_dir = book_dir(library, author, title)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{sanitize_name(title)}.m4b"
    shutil.copy2(m4b, dest)
    if cover and cover.exists():
        suffix = cover.suffix.lower() if cover.suffix else ".jpg"
        if suffix not in {".jpg", ".jpeg", ".png"}:
            suffix = ".jpg"
        shutil.copy2(cover, dest_dir / f"cover{suffix if suffix != '.jpeg' else '.jpg'}")
    return dest


def is_remote_target(target: str) -> bool:
    """scp/rsync host:path, not a local path and not a URL."""
    if not target or "://" in target:
        return False
    host, sep, _rest = target.partition(":")
    if not sep:
        return False
    return bool(host) and "/" not in host and "\\" not in host


def publish_library(library: Path, target: str) -> None:
    if not target:
        return
    library.mkdir(parents=True, exist_ok=True)
    dest = target if target.endswith("/") else f"{target}/"
    _rsync(f"{library}/", dest)


def publish_book(library: Path, installed: Path, target: str) -> str:
    """Copy one Author/Title folder to the Jellyfin media mount. SSH only for host:path."""
    if not target:
        return ""
    book_folder = installed.parent
    rel = book_folder.relative_to(library)
    if is_remote_target(target):
        dest = f"{target.rstrip('/')}/{rel.as_posix()}/"
        _rsync(f"{book_folder}/", dest)
        return dest
    dest_dir = Path(target).expanduser().resolve() / rel
    if dest_dir == book_folder.resolve():
        return str(dest_dir)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(book_folder, dest_dir, dirs_exist_ok=True)
    return str(dest_dir)


def deliver_to_jellyfin(
    *,
    library: Path,
    installed: Path,
    publish_target: str,
    jellyfin_url: str,
    jellyfin_api_key: str,
    container_path: str,
) -> dict:
    """Place the book in Jellyfin's folder if needed, then ask it to scan.

    Remote `host:path` uses system rsync/ssh. A local path copies on disk.
    If the working library already is the Jellyfin folder, skip the copy.
    """
    note: dict = {"mode": "in-place"}
    if publish_target and not _same_library(library, publish_target):
        dest = publish_book(library, installed, publish_target)
        note = {
            "mode": "rsync" if is_remote_target(publish_target) else "local-copy",
            "dest": dest,
        }
    item_path = jellyfin_item_path(container_path, library, installed)
    note["container_path"] = item_path
    if jellyfin_url and jellyfin_api_key:
        notify_jellyfin(jellyfin_url, jellyfin_api_key, item_path)
        note["scanned"] = True
    return note


def _same_library(library: Path, target: str) -> bool:
    if is_remote_target(target):
        return False
    return Path(target).expanduser().resolve() == library.resolve()


def jellyfin_item_path(container_root: str, library: Path, installed: Path) -> str:
    rel = installed.parent.relative_to(library).as_posix()
    root = container_root.rstrip("/")
    return f"{root}/{rel}" if root else rel


def notify_jellyfin(url: str, api_key: str, item_path: str) -> None:
    if not url or not api_key:
        return
    base = url.rstrip("/")
    headers = {
        "X-Emby-Token": api_key,
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=20.0) as client:
        if item_path:
            response = client.post(
                f"{base}/Library/Media/Updated",
                headers=headers,
                json={"Updates": [{"Path": item_path, "UpdateType": "Created"}]},
            )
            if response.status_code >= 400:
                response = client.post(f"{base}/Library/Refresh", headers=headers)
        else:
            response = client.post(f"{base}/Library/Refresh", headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Jellyfin refresh {response.status_code}: {response.text[:300]}"
            )


def _rsync(source: str, dest: str) -> None:
    result = subprocess.run(
        ["rsync", "-a", "--partial", source, dest],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "rsync failed")
