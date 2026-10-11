"""Main graphical interface for Manga Reader."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
)

from .canvas import PageCanvas
from .export import assemble_text, write_text_file
from .models import TextRegion
from .ocr_worker import OCRWorker
from .detection_worker import DetectionWorker


STYLESHEET = """
QMainWindow, QWidget { background: #f5f6f8; color: #20242b; font-size: 10pt; }
QLabel#SectionTitle { font-size: 10pt; font-weight: 700; color: #394150; }
QLabel#Muted { color: #667085; }
QPushButton {
  background: #ffffff; border: 1px solid #d0d5dd; border-radius: 7px;
  padding: 8px 11px; color: #252a34;
}
QPushButton:hover { background: #eef2f7; border-color: #98a2b3; }
QPushButton:pressed { background: #e1e7ef; }
QPushButton:disabled { color: #98a2b3; background: #f2f4f7; }
QPushButton#Primary { background: #2459d3; color: white; border-color: #2459d3; font-weight: 600; }
QPushButton#Primary:hover { background: #1d49b3; }
QListWidget, QPlainTextEdit {
  background: #ffffff; border: 1px solid #d0d5dd; border-radius: 7px;
  selection-background-color: #dce8ff; selection-color: #20242b;
}
QListWidget { padding: 4px; }
QListWidget::item { padding: 9px 7px; border-radius: 4px; }
QPlainTextEdit { padding: 8px; font-size: 12pt; }
QFrame#Divider { color: #e2e5e9; }
QStatusBar { background: #ffffff; border-top: 1px solid #e4e7ec; }
"""


class ReorderListWidget(QListWidget):
    """A list that lets the user reorder regions with drag and drop."""

    order_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAlternatingRowColors(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        super().dropEvent(event)
        self.order_changed.emit()


class MangaReaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manga Reader · Japanese OCR")
        self.resize(1440, 900)
        self.setMinimumSize(1050, 680)
        self.setStyleSheet(STYLESHEET)

        self.page_image: Image.Image | None = None
        self.page_path: Path | None = None
        self.regions: list[TextRegion] = []
        self.worker: OCRWorker | None = None
        self.detection_worker: DetectionWorker | None = None
        self.settings = QSettings("ALE9M", "MangaReader")
        self._loading_editor = False
        self._syncing_list = False

        self._build_ui()
        self._connect_signals()
        self._create_actions()
        self._set_controls_enabled(False)

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 12)
        layout.setSpacing(12)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        title = QLabel("Manga Reader")
        title.setStyleSheet("font-size: 20pt; font-weight: 750; color: #172033;")
        subtitle = QLabel("Riconosci il giapponese, riordina i balloon, esporta il testo.")
        subtitle.setObjectName("Muted")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        header.addLayout(brand)
        header.addStretch(1)
        self.open_button = QPushButton("Apri immagine…")
        self.open_button.setObjectName("Primary")
        self.detect_button = QPushButton("Rileva aree testo…")
        self.detect_button.setToolTip("Rileva automaticamente blocchi e linee di testo con comic-text-detector")
        self.ocr_selected_button = QPushButton("OCR selezionato")
        self.ocr_all_button = QPushButton("OCR di tutte le regioni")
        self.export_button = QPushButton("Esporta .txt")
        header.addWidget(self.open_button)
        header.addWidget(self.detect_button)
        header.addWidget(self.ocr_selected_button)
        header.addWidget(self.ocr_all_button)
        header.addWidget(self.export_button)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left: page canvas
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(8)
        canvas_heading = QHBoxLayout()
        canvas_heading.addWidget(self._section_title("PAGINA"))
        canvas_heading.addStretch(1)
        self.page_info = QLabel("Nessuna immagine caricata")
        self.page_info.setObjectName("Muted")
        canvas_heading.addWidget(self.page_info)
        left_layout.addLayout(canvas_heading)

        self.canvas = PageCanvas()
        self.canvas.setMinimumWidth(420)
        left_layout.addWidget(self.canvas, 1)
        hint = QLabel(
            "Trascina sulla pagina per creare un riquadro intorno a un balloon, una didascalia "
            "o un’onomatopea. Clicca un riquadro per selezionarlo; Maiusc + trascinamento "
            "consente di creare un riquadro sovrapposto."
        )
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        left_layout.addWidget(hint)
        splitter.addWidget(left)

        # Right: ordered regions and editable OCR text
        right = QWidget()
        right.setMinimumWidth(360)
        right.setMaximumWidth(560)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)
        list_heading = QHBoxLayout()
        list_heading.addWidget(self._section_title("ORDINE DI LETTURA"))
        list_heading.addStretch(1)
        self.region_count = QLabel("0 regioni")
        self.region_count.setObjectName("Muted")
        list_heading.addWidget(self.region_count)
        right_layout.addLayout(list_heading)

        self.region_list = ReorderListWidget()
        self.region_list.setMinimumHeight(220)
        self.region_list.setToolTip("Trascina gli elementi per cambiare l'ordine di lettura.")
        right_layout.addWidget(self.region_list, 1)

        region_buttons = QHBoxLayout()
        self.move_up_button = QPushButton("↑ Su")
        self.move_down_button = QPushButton("↓ Giù")
        self.remove_button = QPushButton("Rimuovi")
        self.clear_button = QPushButton("Rimuovi tutte")
        region_buttons.addWidget(self.move_up_button)
        region_buttons.addWidget(self.move_down_button)
        region_buttons.addWidget(self.remove_button)
        region_buttons.addWidget(self.clear_button)
        right_layout.addLayout(region_buttons)

        editor_heading = QHBoxLayout()
        editor_heading.addWidget(self._section_title("TRASCRIZIONE GIAPPONESE"))
        editor_heading.addStretch(1)
        right_layout.addLayout(editor_heading)
        self.text_editor = QPlainTextEdit()
        self.text_editor.setPlaceholderText(
            "Seleziona una regione per visualizzare o correggere qui il testo riconosciuto…"
        )
        self.text_editor.setMinimumHeight(175)
        right_layout.addWidget(self.text_editor, 1)

        editor_help = QLabel(
            "Le trascrizioni sono modificabili. L’esportazione segue esattamente l’ordine "
            "mostrato nell’elenco."
        )
        editor_help.setObjectName("Muted")
        editor_help.setWordWrap(True)
        right_layout.addWidget(editor_help)
        splitter.addWidget(right)
        splitter.setSizes([850, 500])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Pronto · Apri una pagina manga per iniziare")

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    def _create_actions(self) -> None:
        open_action = QAction("Apri immagine", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_image)
        self.addAction(open_action)

        export_action = QAction("Esporta testo", self)
        export_action.setShortcut(QKeySequence.StandardKey.Save)
        export_action.triggered.connect(self.export_text)
        self.addAction(export_action)

    def _connect_signals(self) -> None:
        self.open_button.clicked.connect(self.open_image)
        self.detect_button.clicked.connect(self.detect_regions)
        self.ocr_selected_button.clicked.connect(self.ocr_selected)
        self.ocr_all_button.clicked.connect(self.ocr_all)
        self.export_button.clicked.connect(self.export_text)
        self.move_up_button.clicked.connect(lambda: self.move_region(-1))
        self.move_down_button.clicked.connect(lambda: self.move_region(1))
        self.remove_button.clicked.connect(self.remove_selected_region)
        self.clear_button.clicked.connect(self.clear_regions)
        self.region_list.currentRowChanged.connect(self.on_current_row_changed)
        self.region_list.order_changed.connect(self.sync_order_from_list)
        self.text_editor.textChanged.connect(self.on_editor_changed)
        self.canvas.region_drawn.connect(self.add_region)
        self.canvas.region_activated.connect(self.select_region_by_id)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for control in (
            self.detect_button,
            self.ocr_selected_button,
            self.ocr_all_button,
            self.export_button,
            self.move_up_button,
            self.move_down_button,
            self.remove_button,
            self.clear_button,
            self.region_list,
            self.text_editor,
        ):
            control.setEnabled(enabled)

    def open_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Apri una pagina manga",
            str(self.page_path.parent) if self.page_path else "",
            "Immagini (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;Tutti i file (*)",
        )
        if not filename:
            return
        if self.regions:
            answer = QMessageBox.question(
                self,
                "Cambiare pagina?",
                "Aprire una nuova immagine eliminerà le regioni e le trascrizioni della pagina corrente. Continuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            with Image.open(filename) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
                image.load()
        except Exception as exc:
            QMessageBox.critical(self, "Impossibile aprire l’immagine", str(exc))
            return

        self.page_image = image
        self.page_path = Path(filename)
        self.regions.clear()
        self.canvas.set_page_image(image)
        self.page_info.setText(f"{image.width} × {image.height} px · {self.page_path.name}")
        self._set_controls_enabled(True)
        self.refresh_region_list()
        self.statusBar().showMessage("Pagina caricata · Trascina sull’immagine per delimitare il primo balloon")

    def detect_regions(self) -> None:
        """Detect text blocks with comic-text-detector without freezing the GUI."""
        if self.page_image is None:
            QMessageBox.information(self, "Nessuna pagina", "Apri prima una pagina manga.")
            return
        if self.worker is not None or self.detection_worker is not None:
            return
        if self.regions:
            answer = QMessageBox.question(
                self,
                "Sostituire le regioni?",
                "Il rilevamento automatico sostituirà i riquadri attuali. Vuoi continuare?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        default_repo = str(self.settings.value("detector/repository", str(Path.home() / "comic-text-detector")))
        repository = QFileDialog.getExistingDirectory(
            self, "Seleziona la cartella comic-text-detector", default_repo
        )
        if not repository:
            return
        if not (Path(repository) / "inference.py").is_file():
            QMessageBox.warning(
                self, "Cartella non valida",
                "La cartella selezionata non contiene inference.py. Clona il repository "
                "https://github.com/dmMaze/comic-text-detector e seleziona la cartella radice."
            )
            return
        self.settings.setValue("detector/repository", repository)

        saved_model = str(self.settings.value("detector/model", ""))
        candidates = [
            Path(saved_model) if saved_model else None,
            Path(repository) / "data" / "comictextdetector.pt.onnx",
            Path(repository) / "data" / "comictextdetector.pt",
            Path(repository) / "models" / "comictextdetector.pt.onnx",
            Path(repository) / "models" / "comictextdetector.pt",
            Path.home() / "models" / "comictextdetector.pt.onnx",
            Path.home() / "models" / "comictextdetector.pt",
        ]
        model_path = next((p for p in candidates if p is not None and p.is_file()), None)
        if model_path is None:
            model_name, _ = QFileDialog.getOpenFileName(
                self,
                "Seleziona il checkpoint comic-text-detector",
                str(Path(repository) / "data"),
                "Modelli detector (*.onnx *.pt);;Tutti i file (*)",
            )
            if not model_name:
                return
            model_path = Path(model_name)
        if model_path.suffix.lower() not in {".pt", ".onnx"}:
            QMessageBox.warning(self, "Formato non riconosciuto", "Seleziona un file .pt oppure .onnx.")
            return
        self.settings.setValue("detector/model", str(model_path))

        self.detection_worker = DetectionWorker(
            self.page_image, repository, model_path, self
        )
        self.detection_worker.progress.connect(self.on_detection_progress)
        self.detection_worker.result_ready.connect(self.on_detection_result)
        self.detection_worker.fatal_error.connect(self.on_detection_error)
        self.detection_worker.finished.connect(self.on_detection_finished)
        self.open_button.setEnabled(False)
        self.detect_button.setEnabled(False)
        self.ocr_selected_button.setEnabled(False)
        self.ocr_all_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.statusBar().showMessage("Avvio del rilevamento automatico…")
        self._update_region_buttons()
        self.detection_worker.start()

    def on_detection_progress(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def on_detection_result(self, boxes: list) -> None:
        if not boxes:
            self.statusBar().showMessage("Nessun blocco di testo rilevato.", 10000)
            QMessageBox.information(
                self, "Nessun testo rilevato",
                "Il detector non ha trovato blocchi di testo in questa pagina. "
                "Controlla il modello oppure disegna le aree manualmente."
            )
            return
        self.regions = [
            TextRegion(x=x, y=y, width=width, height=height, source="auto")
            for x, y, width, height in boxes
        ]
        self.refresh_region_list(selected_id=self.regions[0].id if self.regions else None)
        self.statusBar().showMessage(
            f"Rilevate {len(self.regions)} aree di testo. Verifica e riordina l'elenco prima dell'OCR.",
            15000,
        )

    def on_detection_error(self, message: str) -> None:
        QMessageBox.critical(
            self, "Rilevamento automatico non riuscito",
            f"{message}\n\nConsulta la sezione comic-text-detector nel README."
        )

    def on_detection_finished(self) -> None:
        self.detection_worker = None
        self.open_button.setEnabled(True)
        self._update_region_buttons()

    def add_region(self, x: int, y: int, width: int, height: int) -> None:
        if self.page_image is None:
            return
        region = TextRegion(x=x, y=y, width=width, height=height, source="manual")
        self.regions.append(region)
        self.refresh_region_list(selected_id=region.id)
        self.statusBar().showMessage(f"Regione {len(self.regions)} aggiunta")

    def refresh_region_list(self, selected_id: str | None = None) -> None:
        self._syncing_list = True
        self.region_list.clear()
        selected_row = -1
        for row, region in enumerate(self.regions):
            snippet = " ".join(region.text.split())
            if not snippet:
                snippet = "[Testo non ancora riconosciuto]"
            if len(snippet) > 48:
                snippet = snippet[:45] + "…"
            origin = "AUTO" if region.source == "auto" else "MANUALE"
            item = QListWidgetItem(f"{row + 1:02d}  ·  {origin}  ·  {snippet}")
            item.setData(Qt.ItemDataRole.UserRole, region.id)
            item.setToolTip(f"Regione {row + 1} · x={region.x}, y={region.y}, {region.width}×{region.height}")
            self.region_list.addItem(item)
            if region.id == selected_id:
                selected_row = row
        if selected_row >= 0:
            self.region_list.setCurrentRow(selected_row)
        elif self.regions:
            self.region_list.setCurrentRow(0)
        else:
            self.region_list.setCurrentRow(-1)
        self._syncing_list = False
        self.region_count.setText(f"{len(self.regions)} regioni")
        selected = self.current_region()
        self.canvas.set_regions(self.regions, selected.id if selected else None)
        self._update_editor_from_selection()
        self._update_region_buttons()

    def sync_order_from_list(self, *_args) -> None:
        if self._syncing_list:
            return
        ids = [self.region_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.region_list.count())]
        by_id = {region.id: region for region in self.regions}
        if len(ids) == len(self.regions) and all(region_id in by_id for region_id in ids):
            self.regions = [by_id[region_id] for region_id in ids]
            selected = self.current_region()
            self.canvas.set_regions(self.regions, selected.id if selected else None)
            self.region_count.setText(f"{len(self.regions)} regioni")
            self._update_editor_from_selection()
            self._update_region_buttons()
            self.statusBar().showMessage("Ordine di lettura aggiornato")

    def current_region(self) -> TextRegion | None:
        row = self.region_list.currentRow()
        if 0 <= row < len(self.regions):
            return self.regions[row]
        return None

    def select_region_by_id(self, region_id: str) -> None:
        for row, region in enumerate(self.regions):
            if region.id == region_id:
                self.region_list.setCurrentRow(row)
                break

    def on_current_row_changed(self, _row: int) -> None:
        if self._syncing_list:
            return
        self._update_editor_from_selection()
        selected = self.current_region()
        self.canvas.set_regions(self.regions, selected.id if selected else None)
        self._update_region_buttons()

    def _update_editor_from_selection(self) -> None:
        region = self.current_region()
        self._loading_editor = True
        self.text_editor.setPlainText(region.text if region else "")
        self.text_editor.setEnabled(region is not None and self.page_image is not None)
        self._loading_editor = False

    def on_editor_changed(self) -> None:
        if self._loading_editor:
            return
        region = self.current_region()
        if region is None:
            return
        region.text = self.text_editor.toPlainText()
        row = self.region_list.currentRow()
        if row >= 0:
            snippet = " ".join(region.text.split()) or "[Testo non ancora riconosciuto]"
            if len(snippet) > 48:
                snippet = snippet[:45] + "…"
            item = self.region_list.item(row)
            origin = "AUTO" if region.source == "auto" else "MANUALE"
            item.setText(f"{row + 1:02d}  ·  {origin}  ·  {snippet}")
            item.setToolTip(f"Regione {row + 1} · x={region.x}, y={region.y}, {region.width}×{region.height}")

    def _update_region_buttons(self) -> None:
        row = self.region_list.currentRow()
        has_selection = self.current_region() is not None
        busy = self.worker is not None or self.detection_worker is not None
        self.move_up_button.setEnabled(not busy and has_selection and row > 0)
        self.move_down_button.setEnabled(
            not busy and has_selection and row < len(self.regions) - 1
        )
        self.remove_button.setEnabled(not busy and has_selection)
        self.clear_button.setEnabled(not busy and bool(self.regions))
        self.region_list.setEnabled(not busy and self.page_image is not None)
        self.canvas.setEnabled(not busy and self.page_image is not None)
        self.text_editor.setEnabled(not busy and has_selection and self.page_image is not None)
        self.ocr_selected_button.setEnabled(not busy and has_selection)
        self.ocr_all_button.setEnabled(not busy and bool(self.regions))
        self.export_button.setEnabled(not busy and bool(self.regions))
        self.detect_button.setEnabled(self.page_image is not None and not busy)

    def move_region(self, offset: int) -> None:
        row = self.region_list.currentRow()
        new_row = row + offset
        if row < 0 or not (0 <= new_row < len(self.regions)):
            return
        self.regions[row], self.regions[new_row] = self.regions[new_row], self.regions[row]
        selected_id = self.regions[new_row].id
        self.refresh_region_list(selected_id)
        self.statusBar().showMessage("Ordine di lettura aggiornato")

    def remove_selected_region(self) -> None:
        row = self.region_list.currentRow()
        if 0 <= row < len(self.regions):
            del self.regions[row]
            selected_id = self.regions[min(row, len(self.regions) - 1)].id if self.regions else None
            self.refresh_region_list(selected_id)
            self.statusBar().showMessage("Regione rimossa")

    def clear_regions(self) -> None:
        if not self.regions:
            return
        answer = QMessageBox.question(
            self,
            "Rimuovere tutte le regioni?",
            "Vuoi eliminare tutti i riquadri e le trascrizioni di questa pagina?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.regions.clear()
            self.refresh_region_list()
            self.statusBar().showMessage("Tutte le regioni sono state rimosse")

    def _crop_region(self, region: TextRegion) -> Image.Image:
        assert self.page_image is not None
        left = max(0, region.x)
        top = max(0, region.y)
        right = min(self.page_image.width, region.x + region.width)
        bottom = min(self.page_image.height, region.y + region.height)
        if right <= left or bottom <= top:
            raise ValueError("Il riquadro non contiene pixel dell'immagine.")
        return self.page_image.crop((left, top, right, bottom)).copy()

    def ocr_selected(self) -> None:
        region = self.current_region()
        if region is not None:
            self._start_ocr([region])

    def ocr_all(self) -> None:
        if self.regions:
            self._start_ocr(list(self.regions))

    def _start_ocr(self, regions: list[TextRegion]) -> None:
        if self.worker is not None:
            return
        if self.page_image is None:
            return
        try:
            jobs = [(region.id, self._crop_region(region)) for region in regions]
        except Exception as exc:
            QMessageBox.warning(self, "Ritaglio non valido", str(exc))
            return
        self.worker = OCRWorker(jobs, self)
        self.worker.result_ready.connect(self.on_ocr_result)
        self.worker.region_error.connect(self.on_ocr_region_error)
        self.worker.fatal_error.connect(self.on_ocr_fatal_error)
        self.worker.progress.connect(self.on_ocr_progress)
        self.worker.finished.connect(self.on_ocr_finished)
        self.ocr_selected_button.setEnabled(False)
        self.ocr_all_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.statusBar().showMessage("Avvio del motore OCR… Al primo utilizzo il modello può essere scaricato da internet.")
        self._update_region_buttons()
        self.worker.start()

    def on_ocr_result(self, region_id: str, text: str) -> None:
        for region in self.regions:
            if region.id == region_id:
                region.text = text
                break
        current = self.current_region()
        current_id = current.id if current else None
        self.refresh_region_list(selected_id=current_id)

    def on_ocr_region_error(self, region_id: str, message: str) -> None:
        self.statusBar().showMessage(f"Errore OCR in una regione: {message[:160]}", 10000)

    def on_ocr_fatal_error(self, message: str) -> None:
        QMessageBox.critical(self, "Errore durante l'OCR", message)

    def on_ocr_progress(self, completed: int, total: int, message: str) -> None:
        if total:
            self.statusBar().showMessage(f"{message} — {completed}/{total}")
        else:
            self.statusBar().showMessage(message)

    def on_ocr_finished(self) -> None:
        self.worker = None
        self.open_button.setEnabled(True)
        self._update_region_buttons()
        self.statusBar().showMessage("OCR terminato · Controlla le trascrizioni e correggi eventuali errori", 10000)

    def export_text(self) -> None:
        if not self.regions:
            QMessageBox.information(self, "Nessuna regione", "Aggiungi almeno un riquadro prima di esportare il testo.")
            return
        text = assemble_text(self.regions)
        if not text:
            QMessageBox.information(
                self,
                "Nessuna trascrizione",
                "Le regioni non contengono ancora testo. Esegui l'OCR o inserisci le trascrizioni manualmente.",
            )
            return
        default_name = (
            f"{self.page_path.stem}_japanese.txt" if self.page_path else "manga_japanese.txt"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self, "Esporta testo giapponese", default_name, "File di testo (*.txt)"
        )
        if not filename:
            return
        destination = Path(filename)
        if destination.suffix.lower() != ".txt":
            destination = destination.with_suffix(".txt")
        try:
            write_text_file(self.regions, destination)
        except OSError as exc:
            QMessageBox.critical(self, "Esportazione non riuscita", str(exc))
            return
        self.statusBar().showMessage(f"Testo esportato: {destination}", 10000)
        QMessageBox.information(self, "Esportazione completata", f"Testo salvato in UTF-8 in:\n{destination}")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Manga Reader")
    window = MangaReaderWindow()
    window.show()
    return app.exec()
