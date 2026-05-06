"""Walk the local Drive mirror, parse filenames, populate the DB.

Filename convention: '<MasechetName> <DafNumber>.m4a'
  e.g. 'Berachot 2.m4a', 'Avodah Zara 11.m4a'.

Folder name → masechet (via fuzzy lookup in `seasons.lookup`).
The folder takes precedence over the filename's masechet portion when they
disagree (folder is the source of truth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import seasons
from .gematria import daf_label_en, daf_label_he
from .meta import description_for
from .models import Episode, Season

_AUDIO_EXTS = {".m4a", ".mp3", ".wav", ".aac"}

# Captures every variant in the user's catalog:
#   'Berachot 47'           -> daf=47
#   'Yoma 36b'              -> daf=36, amud='b'
#   'Hagiga 24 a'           -> daf=24, amud='a'
#   'Moed Kattan 12a'       -> daf=12, amud='a'
#   'Shabbat 36b37'         -> daf=36, amud='b', daf2=37
#   'Shabbat 40 41a'        -> daf=40, daf2=41, amud2='a'
#   'Yoma 35 36.'           -> daf=35, daf2=36 (trailing dot tolerated)
_FILENAME_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<daf>\d{1,3})\s*(?P<amud>[ab])?"
    r"(?:\s*(?P<daf2>\d{1,3})\s*(?P<amud2>[ab])?)?"
    r"\s*\.*\s*$"
)


@dataclass
class ScannedFile:
    path: Path
    masechet_en: str
    masechet_he: str
    season_number: int
    daf: int
    amud: str | None = None
    daf_end: int | None = None
    amud_end: str | None = None


@dataclass
class ScanReport:
    added: int = 0
    already_present: int = 0
    unmatched_folders: list[str] = None  # type: ignore[assignment]
    unparseable_files: list[str] = None  # type: ignore[assignment]
    misfiled: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.unmatched_folders is None:
            self.unmatched_folders = []
        if self.unparseable_files is None:
            self.unparseable_files = []
        if self.misfiled is None:
            self.misfiled = []


def parse_audio_path(path: Path) -> ScannedFile | None:
    """Resolve a single audio file path to (masechet, daf).

    Folder is the source of truth. If the filename's masechet portion
    disagrees with the folder, returns None — caller logs as misfiled.
    """
    folder = path.parent.name
    folder_m = seasons.lookup(folder)

    match = _FILENAME_RE.match(path.stem)
    if not match:
        return None
    daf = int(match.group("daf"))
    if daf < 2 or daf > 200:
        return None
    amud = match.group("amud")
    daf2_s = match.group("daf2")
    daf_end = int(daf2_s) if daf2_s else None
    if daf_end is not None and (daf_end < 2 or daf_end > 200 or daf_end <= daf):
        # Out of range or not actually a range — treat as single daf.
        daf_end = None
    amud_end = match.group("amud2") if daf_end is not None else None

    filename_m = seasons.lookup(match.group("name"))

    if folder_m is not None and filename_m is not None and folder_m.slug != filename_m.slug:
        # Misfiled: e.g. "Sanhedrin 3.m4a" sitting in the Baba Batra folder.
        return None

    m = folder_m or filename_m
    if m is None:
        return None

    return ScannedFile(
        path=path,
        masechet_en=m.name_en,
        masechet_he=m.name_he,
        season_number=m.season_number,
        daf=daf,
        amud=amud,
        daf_end=daf_end,
        amud_end=amud_end,
    )


def _read_recorded_at(path: Path) -> datetime | None:
    """Best-effort: pull `creation_time` from the m4a tag via mutagen."""
    try:
        from mutagen import File as MutagenFile  # type: ignore
    except ImportError:
        return None

    try:
        mf = MutagenFile(str(path))
    except Exception:
        return None
    if mf is None:
        return None

    candidates: list[str] = []
    tags = getattr(mf, "tags", None)
    if tags is not None:
        for key in ("\xa9day", "creation_time", "date", "TDRC"):
            try:
                v = tags.get(key)
            except Exception:
                v = None
            if v:
                candidates.append(str(v[0]) if isinstance(v, list) else str(v))

    for raw in candidates:
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def walk(folder: Path) -> list[Path]:
    """Yield every audio file under folder, deterministically sorted."""
    out: list[Path] = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in _AUDIO_EXTS:
            out.append(p)
    out.sort()
    return out


def scan_into_db(folder: Path, session: Session) -> ScanReport:
    """Populate `seasons` and `episodes` from a local folder. Idempotent.

    Existing rows (matched by `episodes.original_path`) are left alone.
    """
    report = ScanReport()
    season_by_number = {
        s.season_number: s
        for s in session.scalars(select(Season)).all()
    }
    seen_unmatched: set[str] = set()

    for audio_path in walk(folder):
        parsed = parse_audio_path(audio_path)
        if parsed is None:
            folder_name = audio_path.parent.name
            if seasons.lookup(folder_name) is None and folder_name not in seen_unmatched:
                seen_unmatched.add(folder_name)
                report.unmatched_folders.append(folder_name)
                continue
            # Folder is recognized but file didn't parse cleanly — could be
            # misfiled (filename's masechet disagrees with the folder) or just
            # unparseable.
            stem_match = _FILENAME_RE.match(audio_path.stem)
            if stem_match:
                fn_m = seasons.lookup(stem_match.group("name"))
                folder_m = seasons.lookup(folder_name)
                if fn_m is not None and folder_m is not None and fn_m.slug != folder_m.slug:
                    report.misfiled.append(str(audio_path))
                    continue
            report.unparseable_files.append(str(audio_path))
            continue

        season = season_by_number.get(parsed.season_number)
        if season is None:
            # The init-db step seeds seasons, but be defensive.
            m = seasons.by_season_number(parsed.season_number)
            season = Season(
                masechet_slug=m.slug,
                masechet_name_en=m.name_en,
                masechet_name_he=m.name_he,
                season_number=m.season_number,
            )
            session.add(season)
            session.flush()
            season_by_number[parsed.season_number] = season

        existing = session.scalar(
            select(Episode).where(Episode.original_path == str(audio_path))
        )
        if existing is not None:
            report.already_present += 1
            continue

        label_en = daf_label_en(parsed.daf, parsed.amud, parsed.daf_end, parsed.amud_end)
        label_he = daf_label_he(parsed.daf, parsed.amud, parsed.daf_end, parsed.amud_end)
        ep = Episode(
            season_id=season.id,
            daf_number=parsed.daf,
            amud=parsed.amud,
            daf_end=parsed.daf_end,
            amud_end=parsed.amud_end,
            original_filename=audio_path.name,
            original_path=str(audio_path),
            file_size_bytes=audio_path.stat().st_size,
            recorded_at=_read_recorded_at(audio_path),
            title_en=f"{parsed.masechet_en} {label_en}",
            title_he=f"{parsed.masechet_he} {label_he}",
            description=description_for(audio_path, parsed.masechet_en, label_en),
        )
        session.add(ep)
        report.added += 1

    session.commit()
    return report
