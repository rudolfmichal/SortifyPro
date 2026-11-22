from pathlib import Path
from core.advanced_features import PathIterator, ScanSettings, parse_file_name, is_valid_filename, iter_file_paths, SafeCounter

def test_custom_iterator():
    it = PathIterator([Path("a"), Path("b")])
    assert next(it) == Path("a")
    assert next(it) == Path("b")

def test_regex_named_groups():
    assert parse_file_name("photo.png") == {"stem": "photo", "extension": "png"}
    assert is_valid_filename("report.pdf")


def test_generator_and_counter(tmp_path):
    (tmp_path / "one.txt").write_text("x")
    assert list(iter_file_paths(tmp_path)) == [tmp_path / "one.txt"]
    counter = SafeCounter()
    counter.increment(3)
    assert counter.value == 3

def test_property_validation():
    settings = ScanSettings()
    settings.max_workers = 3
    assert settings.max_workers == 3
    try:
        settings.max_workers = 0
    except ValueError:
        pass
    else:
        assert False, "expected ValueError"
