"""Run ONNX text detection outside the GUI thread."""
from __future__ import annotations

from pathlib import Path
from PIL import Image
from PySide6.QtCore import QThread, Signal

from .detection import Box, detect_manga_text


class DetectionWorker(QThread):
    result_ready = Signal(list)  # list[tuple[x, y, width, height]]
    fatal_error = Signal(str)
    progress = Signal(str)

    def __init__(self, image: Image.Image, model_path: str | Path, parent=None):
        super().__init__(parent)
        self.image = image.copy()
        self.model_path = str(model_path)

    def run(self) -> None:
        try:
            self.progress.emit("Caricamento di Manga-Bubble-YOLO e analisi della pagina…")
            boxes: list[Box] = detect_manga_text(self.image, self.model_path)
            self.result_ready.emit(boxes)
        except Exception as exc:
            self.fatal_error.emit(str(exc))
