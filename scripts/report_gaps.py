"""One-off audit: per-masechet, list missing daf numbers vs the canonical end."""

from __future__ import annotations

from sqlalchemy import select

from dafyomi.db import init_schema, make_engine, make_session_factory
from dafyomi.models import Episode, Season

# Canonical last-daf number per masechet (Vilna Bavli pagination).
LAST_DAF: dict[str, int] = {
    "Berachot": 64,    "Shabbat": 157,   "Eruvin": 105,    "Pesachim": 121,
    "Shekalim": 22,    "Yoma": 88,       "Sukkah": 56,     "Beitzah": 40,
    "Rosh Hashanah": 35, "Taanit": 31,   "Megillah": 32,   "Moed Katan": 29,
    "Chagigah": 27,    "Yevamot": 122,   "Ketubot": 112,   "Nedarim": 91,
    "Nazir": 66,       "Sotah": 49,      "Gittin": 90,     "Kiddushin": 82,
    "Bava Kamma": 119, "Bava Metzia": 119, "Bava Batra": 176, "Sanhedrin": 113,
    "Makkot": 24,      "Shevuot": 49,    "Avodah Zarah": 76, "Horayot": 14,
    "Zevachim": 120,   "Menachot": 110,  "Chullin": 142,
}


def _format_runs(missing: list[int]) -> str:
    """Collapse a sorted list into runs: [3,4,5,8,9] -> '3-5, 8-9'."""
    if not missing:
        return "(none)"
    runs: list[str] = []
    start = prev = missing[0]
    for n in missing[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append(f"{start}" if start == prev else f"{start}-{prev}")
        start = prev = n
    runs.append(f"{start}" if start == prev else f"{start}-{prev}")
    return ", ".join(runs)


def main() -> None:
    engine = make_engine()
    init_schema(engine)
    session = make_session_factory(engine)()

    seasons = session.scalars(
        select(Season).order_by(Season.season_number)
    ).all()

    print(f"{'#':>2}  {'Masechet':<16} {'have':>4} / {'exp':>4}  {'range':>9}  missing")
    print("-" * 80)

    grand_have = grand_expected = 0

    for s in seasons:
        last = LAST_DAF.get(s.masechet_name_en)
        if last is None:
            continue
        expected = set(range(2, last + 1))
        have = sorted(
            r[0]
            for r in session.execute(
                select(Episode.daf_number).where(Episode.season_id == s.id)
            )
        )
        have_set = set(have)
        missing = sorted(expected - have_set)
        extras = sorted(have_set - expected)

        rng = f"{have[0]}-{have[-1]}" if have else "-"
        print(
            f"{s.season_number:>2}  {s.masechet_name_en:<16} "
            f"{len(have):>4} / {last - 1:>4}  {rng:>9}  {_format_runs(missing)}"
        )
        if extras:
            print(f"     [warn] {s.masechet_name_en} has daf above canonical end: {extras}")

        grand_have += len(have)
        grand_expected += last - 1

    print("-" * 80)
    print(f"     {'TOTAL':<16} {grand_have:>4} / {grand_expected:>4}")


if __name__ == "__main__":
    main()
