from __future__ import annotations

import subprocess
from pathlib import Path


class MuxError(RuntimeError):
    pass


def concat_audio(inputs: list[Path], dest: Path, bitrate: str = "64k") -> None:
    if not inputs:
        raise MuxError("No audio inputs to concat")
    dest.parent.mkdir(parents=True, exist_ok=True)
    listing = dest.with_suffix(".concat.txt")
    listing.write_text(
        "".join(f"file '{path.resolve()}'\n" for path in inputs),
        encoding="utf-8",
    )
    _ffmpeg(
        [
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-ac",
            "1",
            "-ar",
            "24000",
            "-movflags",
            "+faststart",
            str(dest),
        ]
    )


def write_m4b(
    *,
    chapters: list[tuple[str, Path]],
    dest: Path,
    title: str,
    author: str,
    cover: Path | None = None,
) -> None:
    if not chapters:
        raise MuxError("No chapters to mux")
    dest.parent.mkdir(parents=True, exist_ok=True)
    work = dest.parent / "_book.m4a"
    concat_audio([path for _, path in chapters], work)

    metadata = dest.with_suffix(".ffmeta")
    metadata.write_text(
        _ffmetadata(title=title, author=author, chapters=chapters), encoding="utf-8"
    )

    cmd = ["-y", "-i", str(work)]
    if cover and cover.exists():
        cmd += ["-i", str(cover)]
    cmd += ["-i", str(metadata), "-map_metadata", "2" if cover and cover.exists() else "1"]
    cmd += ["-map", "0:a"]
    if cover and cover.exists():
        cmd += ["-map", "1:v", "-c:v", "mjpeg", "-disposition:v:0", "attached_pic"]
    cmd += [
        "-c:a",
        "copy",
        "-f",
        "mp4",
        str(dest),
    ]
    _ffmpeg(cmd)


def duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def _ffmetadata(
    *, title: str, author: str, chapters: list[tuple[str, Path]]
) -> str:
    lines = [
        ";FFMETADATA1",
        f"title={_escape(title)}",
        f"artist={_escape(author)}",
        f"album={_escape(title)}",
        "genre=Audiobook",
    ]
    cursor_ms = 0
    for name, path in chapters:
        length_ms = int(duration_seconds(path) * 1000)
        end = cursor_ms + max(length_ms, 1)
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={cursor_ms}",
            f"END={end}",
            f"title={_escape(name)}",
        ]
        cursor_ms = end
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#")


def _ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise MuxError(result.stderr.strip() or "ffmpeg failed")
