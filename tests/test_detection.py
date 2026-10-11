from manga_reader.detection import normalize_xyxy


def test_normalize_boxes_clamps_and_sorts_for_manga_reading():
    boxes = normalize_xyxy(
        [
            [110, 15, 150, 50],  # clipped to the right edge
            [10, 15, 40, 50],
            [-4, 65, 20, 90],
            [2, 2, 4, 4],  # too small
            [10, 15, 40, 50],  # duplicate
        ],
        width=120,
        height=80,
    )
    assert boxes == [
        (110, 15, 10, 35),
        (10, 15, 30, 35),
        (0, 65, 20, 15),
    ]
