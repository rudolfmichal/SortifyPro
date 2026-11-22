"""Tests for the folder scanner."""
from pathlib import Path
from core.file_scanner import scan_folder


def test_scan_folder_counts_files_and_folders(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "docs" / "b.pdf").write_bytes(b"1234")

    result = scan_folder(tmp_path)

    assert result.file_count == 2
    assert result.folder_count == 1
    assert result.total_bytes == 9
    assert result.extensions[".txt"] == 1
    assert result.extensions[".pdf"] == 1
