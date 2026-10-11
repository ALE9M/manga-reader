"""Image canvas that lets users mark text balloons with the mouse."""

from __future__ import annotations

from io import BytesIO
from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView

from .models import TextRegion


class PageCanvas(QGraphicsView):
    """A fit-to-window page view; drag to add a text region."""

    region_drawn = Signal(int, int, int, int)
    region_activated = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setBackgroundBrush(QBrush(QColor("#20242b")))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setMouseTracking(True)
        self._image_item = None
        self._image_size: tuple[int, int] | None = None
        self._overlay_items: list[QGraphicsItem] = []
        self._start_point: QPointF | None = None
        self._preview_item: QGraphicsRectItem | None = None
        self._regions: list[TextRegion] = []
        self._selected_id: str | None = None

    def set_page_image(self, image: Image.Image) -> None:
        """Show the same EXIF-corrected pixels used later for OCR crops."""
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        qimage = QImage.fromData(buffer.getvalue())
        pixmap = QPixmap.fromImage(qimage)
        self._scene.clear()
        self._overlay_items.clear()
        self._preview_item = None
        self._image_item = self._scene.addPixmap(pixmap)
        self._image_item.setZValue(0)
        self._image_size = (image.width, image.height)
        self._scene.setSceneRect(QRectF(0, 0, image.width, image.height))
        self._regions = []
        self._selected_id = None
        self.fit_page()

    def fit_page(self) -> None:
        if self._image_item is not None:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_regions(self, regions: list[TextRegion], selected_id: str | None) -> None:
        self._regions = regions
        self._selected_id = selected_id
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()
        if self._image_item is None:
            return

        for index, region in enumerate(regions, start=1):
            selected = region.id == selected_id
            color = QColor("#ffca5c" if selected else "#42d9c8")
            pen = QPen(color, 2.4 if selected else 1.8)
            pen.setCosmetic(True)
            rect_item = self._scene.addRect(
                QRectF(region.x, region.y, region.width, region.height),
                pen,
                QBrush(Qt.BrushStyle.NoBrush),
            )
            rect_item.setZValue(2)
            self._overlay_items.append(rect_item)

            tag = QGraphicsSimpleTextItem(str(index))
            tag.setBrush(QBrush(QColor("#171a1f")))
            tag.setFont(QFont("Sans Serif", 10, QFont.Weight.Bold))
            tag.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            tag.setPos(region.x + 3, region.y + 3)
            tag.setZValue(3)
            self._scene.addItem(tag)
            self._overlay_items.append(tag)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt method name
        super().resizeEvent(event)
        self.fit_page()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._image_item is not None
            and self._image_size is not None
        ):
            point = self.mapToScene(event.position().toPoint())
            width, height = self._image_size
            if not (0 <= point.x() <= width and 0 <= point.y() <= height):
                return

            force_draw = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if not force_draw:
                for region in reversed(self._regions):
                    bounds = QRectF(region.x, region.y, region.width, region.height)
                    if bounds.contains(point):
                        self.region_activated.emit(region.id)
                        event.accept()
                        return

            self._start_point = point
            pen = QPen(QColor("#ffca5c"), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._preview_item = self._scene.addRect(QRectF(point, point), pen)
            self._preview_item.setZValue(10)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._start_point is not None and self._preview_item is not None:
            current = self.mapToScene(event.position().toPoint())
            self._preview_item.setRect(QRectF(self._start_point, current).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._start_point is not None
            and self._preview_item is not None
            and self._image_size is not None
        ):
            current = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._start_point, current).normalized()
            self._scene.removeItem(self._preview_item)
            self._preview_item = None
            self._start_point = None

            img_w, img_h = self._image_size
            left = max(0, min(img_w, round(rect.left())))
            top = max(0, min(img_h, round(rect.top())))
            right = max(0, min(img_w, round(rect.right())))
            bottom = max(0, min(img_h, round(rect.bottom())))
            if right - left >= 8 and bottom - top >= 8:
                self.region_drawn.emit(left, top, right - left, bottom - top)
            event.accept()
            return
        super().mouseReleaseEvent(event)
