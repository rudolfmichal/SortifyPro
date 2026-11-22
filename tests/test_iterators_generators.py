import re
import types

import pytest

from core.generators import (
    files_at_least, filter_by_pattern, group_by_size, iter_files, with_sizes,
)
from core.iterators import BatchIterator, ChunkReader


def test_chunk_reader_reads_everything(tmp_path):
    file = tmp_path / "f.bin"
    file.write_bytes(b"abcdefghij")
    with ChunkReader(file, chunk_size=4) as reader:
        chunks = list(reader)
        assert reader.bytes_read == 10
    assert chunks == [b"abcd", b"efgh", b"ij"]


def test_chunk_reader_validates_and_closes(tmp_path):
    file = tmp_path / "f.bin"
    file.write_bytes(b"a")
    with pytest.raises(ValueError):
        ChunkReader(file, chunk_size=0)
    reader = ChunkReader(file)
    assert next(reader) == b"a"
    with pytest.raises(StopIteration):
        next(reader)
    reader.close()  # idempotent


def test_chunk_reader_missing_file(tmp_path):
    with pytest.raises(OSError):
        list(ChunkReader(tmp_path / "nope"))


def test_batch_iterator():
    assert list(BatchIterator(range(7), 3)) == [[0, 1, 2], [3, 4, 5], [6]]
    assert list(BatchIterator([], 3)) == []
    with pytest.raises(ValueError):
        BatchIterator([1], 0)


def test_iter_files_is_lazy_generator_and_recursive(messy_folder):
    gen = iter_files(messy_folder)
    assert isinstance(gen, types.GeneratorType)
    names = {p.name for p in gen}
    assert "a_copy.txt" in names and "a.txt" in names


def test_iter_files_skip_dirs_and_non_recursive(messy_folder):
    assert "a_copy.txt" not in {p.name for p in iter_files(messy_folder, skip_dirs={"SUB"})}
    assert "a_copy.txt" not in {p.name for p in iter_files(messy_folder, recursive=False)}


def test_pipeline(messy_folder):
    pipeline = files_at_least(with_sizes(iter_files(messy_folder)), 1000)
    groups = group_by_size(pipeline)
    assert sorted(len(v) for v in groups.values()) == [1, 4]  # 2000 B x1, 3000 B x4


def test_filter_by_pattern(messy_folder):
    paths = list(iter_files(messy_folder))
    kept = list(filter_by_pattern(paths, re.compile(r"copy")))
    assert all("copy" not in p.name for p in kept)
    assert list(filter_by_pattern(paths, None)) == paths
