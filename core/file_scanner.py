"""Read-only folder scanning utilities."""
from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path

from utils.decorators import measure_time, require_directory


@dataclass(frozen=True)
class ScanResult:
    """Summary returned after scanning a directory."""
    root: Path
    file_count: int
    folder_count: int
    total_bytes: int
    extensions: Counter[str]


@measure_time
@require_directory
def scan_folder(folder: Path) -> ScanResult:
    """Scan a folder recursively without modifying its contents.

    Inaccessible files and directories are skipped. ``folder`` is validated
    (and resolved) by :func:`utils.decorators.require_directory`; the duration
    of the last call is available as ``scan_folder.last_duration``.
    """
    root = folder
    file_count = 0
    folder_count = 0
    total_bytes = 0
    extensions: Counter[str] = Counter()

    for current_path, directories, filenames in os.walk(
        root, onerror=lambda _error: None
    ):
        folder_count += len(directories)
        for filename in filenames:
            file_path = Path(current_path) / filename
            try:
                if file_path.is_file():
                    file_count += 1
                    total_bytes += file_path.stat().st_size
                    extensions[file_path.suffix.lower()] += 1
            except OSError:
                continue

    return ScanResult(
        root=root,
        file_count=file_count,
        folder_count=folder_count,
        total_bytes=total_bytes,
        extensions=extensions,
    )
