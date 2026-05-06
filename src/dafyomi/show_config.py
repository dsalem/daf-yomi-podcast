"""Show-level metadata. Edit here to change the channel-level RSS values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShowConfig:
    title: str
    author: str
    description: str
    email: str
    language: str
    category_main: str
    category_sub: str
    explicit: bool
    copyright: str
    type: str  # 'episodic' or 'serial'


SHOW = ShowConfig(
    title="Daf Yomi",
    author="Rabbi Joseph Salem",
    description=(
        "Daf Yomi explained in English, text based, "
        "explanation based on Rashi, Sephardic reading."
    ),
    email="joesalem7@gmail.com",
    language="en",
    category_main="Religion & Spirituality",
    category_sub="Judaism",
    explicit=False,
    copyright="© Rabbi Joseph Salem",
    type="episodic",
)
