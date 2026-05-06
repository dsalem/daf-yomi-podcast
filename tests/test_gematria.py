"""Exhaustive tests for daf-yomi gematria. The 15/16 special cases are critical."""

from __future__ import annotations

import pytest

from dafyomi.gematria import to_hebrew_numeral


# Hand-verified canonical values.
@pytest.mark.parametrize(
    "n,expected",
    [
        (1,   "א"),
        (2,   "ב"),
        (5,   "ה"),
        (9,   "ט"),
        (10,  "י"),
        (11,  "יא"),
        (12,  "יב"),
        (13,  "יג"),
        (14,  "יד"),
        (15,  "טו"),     # critical: NOT יה
        (16,  "טז"),     # critical: NOT יו
        (17,  "יז"),
        (18,  "יח"),
        (19,  "יט"),
        (20,  "כ"),
        (21,  "כא"),
        (29,  "כט"),
        (30,  "ל"),
        (47,  "מז"),     # 'Berachot 47' subtitle example
        (50,  "נ"),
        (64,  "סד"),     # last daf of Berachot
        (99,  "צט"),
        (100, "ק"),
        (101, "קא"),
        (115, "קטו"),    # critical: 15 special-case applies inside hundreds too
        (116, "קטז"),    # critical: same for 16
        (120, "קכ"),
        (157, "קנז"),    # last daf of Sanhedrin
        (176, "קעו"),    # last daf of Bava Batra (longest masechet)
        (200, "ר"),
    ],
)
def test_known_values(n: int, expected: str) -> None:
    assert to_hebrew_numeral(n) == expected


def test_no_yod_he_or_yod_vav_anywhere_in_daf_range() -> None:
    """For every daf 2..200, the result must never contain יה or יו."""
    for n in range(2, 201):
        s = to_hebrew_numeral(n)
        assert "יה" not in s, f"{n} -> {s} contains יה"
        assert "יו" not in s, f"{n} -> {s} contains יו"


def test_all_results_are_unique_in_daf_range() -> None:
    seen: dict[str, int] = {}
    for n in range(1, 201):
        s = to_hebrew_numeral(n)
        assert s not in seen, f"collision: {n} and {seen[s]} both -> {s}"
        seen[s] = n


@pytest.mark.parametrize("bad", [0, -1, 1000, 5000])
def test_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError):
        to_hebrew_numeral(bad)


# Daf labels: English + Hebrew formatting for amud and combined-day cases.
from dafyomi.gematria import daf_label_en, daf_label_he


@pytest.mark.parametrize(
    "args,expected_en,expected_he",
    [
        # Plain daf.
        ((47, None, None, None),  "47",       "מז"),
        ((176, None, None, None), "176",      "קעו"),
        # Single amud.
        ((24, "a", None, None),   "24a",      "כד ע״א"),
        ((36, "b", None, None),   "36b",      "לו ע״ב"),
        ((12, "a", None, None),   "12a",      "יב ע״א"),
        # Combined daf, no amud.
        ((35, None, 36, None),    "35-36",    "לה – לו"),
        # Combined ending in partial amud.
        ((40, None, 41, "a"),     "40-41a",   "מ – מא ע״א"),
        # Combined starting at partial amud.
        ((36, "b", 37, None),     "36b-37",   "לו ע״ב – לז"),
    ],
)
def test_daf_labels(args, expected_en: str, expected_he: str) -> None:
    daf, amud, daf_end, amud_end = args
    assert daf_label_en(daf, amud, daf_end, amud_end) == expected_en
    assert daf_label_he(daf, amud, daf_end, amud_end) == expected_he
