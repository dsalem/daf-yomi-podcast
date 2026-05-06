"""Filename + folder parsing, plus end-to-end scan into a temp DB."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from dafyomi.db import init_schema, make_engine, make_session_factory
from dafyomi.models import Episode
from dafyomi.scan import parse_audio_path, scan_into_db


def _touch(p: Path, content: bytes = b"") -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


@pytest.mark.parametrize(
    "rel_path,exp_masechet,exp_daf,exp_season",
    [
        ("Berachot/Berachot 2.m4a",         "Berachot",     2,   1),
        ("Berachot/Berachot 47.m4a",        "Berachot",     47,  1),
        ("Avodah Zara/Avodah Zara 11.m4a",  "Avodah Zarah", 11,  27),
        ("Makot/Makot 7.m4a",               "Makkot",       7,   25),
        ("Bava Batra/Bava Batra 176.m4a",   "Bava Batra",   176, 23),
    ],
)
def test_parse_audio_path(
    tmp_path: Path, rel_path: str, exp_masechet: str, exp_daf: int, exp_season: int
) -> None:
    audio = _touch(tmp_path / rel_path)
    parsed = parse_audio_path(audio)
    assert parsed is not None
    assert parsed.masechet_en == exp_masechet
    assert parsed.daf == exp_daf
    assert parsed.season_number == exp_season


def test_parse_audio_path_unknown_folder(tmp_path: Path) -> None:
    audio = _touch(tmp_path / "Garbage Folder/Garbage Folder 7.m4a")
    assert parse_audio_path(audio) is None


@pytest.mark.parametrize(
    "rel_path,exp_daf,exp_amud,exp_daf_end,exp_amud_end",
    [
        # Single-amud variants (the 3 simple a/b cases in the user's catalog).
        ("Hagiga/Hagiga 24 a.m4a",            24, "a", None, None),
        ("Moed Kattan/Moed Kattan 12a.m4a",   12, "a", None, None),
        ("Yoma/Yoma 36b.m4a",                 36, "b", None, None),
        # Combined-day variants (4 files).
        ("Shabbat/Shabbat 36b37.m4a",         36, "b", 37,   None),
        ("Shabbat/Shabbat 40 41a.m4a",        40, None, 41,  "a"),
        ("Eruvin/Eruvin 40 41a.m4a",          40, None, 41,  "a"),
        ("Yoma/Yoma 35 36..m4a",              35, None, 36,  None),
        # Plain daf still parses identically.
        ("Berachot/Berachot 47.m4a",          47, None, None, None),
    ],
)
def test_parse_amud_and_combined(
    tmp_path: Path,
    rel_path: str,
    exp_daf: int,
    exp_amud: str | None,
    exp_daf_end: int | None,
    exp_amud_end: str | None,
) -> None:
    audio = _touch(tmp_path / rel_path)
    parsed = parse_audio_path(audio)
    assert parsed is not None, f"failed to parse: {rel_path}"
    assert parsed.daf == exp_daf
    assert parsed.amud == exp_amud
    assert parsed.daf_end == exp_daf_end
    assert parsed.amud_end == exp_amud_end


def test_scan_titles_include_amud_and_range(tmp_path: Path) -> None:
    drive = tmp_path / "drive"
    _touch(drive / "Yoma" / "Yoma 36b.m4a")
    _touch(drive / "Shabbat" / "Shabbat 36b37.m4a")
    _touch(drive / "Eruvin" / "Eruvin 40 41a.m4a")

    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_schema(engine)
    session = make_session_factory(engine)()

    scan_into_db(drive, session)
    eps = {e.title_en: e for e in session.scalars(select(Episode)).all()}

    assert "Yoma 36b" in eps
    assert eps["Yoma 36b"].title_he == "יומא לו ע״ב"
    assert eps["Yoma 36b"].amud == "b"

    assert "Shabbat 36b-37" in eps
    assert eps["Shabbat 36b-37"].title_he == "שבת לו ע״ב – לז"
    assert eps["Shabbat 36b-37"].daf_number == 36
    assert eps["Shabbat 36b-37"].daf_end == 37

    assert "Eruvin 40-41a" in eps
    assert eps["Eruvin 40-41a"].amud_end == "a"


def test_scan_is_idempotent_and_reads_meta(tmp_path: Path) -> None:
    # Layout
    drive = tmp_path / "drive"
    _touch(drive / "Berachot" / "Berachot 2.m4a")
    _touch(drive / "Berachot" / "Berachot 3.m4a")
    _touch(drive / "Berachot" / "Berachot 2.meta.txt", b"Custom blurb for Berachot 2.")
    _touch(drive / "Avodah Zara" / "Avodah Zara 11.m4a")
    # File the parser should reject (no daf number).
    _touch(drive / "Berachot" / "intro.m4a")

    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    init_schema(engine)
    session = make_session_factory(engine)()

    report1 = scan_into_db(drive, session)
    assert report1.added == 3
    assert report1.already_present == 0

    eps = session.scalars(select(Episode).order_by(Episode.id)).all()
    titles_en = {e.title_en for e in eps}
    assert {"Berachot 2", "Berachot 3", "Avodah Zarah 11"} == titles_en

    # Hebrew titles use gematria (with daf-yomi conventions).
    by_en = {e.title_en: e for e in eps}
    assert by_en["Berachot 2"].title_he == "ברכות ב"
    assert by_en["Avodah Zarah 11"].title_he == "עבודה זרה יא"

    # .meta.txt is picked up.
    assert by_en["Berachot 2"].description == "Custom blurb for Berachot 2."
    # Fallback description for files without .meta.txt.
    assert "Berachot 3" in by_en["Berachot 3"].description

    # Idempotent: rerun adds nothing.
    report2 = scan_into_db(drive, session)
    assert report2.added == 0
    assert report2.already_present == 3
