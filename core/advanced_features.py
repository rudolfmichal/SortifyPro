"""Advanced Python features used by Sortify Pro (course project requirements)."""
from __future__ import annotations

import functools
import logging
import re
import time
from pathlib import Path
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import cpu_count

logger = logging.getLogger(__name__)


def timed(func):
    """Decorator: log how long a function takes."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            logger.info("%s executed in %.4f s", func.__name__, time.perf_counter() - start)
    return wrapper


def retry_on_error(attempts: int = 2):
    """Parameterized decorator that retries a function after OSError."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except OSError:
                    if attempt == attempts - 1:
                        raise
        return wrapper
    return decorator


def log_method_call(method):
    """Method decorator using self to log the owning class and method."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        logger.info("Calling %s.%s", type(self).__name__, method.__name__)
        return method(self, *args, **kwargs)
    return wrapper



class ScanSettings:
    """Small settings class demonstrating validated property and class constructor."""
    DEFAULT_MAX_WORKERS = 4



    def __init__(self, max_workers: int = DEFAULT_MAX_WORKERS):
        self.max_workers = max_workers



    @property
    def max_workers(self) -> int:
        return self._max_workers



    @max_workers.setter
    def max_workers(self, value: int) -> None:
        if not isinstance(value, int) or value < 1:
            raise ValueError("max_workers must be a positive integer")
        self._max_workers = value



    @classmethod
    def default(cls) -> "ScanSettings":
        return cls(cls.DEFAULT_MAX_WORKERS)



    @staticmethod
    def is_supported_path(path: Path) -> bool:
        return isinstance(path, Path)



class PathIterator:
    """Custom iterator over paths (implements __iter__ and __next__)."""
    def __init__(self, paths):
        self._paths = iter(paths)

    def __iter__(self):
        return self

    def __next__(self) -> Path:
        return next(self._paths)



# Named-group regex for file names and extension extraction.
FILE_NAME_RE = re.compile(r"^(?P<stem>.+?)(?:\.(?P<extension>[A-Za-z0-9]+))?$", re.IGNORECASE)


def parse_file_name(filename: str) -> dict[str, str | None]:
    """Extract filename stem and extension using named regex groups."""
    match = FILE_NAME_RE.fullmatch(filename)
    if not match:
        return {"stem": filename, "extension": None}
    return match.groupdict()



# Second regex pattern: search for common image/document/media extensions in a string.
KNOWN_EXTENSION_RE = re.compile(r"\.(?P<extension>jpg|jpeg|png|gif|pdf|txt|mp3|mp4|zip|py)$", re.IGNORECASE)



def is_valid_filename(filename: str) -> bool:
    return bool(FILE_NAME_RE.fullmatch(filename))



def iter_file_paths(folder: Path):
    """Generator yielding files recursively, without loading a full list in memory."""
    for path in folder.rglob("*"):
        if path.is_file():
            yield path



class SafeCounter:
    """Thread-safe counter, protected by a Lock."""
    def __init__(self):
        self._value = 0
        self._lock = Lock()

    def increment(self, amount: int = 1) -> int:
        with self._lock:
            self._value += amount
            return self._value

    @property
    def value(self) -> int:
        with self._lock:
            return self._value



@timed
@retry_on_error(attempts=2)
def threaded_stat_files(paths: list[Path], max_workers: int = 4) -> list[int]:
    """I/O-bound example: stat file sizes using a thread pool."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(lambda path: path.stat().st_size, paths))



# CPU-bound function kept at module scope so multiprocessing can pickle it.
def cpu_work(n: int) -> int:
    total = 0
    for i in range(n):
        total += i * i
    return total



def run_gil_benchmark(n: int = 2_000_000, workers: int = 2) -> dict[str, float]:
    """Compare sequential, threaded, and process execution for CPU-bound work."""
    from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
    from time import perf_counter
    tasks = [n] * workers
    results: dict[str, float] = {}
    start = perf_counter()
    [cpu_work(task) for task in tasks]
    results["sequential"] = perf_counter() - start
    start = perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(cpu_work, tasks))
    results["threads"] = perf_counter() - start
    start = perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(cpu_work, tasks))
    results["processes"] = perf_counter() - start
    return results
