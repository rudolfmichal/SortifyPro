import threading

import pytest

from utils.decorators import (
    log_call, measure_time, non_reentrant, require_directory, retry, synchronized,
)


def test_measure_time_keeps_metadata_and_stores_duration():
    @measure_time
    def work(x):
        """doc"""
        return x * 2

    assert work(2) == 4
    assert work.__name__ == "work" and work.__doc__ == "doc"
    assert work.last_duration >= 0


def test_retry_succeeds_after_failures():
    calls = []

    @retry(attempts=3, delay=0, exceptions=(OSError,))
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise OSError("boom")
        return "ok"

    assert flaky() == "ok" and len(calls) == 3


def test_retry_reraises_last_error_and_ignores_other_exceptions():
    @retry(attempts=2, delay=0)
    def always():
        raise OSError("x")

    with pytest.raises(OSError):
        always()

    @retry(attempts=3, delay=0)
    def other():
        raise KeyError("k")

    with pytest.raises(KeyError):
        other()


def test_retry_validates_attempts():
    with pytest.raises(ValueError):
        retry(attempts=0)


def test_require_directory(tmp_path):
    @require_directory
    def name(folder):
        return folder.name

    assert name(tmp_path) == tmp_path.name
    with pytest.raises(FileNotFoundError):
        name(tmp_path / "missing")
    file = tmp_path / "f.txt"
    file.write_text("x")
    with pytest.raises(NotADirectoryError):
        name(file)


class Box:
    def __init__(self):
        self._lock = threading.RLock()
        self._run_lock = threading.Lock()
        self.value = 0

    @synchronized
    def add(self):
        current = self.value
        self.value = current + 1

    @non_reentrant
    @log_call
    def slow(self, started, release):
        started.set()
        release.wait(2)
        return "done"


def test_synchronized_is_thread_safe():
    box = Box()
    threads = [
        threading.Thread(target=lambda: [box.add() for _ in range(2000)])
        for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert box.value == 8000
    assert Box.add.__name__ == "add"


def test_non_reentrant_rejects_second_call():
    box = Box()
    started, release = threading.Event(), threading.Event()
    out = []
    t = threading.Thread(target=lambda: out.append(box.slow(started, release)))
    t.start()
    assert started.wait(2)
    with pytest.raises(RuntimeError):
        box.slow(started, release)
    release.set()
    t.join()
    assert out == ["done"]
    assert box.slow(started, release) == "done"  # lock released afterwards
