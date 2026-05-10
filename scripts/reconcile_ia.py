"""Reconcile DB upload state with IA reality.

When `dafyomi upload` hits a transient IA error mid-upload, the file may
actually have landed on IA even though our code raised. This script queries
IA's metadata API for every pending episode and, where the item exists with
a non-empty file list, marks the row as uploaded.

Safe to run anytime — idempotent and read-only on IA.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from dafyomi.db import init_schema, make_engine, make_session_factory
from dafyomi.ia import ia_audio_url, ia_identifier
from dafyomi.models import Episode


def _ia_exists(identifier: str) -> tuple[bool, list[str]]:
    """Return (exists, file_names). 'exists' = item with a non-empty mp3."""
    url = f"https://archive.org/metadata/{identifier}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
    except Exception as exc:
        print(f"  [warn] failed to query {identifier}: {exc}", file=sys.stderr)
        return False, []
    if not data.get("metadata"):
        return False, []
    files = [f.get("name", "") for f in data.get("files", [])]
    has_mp3 = any(name.endswith(".mp3") for name in files)
    return has_mp3, files


def main() -> int:
    engine = make_engine()
    init_schema(engine)
    session = make_session_factory(engine)()

    pending = session.scalars(
        select(Episode)
        .where(Episode.ia_uploaded_at.is_(None))
        .order_by(Episode.season_id, Episode.daf_number)
    ).all()

    print(f"Checking {len(pending)} pending episodes against IA...\n")

    fixed = 0
    truly_pending = 0
    for i, ep in enumerate(pending):
        season = ep.season
        identifier = ia_identifier(
            season.season_number, season.masechet_slug, ep.daf_number
        )
        exists, _files = _ia_exists(identifier)
        if exists:
            remote_filename = (
                Path(ep.normalized_path).name
                if ep.normalized_path
                else f"{ep.daf_number:03d}.mp3"
            )
            ep.ia_identifier = identifier
            ep.ia_url = ia_audio_url(identifier, remote_filename)
            ep.ia_uploaded_at = datetime.now(timezone.utc)
            session.add(ep)
            session.commit()
            fixed += 1
            print(f"  reconciled: {ep.title_en} -> {ep.ia_url}")
        else:
            truly_pending += 1
        # Be polite to IA's metadata endpoint.
        if i % 50 == 49:
            time.sleep(1)

    print(
        f"\nSummary: {fixed} reconciled, {truly_pending} truly pending "
        f"out of {len(pending)} checked"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
