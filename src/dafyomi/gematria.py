"""Hebrew numeral conversion with daf-yomi conventions.

Special cases the daf-yomi tradition observes when forming numbers:
  - 15 is written טו (9 + 6), NOT יה (10 + 5), to avoid spelling part of a divine name.
  - 16 is written טז (9 + 7), NOT יו (10 + 6), for the same reason.
The same substitution applies in the tens-and-ones portion of any larger number
(e.g. 115 = קטו, 215 = רטו).
"""

from __future__ import annotations

_HUNDREDS = {1: "ק", 2: "ר", 3: "ש", 4: "ת"}
_TENS = {
    1: "י", 2: "כ", 3: "ל", 4: "מ", 5: "נ",
    6: "ס", 7: "ע", 8: "פ", 9: "צ",
}
_ONES = {
    1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה",
    6: "ו", 7: "ז", 8: "ח", 9: "ט",
}


def to_hebrew_numeral(n: int) -> str:
    """Convert a positive integer (1..999) to its Hebrew-numeral form.

    Uses daf-yomi conventions: 15 → טו, 16 → טז (and the same in the trailing
    two digits of larger numbers, e.g. 115 → קטו).
    """
    if not isinstance(n, int) or n < 1 or n > 999:
        raise ValueError(f"Hebrew numeral out of range (1..999): {n}")

    out: list[str] = []

    hundreds = n // 100
    while hundreds > 0:
        if hundreds >= 4:
            out.append("ת")
            hundreds -= 4
        else:
            out.append(_HUNDREDS[hundreds])
            hundreds = 0

    rem = n % 100
    if rem == 15:
        out.append("טו")
    elif rem == 16:
        out.append("טז")
    else:
        t = rem // 10
        o = rem % 10
        if t > 0:
            out.append(_TENS[t])
        if o > 0:
            out.append(_ONES[o])

    return "".join(out)


def daf_subtitle(masechet_he: str, daf: int) -> str:
    """Format the iTunes:subtitle for an episode, e.g. 'ברכות מז'."""
    return f"{masechet_he} {to_hebrew_numeral(daf)}"


# Hebrew amud markers. עמוד א = first amud, עמוד ב = second amud.
_AMUD_HE = {"a": "ע״א", "b": "ע״ב"}


def daf_label_en(
    daf: int,
    amud: str | None = None,
    daf_end: int | None = None,
    amud_end: str | None = None,
) -> str:
    """e.g. '47', '24a', '36b', '36b-37', '40-41a', '35-36'."""
    s = f"{daf}{amud or ''}"
    if daf_end is None:
        return s
    return f"{s}-{daf_end}{amud_end or ''}"


def daf_label_he(
    daf: int,
    amud: str | None = None,
    daf_end: int | None = None,
    amud_end: str | None = None,
) -> str:
    """Hebrew equivalent: e.g. 'מז', 'כד ע״א', 'לו ע״ב – לז'."""
    s = to_hebrew_numeral(daf)
    if amud:
        s = f"{s} {_AMUD_HE[amud]}"
    if daf_end is None:
        return s
    end = to_hebrew_numeral(daf_end)
    if amud_end:
        end = f"{end} {_AMUD_HE[amud_end]}"
    return f"{s} – {end}"
