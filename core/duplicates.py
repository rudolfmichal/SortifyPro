"""Duplicate file detection.

The search narrows the candidates in three cheap-to-expensive stages:

1. **scan**    - lazy generator pipeline, files grouped by size;
2. **partial** - SHA-256 of the first 64 KiB of every candidate. This is
   latency-bound *I/O*, so it runs on a thread pool (``Queue`` + ``Lock``);
3. **full**    - SHA-256 of the whole file. This is the CPU-heavy part and
   runs in a process pool by default (``thread`` / ``sequential`` are
   available for comparison - see ``benchmarks/gil_benchmark.py``).
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from core.concurrency import MODES, ProgressCounter, parallel_map, threaded_map
from core.file_sorter import MoveResult, SortOperation, execute_moves, get_unique_path
from core.generators import (
    DEFAULT_SKIP_DIRS,
    files_at_least,
    filter_by_pattern,
    group_by_size,
    iter_files,
    with_sizes,
)
from core.iterators import ChunkReader
from core.patterns import is_copy_name
from utils.decorators import log_call, non_reentrant
from utils.fs import ensure_directory

if TYPE_CHECKING:  # avoid a runtime import cycle with core.settings
    from core.history import OperationHistory
    from core.settings import Settings

logger = logging.getLogger(__name__)

PARTIAL_BYTES = 64 * 1024
DUPLICATES_DIR_NAME = "_Duplikaty"

#: ``callback(stage, done, total)`` with stage in {"scan", "partial", "full"}.
StageCallback = Callable[[str, int, int], None]


# Module-level functions so they can be pickled and sent to worker processes.
def hash_partial(path: Path) -> str:
    """SHA-256 of the first :data:`PARTIAL_BYTES` bytes of a file."""
    with ChunkReader(path, chunk_size=PARTIAL_BYTES) as reader:
        first_block = next(reader, b"")
    return hashlib.sha256(first_block).hexdigest()


def hash_file(path: Path) -> str:
    """SHA-256 of the whole file, read block by block."""
    digest = hashlib.sha256()
    with ChunkReader(path) as reader:
        for block in reader:
            digest.update(block)
    return digest.hexdigest()


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return float("inf")


def order_by_originality(paths: list[Path]) -> list[Path]:
    """Sort identical files so that the most likely *original* comes first.

    Names that do not look like copies (``photo (1)``, ``photo - Kopia``) win,
    then shallower paths, then older files.
    """
    return sorted(
        paths,
        key=lambda p: (is_copy_name(p.stem), len(p.parts), _mtime(p), str(p)),
    )


@dataclass(frozen=True)
class DuplicateGroup:
    """Files with identical content. ``files[0]`` is the suggested original."""

    digest: str
    size: int
    files: tuple[Path, ...]

    @property
    def original(self) -> Path:
        """The file that is kept."""
        return self.files[0]

    @property
    def duplicates(self) -> tuple[Path, ...]:
        """Everything except the original."""
        return self.files[1:]

    @property
    def wasted_bytes(self) -> int:
        """Space occupied by the redundant copies."""
        return self.size * (len(self.files) - 1)


@dataclass
class DuplicateReport:
    """Result of a duplicate search."""

    root: Path
    mode: str
    groups: list[DuplicateGroup] = field(default_factory=list)
    scanned_files: int = 0
    hashed_files: int = 0
    errors: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    cancelled: bool = False

    @property
    def duplicate_count(self) -> int:
        """Number of redundant files (originals not counted)."""
        return sum(len(group.duplicates) for group in self.groups)

    @property
    def wasted_bytes(self) -> int:
        """Total space that could be reclaimed."""
        return sum(group.wasted_bytes for group in self.groups)


class DuplicateFinder:
    """Finds duplicate files below a folder."""

    def __init__(
        self,
        workers: int = 4,
        mode: str = "process",
        min_size: int = 1024,
        exclude: re.Pattern[str] | None = None,
    ) -> None:
        self._run_lock = threading.Lock()  # used by @non_reentrant
        self.workers = workers
        self.mode = mode
        self.min_size = min_size
        self.exclude = exclude

    # -- configuration --------------------------------------------------------
    @property
    def workers(self) -> int:
        """Number of threads / processes."""
        return self._workers

    @workers.setter
    def workers(self, value: int) -> None:
        if value < 1:
            raise ValueError("workers musi być >= 1")
        self._workers = value

    @property
    def mode(self) -> str:
        """Execution strategy of the full-hash stage."""
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if not self.is_valid_mode(value):
            raise ValueError(f"Nieznany tryb {value!r}; dostępne: {', '.join(MODES)}")
        self._mode = value

    @staticmethod
    def is_valid_mode(mode: str) -> bool:
        """Return ``True`` for ``process``, ``thread`` and ``sequential``."""
        return mode in MODES

    @classmethod
    def from_settings(cls, settings: Settings) -> DuplicateFinder:
        """Build a finder configured from the user's :class:`Settings`."""
        return cls(
            workers=settings.workers,
            mode=settings.hash_mode,
            min_size=settings.min_duplicate_size,
            exclude=settings.compiled_exclude,
        )

    # -- the search ------------------------------------------------------------
    @non_reentrant
    @log_call
    def find(
        self,
        folder: str | Path,
        progress: StageCallback | None = None,
        cancel: threading.Event | None = None,
    ) -> DuplicateReport:
        """Search ``folder`` recursively and return a :class:`DuplicateReport`."""
        root = ensure_directory(folder)
        report = DuplicateReport(root=root, mode=self.mode)
        emit: StageCallback = progress or (lambda stage, done, total: None)

        def cancelled() -> bool:
            return cancel is not None and cancel.is_set()

        # Stage 1: lazy pipeline of generators, grouped by size.
        started = time.perf_counter()
        pipeline = files_at_least(
            with_sizes(
                filter_by_pattern(
                    iter_files(root, skip_dirs=DEFAULT_SKIP_DIRS), self.exclude
                )
            ),
            self.min_size,
        )
        by_size = group_by_size(pipeline)
        report.scanned_files = sum(len(paths) for paths in by_size.values())
        size_of = {path: size for size, paths in by_size.items() for path in paths}
        candidates = [
            path for paths in by_size.values() if len(paths) > 1 for path in paths
        ]
        report.timings["scan"] = time.perf_counter() - started
        emit("scan", report.scanned_files, report.scanned_files)

        # Stage 2: partial hash on threads (I/O bound; Queue + Lock inside).
        started = time.perf_counter()
        partial_groups: dict[tuple[int, str], list[Path]] = defaultdict(list)
        counter = ProgressCounter(
            len(candidates), lambda done, total: emit("partial", done, total)
        )
        for outcome in threaded_map(
            hash_partial, candidates, self.workers, progress=counter, cancel=cancel
        ):
            if outcome.ok:
                partial_groups[(size_of[outcome.item], outcome.value)].append(outcome.item)
            else:
                report.errors.append(f"{outcome.item.name}: {outcome.error}")
        report.timings["partial"] = time.perf_counter() - started

        # Stage 3: full hash with the selected strategy.
        finalists = [
            path for paths in partial_groups.values() if len(paths) > 1 for path in paths
        ]
        started = time.perf_counter()
        counter = ProgressCounter(
            len(finalists), lambda done, total: emit("full", done, total)
        )
        full_groups: dict[str, list[Path]] = defaultdict(list)
        if not cancelled():
            for outcome in parallel_map(
                hash_file, finalists, self.mode, self.workers, progress=counter, cancel=cancel
            ):
                report.hashed_files += 1
                if outcome.ok:
                    full_groups[outcome.value].append(outcome.item)
                else:
                    report.errors.append(f"{outcome.item.name}: {outcome.error}")
        report.timings["full"] = time.perf_counter() - started

        for digest, paths in full_groups.items():
            if len(paths) > 1:
                ordered = order_by_originality(paths)
                report.groups.append(
                    DuplicateGroup(digest, size_of[ordered[0]], tuple(ordered))
                )
        report.groups.sort(key=lambda g: g.wasted_bytes, reverse=True)
        report.cancelled = cancelled()
        return report


def move_duplicates(
    report: DuplicateReport, history: OperationHistory | None = None
) -> MoveResult:
    """Move every redundant copy to ``<root>/_Duplikaty`` (originals stay).

    Nothing is deleted. When a ``history`` is given the batch is recorded so
    the user can undo it from the *Historia operacji* section.
    """
    target = report.root / DUPLICATES_DIR_NAME
    plan = [
        SortOperation(source, get_unique_path(target / source.name))
        for group in report.groups
        for source in group.duplicates
    ]
    result = execute_moves(plan)
    if history is not None:
        history.record_batch("duplicates", result.moved)
    return result
