"""Persistent user settings with validation."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, ClassVar

from core.concurrency import MODES
from core.patterns import DEFAULT_EXCLUDE_PATTERN, compile_exclude_pattern
from utils.fs import app_data_dir

logger = logging.getLogger(__name__)

MAX_WORKERS = 64


class Settings:
    """Application settings; every property validates the assigned value.

    Invalid values raise ``ValueError`` so that the GUI can show the message.
    """

    VALID_MODES: ClassVar[tuple[str, ...]] = MODES

    def __init__(
        self,
        workers: int | None = None,
        hash_mode: str = "process",
        min_duplicate_size: int = 1024,
        exclude_pattern: str = DEFAULT_EXCLUDE_PATTERN,
        group_by_date: bool = False,
        path: Path | None = None,
    ) -> None:
        self._path = path or self.default_path()
        self.workers = workers if workers is not None else min(8, os.cpu_count() or 2)
        self.hash_mode = hash_mode
        self.min_duplicate_size = min_duplicate_size
        self.exclude_pattern = exclude_pattern
        self.group_by_date = group_by_date

    # -- validated properties ------------------------------------------------
    @property
    def workers(self) -> int:
        """Number of worker threads / processes (1..64)."""
        return self._workers

    @workers.setter
    def workers(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("Liczba workerów musi być liczbą całkowitą")
        if not 1 <= value <= MAX_WORKERS:
            raise ValueError(f"Liczba workerów musi mieścić się w zakresie 1-{MAX_WORKERS}")
        self._workers = value

    @property
    def hash_mode(self) -> str:
        """Execution strategy of the full-hash stage: process, thread or sequential."""
        return self._hash_mode

    @hash_mode.setter
    def hash_mode(self, value: str) -> None:
        if value not in self.VALID_MODES:
            raise ValueError(f"Tryb musi być jednym z: {', '.join(self.VALID_MODES)}")
        self._hash_mode = value

    @property
    def min_duplicate_size(self) -> int:
        """Files smaller than this many bytes are ignored by duplicate search."""
        return self._min_duplicate_size

    @min_duplicate_size.setter
    def min_duplicate_size(self, value: int) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Minimalny rozmiar musi być liczbą >= 0")
        self._min_duplicate_size = value

    @property
    def exclude_pattern(self) -> str:
        """Regular expression of file names ignored by the analyses."""
        return self._exclude_pattern

    @exclude_pattern.setter
    def exclude_pattern(self, value: str) -> None:
        compile_exclude_pattern(value)  # raises ValueError when invalid
        self._exclude_pattern = value.strip()

    @property
    def compiled_exclude(self) -> re.Pattern[str] | None:
        """Compiled :attr:`exclude_pattern` (``None`` when empty)."""
        return compile_exclude_pattern(self._exclude_pattern)

    # -- persistence ---------------------------------------------------------
    @staticmethod
    def default_path() -> Path:
        """Location of the settings file."""
        return app_data_dir() / "settings.json"

    def to_dict(self) -> dict[str, Any]:
        """Serialisable representation."""
        return {
            "workers": self.workers,
            "hash_mode": self.hash_mode,
            "min_duplicate_size": self.min_duplicate_size,
            "exclude_pattern": self.exclude_pattern,
            "group_by_date": self.group_by_date,
        }

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Load settings; a missing or damaged file yields the defaults."""
        path = path or cls.default_path()
        settings = cls(path=path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return settings
        except (OSError, ValueError) as error:
            logger.warning("Nie udało się wczytać ustawień (%s) - używam domyślnych.", error)
            return settings

        if not isinstance(data, dict):
            return settings
        for key in ("workers", "hash_mode", "min_duplicate_size", "exclude_pattern"):
            if key in data:
                try:
                    setattr(settings, key, data[key])
                except ValueError as error:
                    logger.warning("Ignoruję ustawienie %s: %s", key, error)
        if isinstance(data.get("group_by_date"), bool):
            settings.group_by_date = data["group_by_date"]
        return settings

    def save(self) -> None:
        """Write settings to disk (errors are logged, never raised)."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as error:
            logger.warning("Nie udało się zapisać ustawień: %s", error)
