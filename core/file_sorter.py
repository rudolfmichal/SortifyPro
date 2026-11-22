"""Utilities for safely organizing files by extension (and optionally by date)."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import shutil

from core.patterns import extract_date
from utils.decorators import measure_time, require_directory, retry

logger = logging.getLogger(__name__)

# Kategorie i przypisane do nich rozszerzenia.
FILE_CATEGORIES = {
    "Obrazy": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"},
    "Dokumenty": {".pdf", ".doc", ".docx", ".txt", ".odt", ".xlsx", ".csv"},
    "Muzyka": {".mp3", ".wav", ".flac", ".aac", ".ogg"},
    "Wideo": {".mp4", ".avi", ".mkv", ".mov", ".wmv"},
    "Archiwa": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Programowanie": {".py", ".cpp", ".c", ".h", ".java", ".js", ".html", ".css"},
}


@dataclass(frozen=True)
class SortOperation:
    """Describes one planned (or executed) file move."""

    source: Path
    destination: Path


@dataclass
class MoveResult:
    """Outcome of :func:`execute_moves`."""

    moved: list[SortOperation] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def moved_count(self) -> int:
        """Number of files that were moved successfully."""
        return len(self.moved)


def get_category(file_path: Path) -> str:
    """Return a category based on the file extension."""
    extension = file_path.suffix.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "Inne"


def get_unique_path(path: Path) -> Path:
    """Return a destination path that does not overwrite an existing file."""
    if not path.exists():
        return path

    counter = 1

    while True:
        new_path = path.with_name(f"{path.stem}_{counter}{path.suffix}")

        if not new_path.exists():
            return new_path

        counter += 1


@measure_time
@require_directory
def create_sort_plan(folder: Path, group_by_date: bool = False) -> list[SortOperation]:
    """Create a sorting plan without moving or modifying any files.

    Args:
        folder: folder whose top-level files are sorted.
        group_by_date: when a file name contains a date (``IMG_20240315.jpg``),
            put the file into a ``<category>/<YYYY-MM>`` sub-folder.
    """
    root = folder
    plan = []

    # Na pierwszym etapie sortujemy tylko pliki bezpośrednio w folderze.
    for file_path in root.iterdir():
        if not file_path.is_file():
            continue

        category_folder = root / get_category(file_path)
        if group_by_date:
            found = extract_date(file_path.name)
            if found is not None:
                category_folder = category_folder / f"{found:%Y-%m}"

        destination = get_unique_path(category_folder / file_path.name)
        plan.append(SortOperation(source=file_path, destination=destination))

    return plan


@retry(attempts=3, delay=0.2, exceptions=(PermissionError,))
def move_file(source: Path, destination: Path) -> None:
    """Move one file; transient ``PermissionError`` (e.g. antivirus) is retried."""
    shutil.move(str(source), str(destination))


def execute_moves(plan: list[SortOperation]) -> MoveResult:
    """Execute an approved plan without overwriting existing files.

    Returns the operations that really happened (with the *final*
    destination paths), which is what the history needs to undo them.
    """
    result = MoveResult()

    for operation in plan:
        try:
            if not operation.source.is_file():
                result.errors.append(f"Plik nie istnieje: {operation.source.name}")
                continue

            operation.destination.parent.mkdir(parents=True, exist_ok=True)

            # Dodatkowa ochrona przed nadpisaniem.
            destination = get_unique_path(operation.destination)
            move_file(operation.source, destination)
            result.moved.append(SortOperation(operation.source, destination))

        except OSError as error:
            logger.warning("Nie przeniesiono %s: %s", operation.source, error)
            result.errors.append(f"{operation.source.name}: {error}")

    return result


def execute_sort_plan(plan: list[SortOperation]) -> tuple[int, list[str]]:
    """Execute an approved plan; returns ``(moved_count, errors)``."""
    result = execute_moves(plan)
    return result.moved_count, result.errors
