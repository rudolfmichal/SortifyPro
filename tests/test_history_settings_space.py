import json

import pytest

from core.file_sorter import (
    SortOperation, create_sort_plan, execute_moves, execute_sort_plan,
)
from core.history import OperationHistory
from core.settings import Settings
from core.space_analyzer import analyze_space
from utils.fs import ensure_directory, format_size


def test_sort_with_group_by_date(messy_folder):
    plan = create_sort_plan(messy_folder, group_by_date=True)
    dest = {op.source.name: op.destination for op in plan}
    assert dest["photo_20240315.jpg"].parent.name == "2024-03"
    assert dest["photo_20240315.jpg"].parent.parent.name == "Obrazy"
    assert dest["a.txt"].parent.name == "Dokumenty"
    assert "a_copy.txt" not in dest  # tylko pliki z poziomu głównego


def test_execute_never_overwrites(tmp_path):
    (tmp_path / "x.txt").write_text("nowy")
    (tmp_path / "Dokumenty").mkdir()
    (tmp_path / "Dokumenty" / "x.txt").write_text("stary")
    result = execute_moves(create_sort_plan(tmp_path))
    assert result.moved_count == 1
    assert (tmp_path / "Dokumenty" / "x.txt").read_text() == "stary"
    assert (tmp_path / "Dokumenty" / "x_1.txt").read_text() == "nowy"


def test_execute_reports_missing_source(tmp_path):
    op = SortOperation(tmp_path / "nie_ma.txt", tmp_path / "D" / "nie_ma.txt")
    count, errors = execute_sort_plan([op])
    assert count == 0 and len(errors) == 1


def test_history_undo_roundtrip_and_persistence(tmp_path):
    folder = tmp_path / "w"
    folder.mkdir()
    (folder / "a.jpg").write_text("1")
    (folder / "b.pdf").write_text("2")
    history = OperationHistory(tmp_path / "h.json")
    result = execute_moves(create_sort_plan(folder))
    batch = history.record_batch("sort", result.moved)
    assert batch is not None and len(history) == 1

    reloaded = OperationHistory(tmp_path / "h.json")      # zapis na dysku
    assert len(reloaded) == 1
    undo = reloaded.undo(batch.batch_id)
    assert undo.restored == 2
    assert (folder / "a.jpg").exists() and (folder / "b.pdf").exists()
    assert not (folder / "Obrazy").exists()               # puste foldery sprzątane
    assert reloaded.batches()[0].undone
    with pytest.raises(ValueError):                       # drugi raz nie wolno
        reloaded.undo(batch.batch_id)


def test_history_empty_batch_and_limit(tmp_path):
    history = OperationHistory(tmp_path / "h.json", max_batches=2)
    assert history.record_batch("sort", []) is None
    for index in range(4):
        f = tmp_path / f"{index}.txt"
        f.write_text("x")
        history.record_batch("sort", [SortOperation(f, tmp_path / "D" / f.name)])
    assert len(history) == 2
    with pytest.raises(ValueError):
        history.max_batches = 0


def test_history_survives_corrupt_file(tmp_path):
    path = tmp_path / "h.json"
    path.write_text("{ to nie jest json", encoding="utf-8")
    assert len(OperationHistory(path)) == 0


def test_settings_validation():
    s = Settings()
    with pytest.raises(ValueError):
        s.workers = 0
    with pytest.raises(ValueError):
        s.hash_mode = "gpu"
    with pytest.raises(ValueError):
        s.min_duplicate_size = -1
    with pytest.raises(ValueError):
        s.exclude_pattern = "(["
    s.exclude_pattern = ""
    assert s.compiled_exclude is None


def test_settings_save_load_roundtrip(tmp_path):
    path = tmp_path / "s.json"
    s = Settings(workers=2, hash_mode="thread", group_by_date=True, path=path)
    s.save()
    loaded = Settings.load(path)
    assert (loaded.workers, loaded.hash_mode, loaded.group_by_date) == (2, "thread", True)


def test_settings_load_tolerates_garbage(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"workers": -5, "hash_mode": "x"}), encoding="utf-8")
    loaded = Settings.load(path)
    assert loaded.workers >= 1 and loaded.hash_mode in ("process", "thread", "sequential")
    path.write_text("śmieci", encoding="utf-8")
    assert Settings.load(path).workers >= 1


def test_analyze_space(messy_folder):
    report = analyze_space(messy_folder, top_n=2)
    assert report.file_count == 6
    assert report.total_bytes == 3000 * 4 + 2000 + 1
    assert len(report.largest) == 2 and report.largest[0][1] == 3000
    assert report.by_category["Dokumenty"] == 3000 * 4 + 1
    assert report.top_extensions(1)[0][0] == ".txt"
    assert analyze_space.last_duration >= 0


def test_fs_helpers(tmp_path):
    assert ensure_directory(tmp_path) == tmp_path.resolve()
    assert format_size(0).endswith(" B")
    assert "KB" in format_size(2048) and "MB" in format_size(5 * 1024**2)
