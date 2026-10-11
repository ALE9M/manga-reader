"""Run model loading and comic text detection outside the GUI thread."""
from __future__ import annotations

from pathlib import Path
from PIL import Image
from PySide6.QtCore import QThread, Signal

from .detection import Box, detect_comic_text


class DetectionWorker(QThread):
    result_ready = Signal(list)  # list[tuple[x, y, width, height]]
    fatal_error = Signal(str)
    progress = Signal(str)

    def __init__(self, image: Image.Image, repository_dir: str | Path,
                 model_path: str | Path, parent=None):
        super().__init__(parent)
        self.image = image.copy()
        self.repository_dir = str(repository_dir)
        self.model_path = str(model_path)

    def run(self) -> None:
        try:
            self.progress.emit("Caricamento del detector e analisi della pagina…")
            boxes: list[Box] = detect_comic_text(
                self.image, self.repository_dir, self.model_path
            )
            self.result_ready.emit(boxes)
        except Exception as exc:
            self.fatal_error.emit(str(exc))
