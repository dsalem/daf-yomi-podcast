"""SQLAlchemy 2.x ORM models. Mirror migrations/0001_init.sql exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Season(Base):
    __tablename__ = "seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    masechet_slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    masechet_name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    masechet_name_he: Mapped[str] = mapped_column(String(128), nullable=False)
    season_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
    )


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (UniqueConstraint("season_id", "daf_number", name="uq_season_daf"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    daf_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'a' / 'b' / NULL (NULL = full daf). For combined-day recordings, daf_end
    # and amud_end describe the upper bound of the range.
    amud: Mapped[Optional[str]] = mapped_column(String(1))
    daf_end: Mapped[Optional[int]] = mapped_column(Integer)
    amud_end: Mapped[Optional[str]] = mapped_column(String(1))

    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    original_path: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    normalized_path: Mapped[Optional[str]] = mapped_column(String(2048))
    normalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    ia_identifier: Mapped[Optional[str]] = mapped_column(String(256))
    ia_url: Mapped[Optional[str]] = mapped_column(String(2048))
    ia_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    description: Mapped[Optional[str]] = mapped_column(Text)
    title_en: Mapped[str] = mapped_column(String(256), nullable=False)
    title_he: Mapped[str] = mapped_column(String(256), nullable=False)

    season: Mapped[Season] = relationship(back_populates="episodes")


class KvState(Base):
    __tablename__ = "kv_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
