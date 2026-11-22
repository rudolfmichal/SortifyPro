import threading

import pytest

from core.concurrency import ProgressCounter, parallel_map, threaded_map


def square(x):
    return x * x


def fail_on_three(x):
    if x == 3:
        raise ValueError("trzy")
    return x


@pytest.mark.parametrize("mode", ["sequential", "thread", "process"])
def test_parallel_map_all_modes(mode):
    results = parallel_map(square, list(range(20)), mode=mode, workers=2)
    assert sorted(r.value for r in results) == [i * i for i in range(20)]
    assert all(r.ok for r in results)


@pytest.mark.parametrize("mode", ["sequential", "thread", "process"])
def test_errors_are_captured_per_item(mode):
    results = parallel_map(fail_on_three, list(range(6)), mode=mode, workers=2)
    bad = [r for r in results if not r.ok]
    assert len(bad) == 1 and bad[0].item == 3 and "ValueError" in bad[0].error
    assert len(results) == 6


def test_invalid_arguments():
    with pytest.raises(ValueError):
        parallel_map(square, [1], mode="gpu")
    with pytest.raises(ValueError):
        threaded_map(square, [1], workers=0)


def test_threaded_map_accepts_generator_and_progress():
    seen = []
    progress = ProgressCounter(50, lambda d, t: seen.append((d, t)), min_interval=0)
    results = threaded_map(square, (i for i in range(50)), workers=4, progress=progress)
    assert len(results) == 50 and progress.done == 50
    assert seen[-1] == (50, 50)


def test_threaded_map_cancel():
    cancel = threading.Event()
    cancel.set()
    assert threaded_map(square, range(100), workers=2, cancel=cancel) == []


def test_progress_counter_is_thread_safe():
    counter = ProgressCounter(8000)
    threads = [
        threading.Thread(target=lambda: [counter.increment() for _ in range(2000)])
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert counter.done == 8000 and counter.total == 8000


def test_empty_items():
    assert parallel_map(square, [], mode="process") == []
