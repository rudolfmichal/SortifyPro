"""Lazy file-processing pipeline built from generators.

``iter_files -> filter_by_pattern -> with_sizes -> files_at_least``

Each stage is a generator (or generator expression), so a folder with
millions of files is processed one entry at a time and never loaded into
memory as a whole list.
"""
from __future__ import annotations

import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Collection, Iterable, Iterator

logger = logging.getLogger(__name__)

#: Folders that are skipped by duplicate detection.
DEFAULT_SKIP_DIRS = frozenset(
    {"_Duplikaty", ".git", ".venv", "__pycache__", "node_modules"}
)


def iter_files(
    root: Path,
    *,
    skip_dirs: Collection[str] = frozenset(),
    recursive: bool = True,
) -> Iterator[Path]:
    """Yield every regular file below ``root`` (symlinks are ignored).

    Uses :func:`os.scandir` and ``yield from`` to delegate to the generator
    of each sub-folder. Unreadable folders are skipped silently.
    """
    folded_skip = {name.casefold() for name in skip_dirs}
    try:
        scanner = os.scandir(root)
    except OSError as error:
        logger.debug("Pomijam %s: %s", root, error)
        return

    with scanner:
        for entry in scanner:
            try:
                if entry.is_symlink():
                    continue
                is_file = entry.is_file(follow_symlinks=False)
                is_dir = not is_file and entry.is_dir(follow_symlinks=False)
            except OSError:
                continue

            if is_file:
                yield Path(entry.path)
            elif is_dir and recursive and entry.name.casefold() not in folded_skip:
                yield from iter_files(
                    Path(entry.path), skip_dirs=skip_dirs, recursive=recursive
                )


def filter_by_pattern(
    paths: Iterable[Path], exclude: re.Pattern[str] | None
) -> Iterator[Path]:
    """Drop files whose *name* matches the ``exclude`` pattern."""
    if exclude is None:
        yield from paths
        return
    for path in paths:
        if not exclude.search(path.name):
            yield path


def with_sizes(paths: Iterable[Path]) -> Iterator[tuple[Path, int]]:
    """Pair every path with its size; files that vanished are skipped."""
    for path in paths:
        try:
            yield path, path.stat().st_size
        except OSError:
            continue


def files_at_least(
    sized: Iterable[tuple[Path, int]], min_size: int
) -> Iterator[tuple[Path, int]]:
    """Keep only files that are at least ``min_size`` bytes (generator expression)."""
    return ((path, size) for path, size in sized if size >= min_size)


def group_by_size(sized: Iterable[tuple[Path, int]]) -> dict[int, list[Path]]:
    """Consume the pipeline and group paths by file size."""
    groups: dict[int, list[Path]] = defaultdict(list)
    for path, size in sized:
        groups[size].append(path)
    return dict(groups)
