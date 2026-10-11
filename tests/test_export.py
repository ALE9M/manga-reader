from pathlib import Path

from manga_reader.export import assemble_text, write_text_file
from manga_reader.models import TextRegion


def test_assemble_text_preserves_order_and_skips_empty_regions():
    regions = [
        TextRegion(0, 0, 20, 20, "二番"),
        TextRegion(0, 0, 20, 20, "  "),
        TextRegion(0, 0, 20, 20, "一番\nです"),
    ]
    assert assemble_text(regions) == "二番\n\n一番\nです"


def test_write_text_file_is_utf8(tmp_path: Path):
    target = tmp_path / "text.txt"
    write_text_file([TextRegion(0, 0, 10, 10, "こんにちは")], target)
    assert target.read_bytes() == "こんにちは".encode("utf-8")
    assert target.read_text(encoding="utf-8") == "こんにちは"
