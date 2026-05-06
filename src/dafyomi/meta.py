"""Per-episode .meta.txt reader and fallback description generator."""

from __future__ import annotations

from pathlib import Path


def read_meta(audio_path: Path) -> str | None:
    """If a sibling `.meta.txt` exists for the audio file, return its contents.

    Convention: for `Berachot 47.m4a`, look for `Berachot 47.meta.txt` next to it.
    Returns None if no meta file is present.
    """
    meta = audio_path.with_suffix(".meta.txt")
    if meta.exists() and meta.is_file():
        try:
            return meta.read_text(encoding="utf-8").strip() or None
        except UnicodeDecodeError:
            return meta.read_text(encoding="utf-8", errors="replace").strip() or None
    return None


def default_description(masechet_en: str, daf_label: str) -> str:
    """Boilerplate description used when no .meta.txt is present.

    `daf_label` is the formatted English daf string ('47', '24a', '36b-37'…).
    """
    return (
        f"Daily Talmud shiur on {masechet_en} {daf_label}, explained in English "
        f"with Rashi commentary, Sephardic reading."
    )


def description_for(audio_path: Path, masechet_en: str, daf_label: str) -> str:
    return read_meta(audio_path) or default_description(masechet_en, daf_label)
