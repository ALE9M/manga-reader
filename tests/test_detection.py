from manga_reader.detection import decode_yolo26_output, normalize_xyxy


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



def test_decode_yolo26_output_maps_boxes_back_to_original_page_and_filters_low_confidence():
    # Model input is 1280x1280 while the original page is 2560x1280.
    output = [
        [
            [640.0, 320.0, 960.0, 640.0, 0.90, 0.0],
            [100.0, 100.0, 200.0, 200.0, 0.20, 0.0],
        ]
    ]

    boxes = decode_yolo26_output(output, width=2560, height=1280)

    assert boxes == [(1280, 320, 640, 320)]


def test_decode_yolo26_output_accepts_normalized_coordinates():
    output = [[[0.1, 0.2, 0.5, 0.4, 0.95, 0.0]]]

    boxes = decode_yolo26_output(output, width=2560, height=1280)

    assert boxes == [(256, 256, 1024, 256)]
