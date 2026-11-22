"""Custom iterators implementing the iterator protocol (``__iter__``/``__next__``).

* :class:`ChunkReader`   - reads a binary file block by block,
* :class:`BatchIterator` - groups any iterable into lists of a fixed size.

Both are lazy and one-shot, exactly like built-in iterators.
"""
from __future__ import annotations

import itertools
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Generic, Iterable, TypeVar

T = TypeVar("T")

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class ChunkReader:
    """Iterate over a file in blocks of ``chunk_size`` bytes.

    The file is opened lazily on the first ``next()`` and closed
    automatically when it is exhausted (or via :meth:`close` / ``with``).

    >>> # for block in ChunkReader("movie.mkv"):
    >>> #     digest.update(block)
    """

    def __init__(self, path: str | Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size musi być dodatni")
        self._path = Path(path)
        self._chunk_size = chunk_size
        self._file: BinaryIO | None = None
        self._finished = False
        self._bytes_read = 0

    @property
    def chunk_size(self) -> int:
        """Size of one block in bytes."""
        return self._chunk_size

    @property
    def bytes_read(self) -> int:
        """Number of bytes returned so far."""
        return self._bytes_read

    def __iter__(self) -> ChunkReader:
        return self

    def __next__(self) -> bytes:
        if self._finished:
            raise StopIteration
        if self._file is None:
            self._file = self._path.open("rb")
        chunk = self._file.read(self._chunk_size)
        if not chunk:
            self.close()
            raise StopIteration
        self._bytes_read += len(chunk)
        return chunk

    def close(self) -> None:
        """Close the file; the iterator is exhausted afterwards."""
        if self._file is not None:
            self._file.close()
            self._file = None
        self._finished = True

    def __enter__(self) -> ChunkReader:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


class BatchIterator(Generic[T]):
    """Yield successive lists of at most ``size`` items from ``items``.

    >>> list(BatchIterator(range(5), 2))
    [[0, 1], [2, 3], [4]]
    """

    def __init__(self, items: Iterable[T], size: int) -> None:
        if size < 1:
            raise ValueError("size musi być >= 1")
        self._source = iter(items)
        self._size = size

    def __iter__(self) -> BatchIterator[T]:
        return self

    def __next__(self) -> list[T]:
        batch = list(itertools.islice(self._source, self._size))
        if not batch:
            raise StopIteration
        return batch
