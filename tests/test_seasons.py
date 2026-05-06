"""Sanity-check the canonical Bavli order and the fuzzy folder-name matcher."""

from __future__ import annotations

import pytest

from dafyomi.seasons import MASECHTOT, lookup, by_season_number


def test_31_masechtot_in_canonical_order() -> None:
    assert len(MASECHTOT) == 31
    assert MASECHTOT[0].name_en == "Berachot"
    assert MASECHTOT[0].season_number == 1
    assert MASECHTOT[-1].name_en == "Chullin"
    assert MASECHTOT[-1].season_number == 31


def test_season_numbers_unique_and_sequential() -> None:
    nums = [m.season_number for m in MASECHTOT]
    assert nums == list(range(1, 32))


def test_slugs_unique() -> None:
    slugs = [m.slug for m in MASECHTOT]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize(
    "raw,expected_slug",
    [
        ("Berachot",       "berachot"),
        ("berachot",       "berachot"),
        ("Brachos",        "berachot"),
        ("Berakhot",       "berachot"),
        ("Avodah Zara",    "avodah-zarah"),
        ("Avodah Zarah",   "avodah-zarah"),
        ("avoda-zara",     "avodah-zarah"),
        ("Makot",          "makkot"),
        ("Makkot",         "makkot"),
        ("Bava Kamma",     "bava-kamma"),
        ("Baba Kamma",     "bava-kamma"),
        ("BK",             "bava-kamma"),
        ("Rosh Hashana",   "rosh-hashanah"),
        ("Rosh-Hashanah",  "rosh-hashanah"),
        ("Moed Katan",     "moed-katan"),
        ("Moed-Kattan",    "moed-katan"),
        ("Shabbos",        "shabbat"),
        ("Sukkos",         "sukkah"),
    ],
)
def test_lookup_handles_common_variants(raw: str, expected_slug: str) -> None:
    m = lookup(raw)
    assert m is not None, f"failed to match: {raw!r}"
    assert m.slug == expected_slug


def test_lookup_returns_none_for_garbage() -> None:
    assert lookup("not a masechet") is None
    assert lookup("xyz123") is None


def test_by_season_number() -> None:
    assert by_season_number(1).name_en == "Berachot"
    assert by_season_number(27).name_en == "Avodah Zarah"
    assert by_season_number(31).name_en == "Chullin"
