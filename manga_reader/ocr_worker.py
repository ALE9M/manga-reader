"""Background worker for Manga OCR so the interface stays responsive."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QThread, Signal


class OCRWorker(QThread):
    result_ready = Signal(str, str)  # region_id, recognized text
    region_error = Signal(str, str)  # region_id, error message
    fatal_error = Signal(str)
    progress = Signal(int, int, str)  # completed, total, status message

    def __init__(self, jobs: list[tuple[str, Image.Image]], parent=None):
        super().__init__(parent)
        self.jobs = jobs

    def run(self) -> None:
        try:
            self.progress.emit(0, len(self.jobs), "Caricamento del modello Manga OCR…")
            from manga_ocr import MangaOcr

            recognizer = MangaOcr()
            total = len(self.jobs)
            for index, (region_id, crop) in enumerate(self.jobs, start=1):
                try:
                    text = recognizer(crop)
                    self.result_ready.emit(region_id, str(text).strip())
                except Exception as exc:  # one bad crop should not stop the page
                    self.region_error.emit(region_id, f"{type(exc).__name__}: {exc}")
                self.progress.emit(index, total, f"OCR: {index}/{total}")
        except Exception as exc:
            self.fatal_error.emit(
                f"{type(exc).__name__}: {exc}\n\n"
                "Controlla l'installazione di manga-ocr e la connessione internet "
                "necessaria al primo download del modello."
            )
