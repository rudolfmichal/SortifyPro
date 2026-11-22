"""Filesystem helpers shared by the core modules, the CLI and the GUI."""
from __future__ import annotations

import os
from pathlib import Path

_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


def ensure_directory(folder: str | Path) -> Path:
    """Return the resolved path of an existing directory.

    Raises:
        FileNotFoundError: the path does not exist.
        NotADirectoryError: the path exists but is not a directory.
    """
    root = Path(folder).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Folder nie istnieje: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"To nie jest folder: {root}")
    return root


def format_size(size_bytes: int | float) -> str:
    """Convert a number of bytes to a human readable string (e.g. ``1.5 MB``)."""
    size = float(size_bytes)
    for unit in _SIZE_UNITS[:-1]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {_SIZE_UNITS[-1]}"


def app_data_dir() -> Path:
    """Return the directory where settings, history and logs are stored.

    The location can be overridden with the ``SORTIFYPRO_HOME`` environment
    variable, which is also what the automated tests use.
    """
    override = os.environ.get("SORTIFYPRO_HOME")
    return Path(override) if override else Path.home() / ".sortifypro"
