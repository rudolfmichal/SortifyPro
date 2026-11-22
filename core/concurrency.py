"""Concurrency helpers: thread pool with a Queue, process pool and progress.

* :func:`threaded_map` - producer/consumer on :class:`queue.Queue`; results
  are collected under a :class:`threading.Lock`. Best for I/O-bound work.
* :func:`parallel_map` - one entry point for ``sequential`` / ``thread`` /
  ``process`` execution so the three strategies can be compared.
* :class:`ProgressCounter` - thread-safe, throttled progress reporting.

Functions passed to the *process* mode must be defined at module level
(they are pickled and sent to the worker processes).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from typing import Callable, Final, Generic, Iterable, Sequence, TypeVar

from core.iterators import BatchIterator

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")

ProgressCallback = Callable[[int, int], None]

MODES: Final = ("process", "thread", "sequential")
_SENTINEL: Final = object()


@dataclass(frozen=True)
class TaskResult(Generic[T, R]):
    """Outcome of processing one item. ``error`` holds a text, not an exception,
    because results travel between processes and must stay picklable."""

    item: T
    value: R | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        """``True`` when the item was processed without an error."""
        return self.error is None


class ProgressCounter:
    """Thread-safe counter that reports progress at most every ``min_interval`` s.

    The callback runs while the internal lock is held (so updates arrive in
    order) and therefore has to be fast - e.g. just schedule a UI update.
    """

    def __init__(
        self,
        total: int,
        callback: ProgressCallback | None = None,
        min_interval: float = 0.1,
    ) -> None:
        self._lock = threading.Lock()
        self._done = 0
        self._total = total
        self._callback = callback
        self._min_interval = min_interval
        self._last_emit = 0.0

    @property
    def done(self) -> int:
        """Items finished so far."""
        with self._lock:
            return self._done

    @property
    def total(self) -> int:
        """Items expected in total."""
        return self._total

    def increment(self, amount: int = 1) -> int:
        """Register finished work and return the new total of finished items."""
        with self._lock:
            self._done += amount
            done = self._done
            if self._callback is not None:
                now = time.monotonic()
                if done >= self._total or now - self._last_emit >= self._min_interval:
                    self._last_emit = now
                    self._callback(done, self._total)
            return done


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def threaded_map(
    func: Callable[[T], R],
    items: Iterable[T],
    workers: int = 4,
    progress: ProgressCounter | None = None,
    cancel: threading.Event | None = None,
) -> list[TaskResult[T, R]]:
    """Apply ``func`` to ``items`` using ``workers`` threads.

    A *producer* thread feeds a bounded :class:`queue.Queue` (so ``items``
    may be a lazy generator) and ``workers`` *consumers* process the tasks.
    Results are appended under a :class:`threading.Lock`; the order of the
    returned list is therefore not guaranteed. Exceptions raised by ``func``
    are captured in :attr:`TaskResult.error`.
    """
    if workers < 1:
        raise ValueError("workers musi być >= 1")

    tasks: queue.Queue[object] = queue.Queue(maxsize=workers * 4)
    results: list[TaskResult[T, R]] = []
    results_lock = threading.Lock()
    producer_errors: list[BaseException] = []

    def producer() -> None:
        try:
            for item in items:
                if cancel is not None and cancel.is_set():
                    break
                tasks.put(item)
        except BaseException as error:  # noqa: BLE001 - re-raised in the caller
            producer_errors.append(error)
        finally:
            for _ in range(workers):
                tasks.put(_SENTINEL)

    def consumer() -> None:
        while True:
            item = tasks.get()
            if item is _SENTINEL:
                return
            if cancel is not None and cancel.is_set():
                continue  # drain the queue so the producer is never blocked
            try:
                outcome: TaskResult[T, R] = TaskResult(item, value=func(item))  # type: ignore[arg-type]
            except Exception as error:  # noqa: BLE001 - reported per item
                outcome = TaskResult(item, error=_describe(error))  # type: ignore[arg-type]
            with results_lock:
                results.append(outcome)
            if progress is not None:
                progress.increment()

    threads = [threading.Thread(target=producer, name="producer", daemon=True)]
    threads += [
        threading.Thread(target=consumer, name=f"worker-{i}", daemon=True)
        for i in range(workers)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if producer_errors:
        raise producer_errors[0]
    return results


def _run_batch(func: Callable[[T], R], batch: list[T]) -> list[TaskResult[T, R]]:
    """Process a batch inside a worker process (module level => picklable)."""
    outcomes: list[TaskResult[T, R]] = []
    for item in batch:
        try:
            outcomes.append(TaskResult(item, value=func(item)))
        except Exception as error:  # noqa: BLE001
            outcomes.append(TaskResult(item, error=_describe(error)))
    return outcomes


def _process_map(
    func: Callable[[T], R],
    items: Sequence[T],
    workers: int,
    progress: ProgressCounter | None,
    cancel: threading.Event | None,
) -> list[TaskResult[T, R]]:
    results: list[TaskResult[T, R]] = []
    batch_size = max(1, min(64, len(items) // (workers * 4)))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_run_batch, func, batch)
            for batch in BatchIterator(items, batch_size)
        ]
        for future in as_completed(futures):
            if cancel is not None and cancel.is_set():
                for pending in futures:
                    pending.cancel()
                break
            batch_results = future.result()
            results.extend(batch_results)
            if progress is not None:
                progress.increment(len(batch_results))
    return results


def _sequential_map(
    func: Callable[[T], R],
    items: Sequence[T],
    progress: ProgressCounter | None,
    cancel: threading.Event | None,
) -> list[TaskResult[T, R]]:
    results: list[TaskResult[T, R]] = []
    for item in items:
        if cancel is not None and cancel.is_set():
            break
        try:
            results.append(TaskResult(item, value=func(item)))
        except Exception as error:  # noqa: BLE001
            results.append(TaskResult(item, error=_describe(error)))
        if progress is not None:
            progress.increment()
    return results


def parallel_map(
    func: Callable[[T], R],
    items: Sequence[T],
    mode: str = "thread",
    workers: int = 4,
    progress: ProgressCounter | None = None,
    cancel: threading.Event | None = None,
    allow_fallback: bool = True,
) -> list[TaskResult[T, R]]:
    """Run ``func`` over ``items`` sequentially, in threads or in processes.

    If process creation is impossible (restricted environment, broken pool)
    and ``allow_fallback`` is set, the work is repeated using threads.

    Raises:
        ValueError: ``mode`` is not one of :data:`MODES`.
    """
    if mode not in MODES:
        raise ValueError(f"Nieznany tryb {mode!r}; dostępne: {', '.join(MODES)}")
    if mode == "sequential" or not items:
        return _sequential_map(func, items, progress, cancel)
    if mode == "thread":
        return threaded_map(func, items, workers, progress, cancel)

    try:
        return _process_map(func, items, workers, progress, cancel)
    except (BrokenProcessPool, OSError, NotImplementedError) as error:
        if not allow_fallback:
            raise
        logger.warning("Procesy niedostępne (%s) - używam wątków.", error)
        if progress is not None:
            progress = ProgressCounter(progress.total, None)
        return threaded_map(func, items, workers, progress, cancel)
