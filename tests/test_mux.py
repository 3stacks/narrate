import shutil
import subprocess
from pathlib import Path

import pytest

from narrate.mux import duration_seconds, write_m4b


def _silence(path: Path, seconds: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            str(seconds),
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            str(path),
        ],
        check=True,
    )


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_write_m4b_with_chapters(tmp_path: Path):
    one = tmp_path / "one.m4a"
    two = tmp_path / "two.m4a"
    _silence(one, 0.4)
    _silence(two, 0.6)
    dest = tmp_path / "book.m4b"
    write_m4b(
        chapters=[("One", one), ("Two", two)],
        dest=dest,
        title="River Book",
        author="Edith Wren",
    )
    assert dest.exists()
    assert dest.stat().st_size > 200
    assert duration_seconds(dest) == pytest.approx(1.0, abs=0.2)
