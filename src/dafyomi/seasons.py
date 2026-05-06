"""Canonical Bavli masechet order, with English and Hebrew names.

The season_number is the integer used in `<itunes:season>`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Masechet:
    season_number: int
    slug: str          # canonical lowercase slug, no punctuation
    name_en: str       # canonical English title
    name_he: str       # Hebrew name as it should appear in the subtitle


# Canonical Bavli order. Slugs are normalized (lowercase, alphanumeric+hyphen)
# and double as the lookup key for fuzzy folder-name matching.
MASECHTOT: tuple[Masechet, ...] = (
    Masechet(1,  "berachot",       "Berachot",       "ברכות"),
    Masechet(2,  "shabbat",        "Shabbat",        "שבת"),
    Masechet(3,  "eruvin",         "Eruvin",         "עירובין"),
    Masechet(4,  "pesachim",       "Pesachim",       "פסחים"),
    Masechet(5,  "shekalim",       "Shekalim",       "שקלים"),
    Masechet(6,  "yoma",           "Yoma",           "יומא"),
    Masechet(7,  "sukkah",         "Sukkah",         "סוכה"),
    Masechet(8,  "beitzah",        "Beitzah",        "ביצה"),
    Masechet(9,  "rosh-hashanah",  "Rosh Hashanah",  "ראש השנה"),
    Masechet(10, "taanit",         "Taanit",         "תענית"),
    Masechet(11, "megillah",       "Megillah",       "מגילה"),
    Masechet(12, "moed-katan",     "Moed Katan",     "מועד קטן"),
    Masechet(13, "chagigah",       "Chagigah",       "חגיגה"),
    Masechet(14, "yevamot",        "Yevamot",        "יבמות"),
    Masechet(15, "ketubot",        "Ketubot",        "כתובות"),
    Masechet(16, "nedarim",        "Nedarim",        "נדרים"),
    Masechet(17, "nazir",          "Nazir",          "נזיר"),
    Masechet(18, "sotah",          "Sotah",          "סוטה"),
    Masechet(19, "gittin",         "Gittin",         "גיטין"),
    Masechet(20, "kiddushin",      "Kiddushin",      "קידושין"),
    Masechet(21, "bava-kamma",     "Bava Kamma",     "בבא קמא"),
    Masechet(22, "bava-metzia",    "Bava Metzia",    "בבא מציעא"),
    Masechet(23, "bava-batra",     "Bava Batra",     "בבא בתרא"),
    Masechet(24, "sanhedrin",      "Sanhedrin",      "סנהדרין"),
    Masechet(25, "makkot",         "Makkot",         "מכות"),
    Masechet(26, "shevuot",        "Shevuot",        "שבועות"),
    Masechet(27, "avodah-zarah",   "Avodah Zarah",   "עבודה זרה"),
    Masechet(28, "horayot",        "Horayot",        "הוריות"),
    Masechet(29, "zevachim",       "Zevachim",       "זבחים"),
    Masechet(30, "menachot",       "Menachot",       "מנחות"),
    Masechet(31, "chullin",        "Chullin",        "חולין"),
)

# Common spelling variants users may have in their Drive folders.
# All values must be canonical slugs from MASECHTOT.
_ALIASES: dict[str, str] = {
    "brachos": "berachot",
    "brachot": "berachot",
    "berakhot": "berachot",
    "berakhos": "berachot",
    "berachos": "berachot",
    "shabbos": "shabbat",
    "shabbas": "shabbat",
    "eiruvin": "eruvin",
    "pesahim": "pesachim",
    "pesachin": "pesachim",
    "shkalim": "shekalim",
    "succah": "sukkah",
    "succos": "sukkah",
    "sukkos": "sukkah",
    "beitza": "beitzah",
    "beitsa": "beitzah",
    "beitsah": "beitzah",
    "betza": "beitzah",
    "rosh-hashana": "rosh-hashanah",
    "rosh-ha-shanah": "rosh-hashanah",
    "rosh-ha-shana": "rosh-hashanah",
    "rh": "rosh-hashanah",
    "taanis": "taanit",
    "tanit": "taanit",
    "megilla": "megillah",
    "megila": "megillah",
    "moed-kattan": "moed-katan",
    "moed-katon": "moed-katan",
    "chagiga": "chagigah",
    "hagigah": "chagigah",
    "hagiga": "chagigah",
    "yevamos": "yevamot",
    "yevamoth": "yevamot",
    "yebamot": "yevamot",
    "yebamos": "yevamot",
    "yebamoth": "yevamot",
    "kesubos": "ketubot",
    "kesubot": "ketubot",
    "ketubos": "ketubot",
    "ketuvot": "ketubot",
    "ketuvos": "ketubot",
    "kesuvos": "ketubot",
    "kesuvot": "ketubot",
    "sota": "sotah",
    "sotta": "sotah",
    "gitin": "gittin",
    "gittim": "gittin",
    "gettin": "gittin",
    "kidushin": "kiddushin",
    "kiddushim": "kiddushin",
    "baba-kamma": "bava-kamma",
    "bava-kama": "bava-kamma",
    "baba-kama": "bava-kamma",
    "bk": "bava-kamma",
    "baba-metzia": "bava-metzia",
    "bava-metsia": "bava-metzia",
    "bm": "bava-metzia",
    "baba-batra": "bava-batra",
    "bava-basra": "bava-batra",
    "baba-basra": "bava-batra",
    "bb": "bava-batra",
    "makot": "makkot",
    "makos": "makkot",
    "makkos": "makkot",
    "shavuot": "shevuot",
    "shavuos": "shevuot",
    "shevuos": "shevuot",
    "avoda-zara": "avodah-zarah",
    "avodah-zara": "avodah-zarah",
    "avoda-zarah": "avodah-zarah",
    "az": "avodah-zarah",
    "horayos": "horayot",
    "zvachim": "zevachim",
    "zevahim": "zevachim",
    "menachos": "menachot",
    "menahot": "menachot",
    "chulin": "chullin",
    "chullim": "chullin",
    "hullin": "chullin",
    "chullen": "chullin",
}


def _normalize(s: str) -> str:
    """Aggressively normalize: lowercase, ASCII fold, collapse separators to '-'."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


_BY_SLUG: dict[str, Masechet] = {m.slug: m for m in MASECHTOT}
_BY_NUMBER: dict[int, Masechet] = {m.season_number: m for m in MASECHTOT}


def lookup(name: str) -> Masechet | None:
    """Resolve any reasonable spelling of a masechet name to canonical metadata.

    Returns None if no match is found. Caller decides whether that's a warning
    or an error.
    """
    norm = _normalize(name)
    if norm in _BY_SLUG:
        return _BY_SLUG[norm]
    if norm in _ALIASES:
        return _BY_SLUG[_ALIASES[norm]]
    # Try stripping a leading "tractate" or "masechet" if present.
    stripped = re.sub(r"^(tractate|masechet|masechtas|masekhet)-", "", norm)
    if stripped != norm:
        if stripped in _BY_SLUG:
            return _BY_SLUG[stripped]
        if stripped in _ALIASES:
            return _BY_SLUG[_ALIASES[stripped]]
    return None


def by_season_number(n: int) -> Masechet:
    return _BY_NUMBER[n]


def all_masechtot() -> tuple[Masechet, ...]:
    return MASECHTOT
