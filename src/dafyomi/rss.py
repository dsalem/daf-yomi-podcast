"""Build a Spotify/Apple-compatible podcast RSS feed from the DB.

Namespaces:
  itunes  — http://www.itunes.com/dtds/podcast-1.0.dtd
  content — http://purl.org/rss/1.0/modules/content/
  atom    — http://www.w3.org/2005/Atom
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, ElementTree, SubElement

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Episode, Season
from .show_config import SHOW

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS = "http://www.w3.org/2005/Atom"

# Register stable prefixes so ElementTree emits xmlns:itunes / xmlns:atom
# instead of auto-generating ns0/ns1 aliases.
import xml.etree.ElementTree as _ET

_ET.register_namespace("itunes", ITUNES_NS)
_ET.register_namespace("content", CONTENT_NS)
_ET.register_namespace("atom", ATOM_NS)


def _rfc2822(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _itunes(parent: Element, tag: str, text: str | None = None, **attrs: str) -> Element:
    el = SubElement(parent, f"{{{ITUNES_NS}}}{tag}")
    if text is not None:
        el.text = text
    for k, v in attrs.items():
        el.set(k, v)
    return el


def build_feed(session: Session, feed_base_url: str, cover_art_url: str) -> bytes:
    rss = Element("rss", attrib={"version": "2.0"})
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = SHOW.title
    SubElement(channel, "link").text = feed_base_url
    SubElement(channel, "language").text = SHOW.language
    SubElement(channel, "description").text = SHOW.description
    SubElement(channel, "copyright").text = SHOW.copyright
    SubElement(channel, "generator").text = "dafyomi (custom static feed)"
    SubElement(channel, "lastBuildDate").text = _rfc2822(datetime.now(timezone.utc))

    self_link = SubElement(channel, f"{{{ATOM_NS}}}link")
    self_link.set("href", f"{feed_base_url.rstrip('/')}/feed.xml")
    self_link.set("rel", "self")
    self_link.set("type", "application/rss+xml")

    _itunes(channel, "author", SHOW.author)
    _itunes(channel, "summary", SHOW.description)
    _itunes(channel, "type", SHOW.type)
    _itunes(channel, "explicit", "false" if not SHOW.explicit else "true")
    _itunes(channel, "image", href=cover_art_url)

    owner = _itunes(channel, "owner")
    _itunes(owner, "name", SHOW.author)
    _itunes(owner, "email", SHOW.email)

    # Apple/Spotify expect the category name in the `text=` attribute only —
    # not in the element's inner content.
    cat = _itunes(channel, "category")
    cat.set("text", SHOW.category_main)
    sub = _itunes(cat, "category")
    sub.set("text", SHOW.category_sub)

    image = SubElement(channel, "image")
    SubElement(image, "url").text = cover_art_url
    SubElement(image, "title").text = SHOW.title
    SubElement(image, "link").text = feed_base_url

    # Episodes — only those that are uploaded to IA (have an ia_url).
    eps = session.scalars(
        select(Episode)
        .join(Season, Episode.season_id == Season.id)
        .where(Episode.ia_url.is_not(None))
        .order_by(Season.season_number, Episode.daf_number)
    ).all()

    for ep in eps:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = ep.title_en
        SubElement(item, "link").text = ep.ia_url
        SubElement(item, "guid", attrib={"isPermaLink": "false"}).text = (
            ep.ia_identifier or ep.ia_url
        )
        SubElement(item, "description").text = ep.description or ""

        if ep.recorded_at:
            SubElement(item, "pubDate").text = _rfc2822(ep.recorded_at)
        elif ep.ia_uploaded_at:
            SubElement(item, "pubDate").text = _rfc2822(ep.ia_uploaded_at)

        size = ep.file_size_bytes or 0
        if ep.normalized_path:
            try:
                size = Path(ep.normalized_path).stat().st_size
            except OSError:
                pass
        SubElement(item, "enclosure", attrib={
            "url": ep.ia_url or "",
            "length": str(size),
            "type": "audio/mpeg",
        })

        _itunes(item, "title", ep.title_en)
        _itunes(item, "subtitle", ep.title_he)
        _itunes(item, "summary", ep.description or "")
        _itunes(item, "author", SHOW.author)
        _itunes(item, "explicit", "false")
        _itunes(item, "season", str(ep.season.season_number))
        _itunes(item, "episode", str(ep.daf_number))
        _itunes(item, "episodeType", "full")
        if ep.duration_seconds:
            _itunes(item, "duration", str(ep.duration_seconds))
        _itunes(item, "image", href=cover_art_url)

    tree = ElementTree(rss)
    from io import BytesIO

    buf = BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue()


def write_feed(session: Session, out_path: Path) -> Path:
    feed_base_url = os.environ.get("FEED_BASE_URL", "https://example.com")
    cover_art_url = os.environ.get("COVER_ART_URL", "https://example.com/cover.jpg")
    xml_bytes = build_feed(session, feed_base_url, cover_art_url)
    out_path.write_bytes(xml_bytes)
    return out_path
