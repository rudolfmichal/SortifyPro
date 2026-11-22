
from pathlib import Path

from core.file_sorter import create_sort_plan, get_category


def test_get_category():
    assert get_category(Path("zdjecie.jpg")) == "Obrazy"
    assert get_category(Path("dokument.pdf")) == "Dokumenty"
    assert get_category(Path("program.py")) == "Programowanie"
    assert get_category(Path("plik.xyz")) == "Inne"


def test_create_sort_plan(tmp_path):
    # Tworzymy przykładowe pliki testowe.
    (tmp_path / "zdjecie.jpg").write_text("test")
    (tmp_path / "dokument.pdf").write_text("test")
    (tmp_path / "program.py").write_text("test")

    plan = create_sort_plan(tmp_path)

    assert len(plan) == 3
    assert all(operation.source.exists() for operation in plan)

    # Samo przygotowanie planu nie może przenosić plików.
    assert (tmp_path / "zdjecie.jpg").exists()
    assert (tmp_path / "dokument.pdf").exists()
    assert (tmp_path / "program.py").exists()
