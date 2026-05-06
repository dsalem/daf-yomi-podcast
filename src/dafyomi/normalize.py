"""ffmpeg loudnorm wrapper.

Single-pass loudnorm with Spotify-recommended targets (-16 LUFS integrated,
-1.5 dBTP true-peak, 11 LU range). Output: mono mp3 at 64 kbps.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import project_root
from .models import Episode

LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it (e.g. `winget install ffmpeg` "
            "on Windows, `brew install ffmpeg` on macOS) and try again."
        )
    return path


def normalize_one(src: Path, dst: Path, ffmpeg: str = "ffmpeg") -> None:
    """Run ffmpeg loudnorm src -> dst (mp3 mono 64k)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(src),
        "-af", LOUDNORM_FILTER,
        "-ac", "1",
        "-c:a", "libmp3lame",
        "-b:a", "64k",
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def ffprobe_duration(path: Path) -> int | None:
    """Return duration in whole seconds, or None on failure."""
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            text=True,
        )
        return int(float(out.strip()))
    except (subprocess.CalledProcessError, ValueError):
        return None


def normalize_pending(session: Session, limit: int | None = None) -> int:
    """Normalize episodes that have not yet been normalized.

    Output goes to `<project_root>/normalized/<masechet_slug>/<daf>.mp3`.
    Returns the number of episodes successfully processed.
    """
    ensure_ffmpeg()
    out_root = project_root() / "normalized"

    q = (
        select(Episode)
        .where(Episode.normalized_at.is_(None))
        .order_by(Episode.season_id, Episode.daf_number)
    )
    if limit is not None:
        q = q.limit(limit)

    processed = 0
    for ep in session.scalars(q).all():
        slug = ep.season.masechet_slug
        dst = out_root / slug / f"{ep.daf_number:03d}.mp3"
        src = Path(ep.original_path)

        if not src.exists():
            continue

        normalize_one(src, dst)
        ep.normalized_path = str(dst)
        ep.normalized_at = datetime.now(timezone.utc)
        ep.duration_seconds = ffprobe_duration(dst)
        session.add(ep)
        session.commit()
        processed += 1

    return processed
