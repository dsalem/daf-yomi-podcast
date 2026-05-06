"""Print every episode that has an amud or daf_end set."""

from __future__ import annotations

import io
import sys

# Windows consoles default to cp1252; force UTF-8 so Hebrew prints cleanly.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from sqlalchemy import or_, select

from dafyomi.db import init_schema, make_engine, make_session_factory
from dafyomi.models import Episode


def main() -> None:
    engine = make_engine()
    init_schema(engine)
    session = make_session_factory(engine)()
    eps = session.scalars(
        select(Episode)
        .where(or_(Episode.amud.is_not(None), Episode.daf_end.is_not(None)))
        .order_by(Episode.id)
    ).all()
    for ep in eps:
        end = f"{ep.daf_end or ''}{ep.amud_end or ''}"
        print(
            f"  {ep.title_en:22}  he={ep.title_he:30}  "
            f"amud={ep.amud!s:5}  end={end:6}  file={ep.original_filename}"
        )


if __name__ == "__main__":
    main()
