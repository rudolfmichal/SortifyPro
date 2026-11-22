"""Disk space analysis: where do the bytes go?"""
from __future__ import annotations

import heapq
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from core.file_sorter import get_category
from core.generators import filter_by_pattern, iter_files, with_sizes
from utils.decorators import measure_time, require_directory


@dataclass
class SpaceReport:
    """Aggregated disk usage of a folder."""

    root: Path
    file_count: int = 0
    total_bytes: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_extension: dict[str, int] = field(default_factory=dict)
    largest: list[tuple[Path, int]] = field(default_factory=list)

    def top_extensions(self, limit: int = 10) -> list[tuple[str, int]]:
        """Extensions that use the most space, biggest first."""
        return heapq.nlargest(limit, self.by_extension.items(), key=lambda item: item[1])


def _tally(
    sized: Iterable[tuple[Path, int]], report: SpaceReport
) -> Iterator[tuple[Path, int]]:
    """Pass-through generator that updates the totals as items flow by."""
    categories: dict[str, int] = defaultdict(int)
    extensions: dict[str, int] = defaultdict(int)
    for path, size in sized:
        report.file_count += 1
        report.total_bytes += size
        categories[get_category(path)] += size
        extensions[path.suffix.lower()] += size
        yield path, size
    report.by_category = dict(categories)
    report.by_extension = dict(extensions)


@measure_time
@require_directory
def analyze_space(
    folder: Path, top_n: int = 15, exclude: re.Pattern[str] | None = None
) -> SpaceReport:
    """Analyse a folder in a single lazy pass.

    ``heapq.nlargest`` keeps only ``top_n`` entries in memory while the
    generator pipeline streams through every file.
    """
    report = SpaceReport(root=folder)
    stream = _tally(with_sizes(filter_by_pattern(iter_files(folder), exclude)), report)
    report.largest = heapq.nlargest(top_n, stream, key=lambda item: item[1])
    return report
