"""Validate the RSS XML structure against Spotify's iTunes-namespace requirements."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dafyomi.db import init_schema, make_engine, make_session_factory
from dafyomi.models import Episode, Season
from dafyomi.rss import build_feed

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
ATOM = "{http://www.w3.org/2005/Atom}"


@pytest.fixture()
def session_with_episode(tmp_path: Path):
    engine = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_schema(engine)
    session = make_session_factory(engine)()

    # Seasons are seeded by init_schema; pick Berachot (1).
    from sqlalchemy import select

    berachot = session.scalar(select(Season).where(Season.season_number == 1))
    assert berachot is not None

    ep = Episode(
        season_id=berachot.id,
        daf_number=47,
        original_filename="Berachot 47.m4a",
        original_path=str(tmp_path / "Berachot 47.m4a"),
        file_size_bytes=10_000_000,
        recorded_at=datetime(2025, 6, 20, 10, 37, 50, tzinfo=timezone.utc),
        normalized_path=str(tmp_path / "047.mp3"),
        normalized_at=datetime(2025, 6, 21, tzinfo=timezone.utc),
        duration_seconds=1800,
        ia_identifier="rabbi-joseph-salem-daf-yomi-berachot-047",
        ia_url="https://archive.org/download/rabbi-joseph-salem-daf-yomi-berachot-047/047.mp3",
        ia_uploaded_at=datetime(2025, 6, 22, tzinfo=timezone.utc),
        title_en="Berachot 47",
        title_he="ברכות מז",
        description="Daily Talmud shiur on Berachot 47.",
    )
    session.add(ep)
    session.commit()
    yield session


def test_feed_has_required_channel_metadata(session_with_episode) -> None:
    xml = build_feed(
        session_with_episode,
        feed_base_url="https://example.com/dy",
        cover_art_url="https://example.com/cover.jpg",
    )
    root = ET.fromstring(xml)
    assert root.tag == "rss"
    ch = root.find("channel")
    assert ch is not None

    assert ch.findtext("title") == "Daf Yomi"
    assert ch.findtext("language") == "en"
    assert ch.find(f"{ITUNES}author").text == "Rabbi Joseph Salem"
    assert ch.find(f"{ITUNES}type").text == "episodic"
    assert ch.find(f"{ITUNES}explicit").text == "false"

    owner = ch.find(f"{ITUNES}owner")
    assert owner is not None
    assert owner.find(f"{ITUNES}email").text == "joesalem7@aol.com"

    cat = ch.find(f"{ITUNES}category")
    assert cat is not None and cat.get("text") == "Religion & Spirituality"
    sub = cat.find(f"{ITUNES}category")
    assert sub is not None and sub.get("text") == "Judaism"
    # Per Apple/Spotify spec, category name lives ONLY in the `text=` attribute,
    # not in the element's inner text content.
    assert (cat.text or "").strip() == ""

    image = ch.find(f"{ITUNES}image")
    assert image is not None and image.get("href") == "https://example.com/cover.jpg"

    self_link = ch.find(f"{ATOM}link")
    assert self_link is not None
    assert self_link.get("rel") == "self"
    assert self_link.get("href").endswith("/feed.xml")


def test_episode_has_required_itunes_fields(session_with_episode) -> None:
    xml = build_feed(
        session_with_episode,
        feed_base_url="https://example.com/dy",
        cover_art_url="https://example.com/cover.jpg",
    )
    root = ET.fromstring(xml)
    item = root.find("./channel/item")
    assert item is not None

    assert item.findtext("title") == "Berachot 47"
    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert enclosure.get("type") == "audio/mpeg"
    assert "rabbi-joseph-salem-daf-yomi-berachot-047" in enclosure.get("url")

    assert item.find(f"{ITUNES}subtitle").text == "ברכות מז"
    assert item.find(f"{ITUNES}season").text == "1"
    assert item.find(f"{ITUNES}episode").text == "47"
    assert item.find(f"{ITUNES}duration").text == "1800"
    assert item.find(f"{ITUNES}episodeType").text == "full"
    # pubDate present (RFC 2822-ish).
    assert "2025" in item.findtext("pubDate")


def test_unuploaded_episodes_are_excluded(tmp_path: Path) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 't.db'}")
    init_schema(engine)
    session = make_session_factory(engine)()

    from sqlalchemy import select

    berachot = session.scalar(select(Season).where(Season.season_number == 1))
    # Episode that has been scanned but not uploaded — must not appear in feed.
    ep = Episode(
        season_id=berachot.id,
        daf_number=2,
        original_filename="Berachot 2.m4a",
        original_path=str(tmp_path / "Berachot 2.m4a"),
        title_en="Berachot 2",
        title_he="ברכות ב",
        description="...",
    )
    session.add(ep)
    session.commit()

    xml = build_feed(session, "https://example.com", "https://example.com/c.jpg")
    root = ET.fromstring(xml)
    assert root.find("./channel/item") is None
