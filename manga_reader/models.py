"""Small domain models used by Manga Reader."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TextRegion:
    """A rectangular page region and its editable OCR transcription."""

    x: int
    y: int
    width: int
    height: int
    text: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    source: str = "manual"  # "manual" or "auto"

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height
