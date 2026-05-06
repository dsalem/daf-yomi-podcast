"""Internet Archive uploader. Wraps the `internetarchive` Python package."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Episode
from .show_config import SHOW


def ia_identifier(season_number: int, masechet_slug: str, daf: int) -> str:
    """Stable, predictable IA identifier for an episode.

    Format: 'rabbi-joseph-salem-daf-yomi-<slug>-<daf3>'
    e.g. 'rabbi-joseph-salem-daf-yomi-berachot-047'
    """
    return f"rabbi-joseph-salem-daf-yomi-{masechet_slug}-{daf:03d}"


def ia_audio_url(identifier: str, filename: str) -> str:
    """Direct-download URL of a file inside an IA item."""
    return f"https://archive.org/download/{identifier}/{filename}"


def _make_metadata(ep: Episode) -> dict:
    """Build the IA item metadata dict for one episode."""
    return {
        "title": f"{ep.title_en} — Daf Yomi shiur by {SHOW.author}",
        "creator": SHOW.author,
        "description": ep.description or "",
        "subject": ["daf yomi", "talmud", "judaism", ep.season.masechet_name_en],
        "language": "eng",
        "mediatype": "audio",
        "collection": os.environ.get("IA_COLLECTION", "opensource_audio"),
        "date": (
            ep.recorded_at.date().isoformat()
            if ep.recorded_at
            else datetime.now(timezone.utc).date().isoformat()
        ),
    }


def upload_one(ep: Episode, dry_run: bool = False) -> tuple[str, str]:
    """Upload one normalized episode to IA. Returns (identifier, url).

    Raises if dry_run=False and the upload fails.
    """
    if not ep.normalized_path:
        raise RuntimeError(f"Episode {ep.id} has not been normalized yet.")

    identifier = ia_identifier(
        ep.season.season_number, ep.season.masechet_slug, ep.daf_number
    )
    src = Path(ep.normalized_path)
    remote_filename = src.name
    url = ia_audio_url(identifier, remote_filename)

    if dry_run:
        return identifier, url

    # Imported lazily so `--dry-run` works without IA credentials configured.
    from internetarchive import upload  # type: ignore

    access_key = os.environ.get("IA_ACCESS_KEY")
    secret_key = os.environ.get("IA_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError(
            "IA_ACCESS_KEY / IA_SECRET_KEY missing. Set them in .env "
            "(or run `ia configure`)."
        )

    metadata = _make_metadata(ep)
    responses = upload(
        identifier,
        files={remote_filename: str(src)},
        metadata=metadata,
        access_key=access_key,
        secret_key=secret_key,
        retries=3,
        retries_sleep=10,
    )
    for r in responses:
        # Each response is a requests.Response. Non-2xx → raise.
        if not getattr(r, "ok", True):
            raise RuntimeError(
                f"IA upload for {identifier} failed: HTTP {r.status_code} {r.text[:200]}"
            )
    return identifier, url


def upload_pending(
    session: Session, limit: int | None = None, dry_run: bool = False
) -> int:
    q = (
        select(Episode)
        .where(Episode.normalized_at.is_not(None))
        .where(Episode.ia_uploaded_at.is_(None))
        .order_by(Episode.season_id, Episode.daf_number)
    )
    if limit is not None:
        q = q.limit(limit)

    count = 0
    for ep in session.scalars(q).all():
        identifier, url = upload_one(ep, dry_run=dry_run)
        if dry_run:
            print(f"[dry-run] would upload {ep.title_en} -> {url}")
        else:
            ep.ia_identifier = identifier
            ep.ia_url = url
            ep.ia_uploaded_at = datetime.now(timezone.utc)
            session.add(ep)
            session.commit()
        count += 1
    return count
