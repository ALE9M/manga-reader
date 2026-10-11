"""Plain-text export helpers."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import TextRegion


def assemble_text(regions: Iterable[TextRegion]) -> str:
    """Join non-empty transcriptions in the supplied reading order."""
    paragraphs = [region.text.strip() for region in regions if region.text.strip()]
    return "\n\n".join(paragraphs)


def write_text_file(regions: Iterable[TextRegion], destination: str | Path) -> None:
    """Write ordered Japanese text as UTF-8 without adding extra metadata."""
    Path(destination).write_text(assemble_text(regions), encoding="utf-8", newline="\n")
