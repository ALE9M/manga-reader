"""Adapter for dmMaze/comic-text-detector.

The detector is intentionally an external checkout: we do not vendor its GPL-3.0
source or distribute its pretrained weights inside this repository.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image

Box = tuple[int, int, int, int]  # x, y, width, height


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
        # Some detector versions can yield the same block more than once.
        if any(all(abs(a - b) <= 2 for a, b in zip(box, old)) for old in result):
            continue
        result.append(box)

    # A helpful default for Japanese pages: top-to-bottom, and right-to-left
    # for blocks at approximately the same vertical position. It is only a
    # starting order; the UI deliberately leaves final ordering to the user.
    result.sort(key=lambda b: (b[1], -b[0]))
    return result


def detect_comic_text(image: Image.Image, repository_dir: str | Path,
                      model_path: str | Path) -> list[Box]:
    """Detect comic text blocks using the upstream TextDetector API.

    \`comic-text-detector\` does not expose a normal pip API. The upstream README
    instructs users to clone its repository and download a checkpoint. The
    adapter calls its documented \`TextDetector(model_path=..., ...)\` class and
    uses the returned TextBlock.xyxy rectangles.
    """
    repository = Path(repository_dir).expanduser().resolve()
    checkpoint = Path(model_path).expanduser().resolve()
    if not (repository / "inference.py").is_file():
        raise RuntimeError(
            "Cartella comic-text-detector non valida: non trovo inference.py. "
            "Clona https://github.com/dmMaze/comic-text-detector e seleziona la cartella corretta."
        )
    if not checkpoint.is_file():
        raise RuntimeError("Checkpoint del modello non trovato: seleziona un file .pt o .onnx.")

    import cv2
    import numpy as np
    import torch

    old_sys_path = list(sys.path)
    sys.path.insert(0, str(repository))
    try:
        # The upstream code uses root-level imports (basemodel, utils, models).
        # Import it only after making the cloned repository importable.
        importlib.invalidate_caches()
        inference = importlib.import_module("inference")
        detector_class = getattr(inference, "TextDetector", None)
        if detector_class is None:
            raise RuntimeError(
                "Versione incompatibile di comic-text-detector: la classe TextDetector non è presente."
            )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        detector = detector_class(
            model_path=str(checkpoint), input_size=1024, device=device, act="leaky"
        )
        # Upstream preprocess_img expects BGR and converts it to RGB internally.
        rgb = np.asarray(image.convert("RGB"))
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        try:
            from utils.textmask import REFINEMASK_ANNOTATION
            _mask, _refined_mask, blocks = detector(
                bgr, refine_mode=REFINEMASK_ANNOTATION, keep_undetected_mask=False
            )
        except ImportError:
            _mask, _refined_mask, blocks = detector(bgr)

        coordinates = []
        for block in blocks or []:
            box = getattr(block, "xyxy", None)
            if box is not None and len(box) >= 4:
                coordinates.append(box[:4])
        return normalize_xyxy(coordinates, image.width, image.height)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(
            f"comic-text-detector non è riuscito a elaborare la pagina: {type(exc).__name__}: {exc}. "
            "Verifica dipendenze, checkpoint e versione del repository upstream."
        ) from exc
    finally:
        sys.path[:] = old_sys_path
