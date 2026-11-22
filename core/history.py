"""Persistent history of file operations with *undo* support."""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from core.file_sorter import SortOperation, get_unique_path, move_file
from utils.decorators import synchronized
from utils.fs import app_data_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MoveRecord:
    """One executed move, stored as text so it can be saved as JSON."""

    source: str
    destination: str


@dataclass
class HistoryBatch:
    """A group of moves performed by one user action (e.g. one sorting)."""

    batch_id: str
    timestamp: str
    action: str
    moves: list[MoveRecord] = field(default_factory=list)
    undone: bool = False

    @property
    def label(self) -> str:
        """Short human readable description."""
        names = {"sort": "Sortowanie", "duplicates": "Przeniesienie duplikatów"}
        title = names.get(self.action, self.action)
        suffix = " (cofnięte)" if self.undone else ""
        return f"{self.timestamp}  {title}: {len(self.moves)} plików{suffix}"


@dataclass
class UndoResult:
    """Outcome of :meth:`OperationHistory.undo`."""

    restored: int = 0
    errors: list[str] = field(default_factory=list)


class OperationHistory:
    """Thread-safe log of move operations stored in a JSON file."""

    def __init__(self, path: Path | None = None, max_batches: int = 50) -> None:
        self._lock = threading.RLock()  # used by @synchronized
        self._path = path or self.default_path()
        self._max_batches = 50
        self.max_batches = max_batches
        self._batches: list[HistoryBatch] = self._load()

    # -- properties / alternative constructors ---------------------------
    @staticmethod
    def default_path() -> Path:
        """Location of the history file."""
        return app_data_dir() / "history.json"

    @classmethod
    def in_folder(cls, folder: Path, **kwargs: Any) -> OperationHistory:
        """Create a history stored as ``history.json`` inside ``folder``."""
        return cls(path=Path(folder) / "history.json", **kwargs)

    @property
    def max_batches(self) -> int:
        """How many batches are kept (older ones are dropped)."""
        return self._max_batches

    @max_batches.setter
    def max_batches(self, value: int) -> None:
        if value < 1:
            raise ValueError("max_batches musi być >= 1")
        self._max_batches = value
        if hasattr(self, "_batches"):
            with self._lock:
                self._trim()
                self._save()

    # -- public API -----------------------------------------------------------
    @synchronized
    def record_batch(
        self, action: str, operations: Iterable[SortOperation]
    ) -> HistoryBatch | None:
        """Store executed moves; returns ``None`` when there is nothing to store."""
        moves = [
            MoveRecord(str(op.source), str(op.destination)) for op in operations
        ]
        if not moves:
            return None
        batch = HistoryBatch(
            batch_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action=action,
            moves=moves,
        )
        self._batches.append(batch)
        self._trim()
        self._save()
        return batch

    @synchronized
    def batches(self) -> list[HistoryBatch]:
        """All batches, newest first."""
        return list(reversed(self._batches))

    def __iter__(self) -> Iterator[HistoryBatch]:
        return iter(self.batches())

    def __len__(self) -> int:
        with self._lock:
            return len(self._batches)

    @synchronized
    def undo(self, batch_id: str) -> UndoResult:
        """Move the files of a batch back to where they came from.

        Files that vanished are reported, never overwritten; if the original
        location is occupied the file is restored under a unique name.
        """
        batch = next((b for b in self._batches if b.batch_id == batch_id), None)
        if batch is None:
            raise KeyError(f"Nie ma operacji o id {batch_id}")
        if batch.undone:
            raise ValueError("Ta operacja została już cofnięta")

        result = UndoResult()
        for move in reversed(batch.moves):
            source, current = Path(move.source), Path(move.destination)
            if not current.is_file():
                result.errors.append(f"Brak pliku do cofnięcia: {current.name}")
                continue
            try:
                target = source if not source.exists() else get_unique_path(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                move_file(current, target)
                result.restored += 1
                _prune_empty_dirs(current.parent, stop_at=_common_dir(source, current))
            except OSError as error:
                logger.warning("Nie cofnięto %s: %s", current, error)
                result.errors.append(f"{current.name}: {error}")

        batch.undone = True
        self._save()
        return result

    # -- persistence ----------------------------------------------------------
    def _trim(self) -> None:
        del self._batches[: max(0, len(self._batches) - self._max_batches)]

    def _load(self) -> list[HistoryBatch]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return [
                HistoryBatch(
                    batch_id=item["batch_id"],
                    timestamp=item["timestamp"],
                    action=item["action"],
                    moves=[MoveRecord(**m) for m in item["moves"]],
                    undone=bool(item.get("undone", False)),
                )
                for item in raw
            ][-self._max_batches:]
        except FileNotFoundError:
            return []
        except (OSError, ValueError, KeyError, TypeError) as error:
            logger.warning("Uszkodzony plik historii (%s) - zaczynam od zera.", error)
            return []

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp = self._path.with_suffix(".tmp")
            temp.write_text(
                json.dumps([asdict(b) for b in self._batches], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(temp, self._path)  # atomic: never leaves a half-written file
        except OSError as error:
            logger.warning("Nie udało się zapisać historii: %s", error)


def _common_dir(first: Path, second: Path) -> Path:
    try:
        return Path(os.path.commonpath([first.parent, second.parent]))
    except ValueError:  # different drives on Windows: nothing to prune
        return second.parent


def _prune_empty_dirs(directory: Path, stop_at: Path) -> None:
    """Remove ``directory`` and its empty parents, never going above ``stop_at``."""
    while directory != stop_at and stop_at in directory.parents:
        try:
            directory.rmdir()  # only succeeds when the folder is empty
        except OSError:
            return
        directory = directory.parent
