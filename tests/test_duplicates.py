import threading

import pytest

from core.duplicates import DuplicateFinder, hash_file, move_duplicates
from core.history import OperationHistory
from core.settings import Settings


@pytest.mark.parametrize("mode", ["sequential", "thread", "process"])
def test_finds_exact_duplicates_only(messy_folder, mode):
    report = DuplicateFinder(workers=2, mode=mode, min_size=1000).find(messy_folder)
    assert len(report.groups) == 1
    group = report.groups[0]
    assert {p.name for p in group.files} == {"a.txt", "a (1).txt", "a_copy.txt"}
    assert group.original.name == "a.txt"          # najkrótsza/„oryginalna” nazwa
    assert report.duplicate_count == 2
    assert report.wasted_bytes == 6000


def test_min_size_excludes_small_files(messy_folder):
    report = DuplicateFinder(mode="sequential", min_size=5000).find(messy_folder)
    assert report.groups == []


def test_hash_file_matches_for_equal_content(messy_folder):
    assert hash_file(messy_folder / "a.txt") == hash_file(messy_folder / "a (1).txt")
    assert hash_file(messy_folder / "a.txt") != hash_file(messy_folder / "b.txt")


def test_invalid_configuration():
    with pytest.raises(ValueError):
        DuplicateFinder(workers=0)
    with pytest.raises(ValueError):
        DuplicateFinder(mode="quantum")
    assert DuplicateFinder.is_valid_mode("thread")
    assert not DuplicateFinder.is_valid_mode("x")


def test_from_settings():
    settings = Settings(workers=3, hash_mode="thread", min_duplicate_size=2048)
    finder = DuplicateFinder.from_settings(settings)
    assert (finder.workers, finder.mode, finder.min_size) == (3, "thread", 2048)


def test_cancel_returns_flagged_report(messy_folder):
    cancel = threading.Event()
    cancel.set()
    report = DuplicateFinder(mode="thread", min_size=1).find(messy_folder, cancel=cancel)
    assert report.cancelled


def test_missing_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        DuplicateFinder().find(tmp_path / "nie_ma")


def test_move_duplicates_and_undo(messy_folder, tmp_path):
    history = OperationHistory(tmp_path / "h.json")
    report = DuplicateFinder(mode="sequential", min_size=1000).find(messy_folder)
    result = move_duplicates(report, history)
    assert result.moved_count == 2 and not result.errors
    assert (messy_folder / "a.txt").exists()           # oryginał zostaje
    assert not (messy_folder / "a (1).txt").exists()
    assert len(list((messy_folder / "_Duplikaty").iterdir())) == 2

    batch = history.batches()[-1]
    undone = history.undo(batch.batch_id)
    assert undone.restored == 2 and not undone.errors
    assert (messy_folder / "a (1).txt").exists()
    assert (messy_folder / "sub" / "a_copy.txt").exists()
