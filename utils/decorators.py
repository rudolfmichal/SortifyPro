"""Custom decorators used across Sortify Pro.

Function decorators
    * :func:`measure_time`      - measures and logs the run time of a function,
    * :func:`retry`             - decorator *factory* (takes parameters) that
                                  retries a function after transient errors,
    * :func:`require_directory` - validates that the first argument is a folder.

Method decorators (they rely on the state stored in ``self``)
    * :func:`synchronized`   - runs a method under ``self._lock``,
    * :func:`non_reentrant`  - refuses to start a method that is already running,
    * :func:`log_call`       - logs ``ClassName.method`` calls.

Every wrapper uses :func:`functools.wraps`, so names, docstrings and other
metadata of the decorated callable are preserved.
"""
from __future__ import annotations

import functools
import logging
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from utils.fs import ensure_directory

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# --------------------------------------------------------------------------- #
# Function decorators
# --------------------------------------------------------------------------- #
def measure_time(func: F) -> F:
    """Measure how long ``func`` runs.

    The duration of the most recent call is stored in ``func.last_duration``
    (seconds) and written to the debug log.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            wrapper.last_duration = elapsed  # type: ignore[attr-defined]
            logger.debug("[%s] wykonano w %.4f s", func.__name__, elapsed)

    wrapper.last_duration = 0.0  # type: ignore[attr-defined]
    return wrapper  # type: ignore[return-value]


def retry(
    attempts: int = 3,
    delay: float = 0.1,
    exceptions: tuple[type[BaseException], ...] = (OSError,),
) -> Callable[[F], F]:
    """Return a decorator that retries ``func`` when it raises ``exceptions``.

    Args:
        attempts: total number of calls before giving up (>= 1).
        delay: base pause in seconds; it grows linearly with every attempt.
        exceptions: exception types treated as transient.

    The last exception is re-raised unchanged, so callers can keep using
    their usual ``except OSError`` handlers.
    """
    if attempts < 1:
        raise ValueError("attempts musi być >= 1")

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as error:
                    if attempt == attempts:
                        raise
                    logger.warning(
                        "%s: próba %d/%d nieudana (%s)",
                        func.__name__, attempt, attempts, error,
                    )
                    time.sleep(delay * attempt)
            raise AssertionError("unreachable")  # pragma: no cover

        return wrapper  # type: ignore[return-value]

    return decorator


def require_directory(func: F) -> F:
    """Validate the first argument and pass the *resolved* directory on.

    Raises ``FileNotFoundError`` / ``NotADirectoryError`` before the decorated
    function runs, so the function body can assume a valid folder.
    """

    @functools.wraps(func)
    def wrapper(folder: str | Path, *args: Any, **kwargs: Any) -> Any:
        return func(ensure_directory(folder), *args, **kwargs)

    return wrapper  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Method decorators
# --------------------------------------------------------------------------- #
def synchronized(method: F) -> F:
    """Run an instance method while holding ``self._lock`` (an ``RLock``)."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


def non_reentrant(method: F) -> F:
    """Refuse to run a method again while the previous call is unfinished.

    The instance must provide a ``threading.Lock`` called ``_run_lock``.
    A second concurrent call raises ``RuntimeError`` instead of blocking.
    """

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError(
                f"{type(self).__name__}.{method.__name__}: operacja jest już w toku"
            )
        try:
            return method(self, *args, **kwargs)
        finally:
            self._run_lock.release()

    return wrapper  # type: ignore[return-value]


def log_call(method: F) -> F:
    """Log every call of an instance method as ``ClassName.method``."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        logger.debug("%s.%s wywołana", type(self).__name__, method.__name__)
        return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]
