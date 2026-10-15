"""Manga-Bubble-YOLO text detection using ONNX Runtime (CPU)."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from PIL import Image

Box = tuple[int, int, int, int]  # x, y, width, height
INPUT_SIZE = 1280
DEFAULT_CONFIDENCE = 0.25


def normalize_xyxy(raw_boxes: Iterable[Iterable[float]], width: int, height: int) -> list[Box]:
    """Clamp XYXY boxes to the page, discard degenerate boxes, and deduplicate."""
    result: list[Box] = []
    for raw in raw_boxes:
        try:
            x1, y1, x2, y2 = (int(round(float(v))) for v in raw[:4])
        except (TypeError, ValueError, IndexError):
            continue
        left = max(0, min(width, x1))
        top = max(0, min(height, y1))
        right = max(0, min(width, x2))
        bottom = max(0, min(height, y2))
        if right - left < 8 or bottom - top < 8:
            continue
        box = (left, top, right - left, bottom - top)
        if any(all(abs(a - b) <= 2 for a, b in zip(box, old)) for old in result):
            continue
        result.append(box)

    # Suggested manga reading order: top-to-bottom, right-to-left within rows.
    result.sort(key=lambda b: (b[1], -b[0]))
    return result


def decode_yolo26_output(
    raw_output,
    width: int,
    height: int,
    confidence_threshold: float = DEFAULT_CONFIDENCE,
) -> list[Box]:
    """Convert YOLO26 ONNX output (1, 300, 6) into original-page boxes.

    Each prediction row is [x1, y1, x2, y2, confidence, class_id]. This parser
    deliberately uses only Python built-ins, so its unit tests do not need the
    heavy inference dependencies installed.
    """
    # ONNX Runtime returns NumPy arrays, while unit tests can use plain lists.
    if hasattr(raw_output, "tolist"):
        predictions = raw_output.tolist()
    else:
        predictions = raw_output
    if not isinstance(predictions, (list, tuple)) or not predictions:
        return []

    # Accept the model's batch-one output shape (1, N, 6) and test/direct N x 6.
    first = predictions[0]
    if (
        isinstance(first, (list, tuple))
        and first
        and isinstance(first[0], (list, tuple))
    ):
        if len(predictions) != 1:
            raise RuntimeError(
                f"Output del modello non supportato: batch {len(predictions)}, atteso 1."
            )
        predictions = first

    if not isinstance(predictions, (list, tuple)):
        raise RuntimeError("Output del modello non riconosciuto.")
    if not predictions:
        return []
    if any(not isinstance(row, (list, tuple)) or len(row) < 6 for row in predictions):
        raise RuntimeError("Output del modello non riconosciuto: attese righe con 6 valori.")

    parsed_rows = []
    finite_coords = []
    for row in predictions:
        try:
            values = [float(value) for value in row[:6]]
        except (TypeError, ValueError):
            continue
        parsed_rows.append(values)
        for value in values[:4]:
            if math.isfinite(value):
                finite_coords.append(abs(value))

    # Also tolerate normalized xyxy output from compatible model exports.
    coord_scale = INPUT_SIZE if finite_coords and max(finite_coords) <= 2.0 else 1.0
    x_scale = width / INPUT_SIZE
    y_scale = height / INPUT_SIZE
    boxes = []
    for row in parsed_rows:
        x1, y1, x2, y2, score, _class_id = row
        if not math.isfinite(score) or score < confidence_threshold:
            continue
        coords = (x1, y1, x2, y2)
        if not all(math.isfinite(value) for value in coords):
            continue
        boxes.append(
            (
                x1 * coord_scale * x_scale,
                y1 * coord_scale * y_scale,
                x2 * coord_scale * x_scale,
                y2 * coord_scale * y_scale,
            )
        )
    return normalize_xyxy(boxes, width, height)

def detect_manga_text(image: Image.Image, model_path: str | Path) -> list[Box]:
    """Detect manga text regions with Manga-Bubble-YOLO's ONNX model."""
    checkpoint = Path(model_path).expanduser().resolve()
    if not checkpoint.is_file():
        raise RuntimeError(
            f"Modello Manga-Bubble-YOLO non trovato: {checkpoint}. "
            "Esegui setup_windows.bat per scaricare il modello."
        )
    if checkpoint.suffix.lower() != ".onnx":
        raise RuntimeError("Manga Reader richiede il modello ONNX yolo26n.onnx.")

    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(
            "Mancano le dipendenze del rilevatore ONNX. Esegui setup_windows.bat."
        ) from exc

    try:
        # Match the model card's preprocessing. The model is trained/instructed
        # with a square resize (not letterboxing), then RGB NCHW float32 [0, 1].
        resized = image.convert("RGB").resize(
            (INPUT_SIZE, INPUT_SIZE), Image.Resampling.BILINEAR
        )
        tensor = np.asarray(resized, dtype=np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...]

        session = ort.InferenceSession(
            str(checkpoint), providers=["CPUExecutionProvider"]
        )
        inputs = session.get_inputs()
        if not inputs:
            raise RuntimeError("Il modello ONNX non dichiara input utilizzabili.")
        outputs = session.run(None, {inputs[0].name: tensor})
        if not outputs:
            raise RuntimeError("Il modello ONNX non ha restituito predizioni.")
        return decode_yolo26_output(outputs[0], image.width, image.height)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            "Manga-Bubble-YOLO non è riuscito a elaborare la pagina: "
            f"{type(exc).__name__}: {exc}. Verifica il modello ONNX e le dipendenze."
        ) from exc
