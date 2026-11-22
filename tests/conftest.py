"""Shared fixtures: every test gets its own private data directory."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def isolated_home(tmp_path_factory, monkeypatch):
    """Keep settings, history and logs out of the real home directory."""
    home = tmp_path_factory.mktemp("sortify_home")
    monkeypatch.setenv("SORTIFYPRO_HOME", str(home))
    return home


@pytest.fixture
def messy_folder(tmp_path):
    """A small folder with duplicates, a near-duplicate and a nested file."""
    (tmp_path / "a.txt").write_bytes(b"x" * 3000)
    (tmp_path / "a (1).txt").write_bytes(b"x" * 3000)
    (tmp_path / "b.txt").write_bytes(b"y" * 3000)  # same size, other content
    (tmp_path / "photo_20240315.jpg").write_bytes(b"j" * 2000)
    (tmp_path / "tiny.txt").write_bytes(b"z")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a_copy.txt").write_bytes(b"x" * 3000)
    return tmp_path
