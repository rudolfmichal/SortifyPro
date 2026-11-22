"""GIL benchmark: sequential vs. threads vs. processes.

Three workloads show how the Global Interpreter Lock shapes the results:

* **I/O wait**              - ``time.sleep`` releases the GIL      -> threads win,
* **CPU in pure Python**    - the GIL is held the whole time        -> only processes help,
* **CPU inside C (SHA-256)**- ``hashlib`` releases the GIL on big buffers -> threads help too.

Run it with::

    python main.py benchmark                   # prints a table
    python main.py benchmark --write-readme    # fills the results section of README.md
    python main.py benchmark --chart benchmarks/results/gil.png

The measured time of the *process* mode includes starting the worker
processes - exactly what a real program pays.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from core.concurrency import parallel_map

IO_DELAY_SECONDS = 0.05
PYTHON_BYTES = 1_000_000  # the pure-Python loop only processes the first ~1 MB
MODES = ("sequential", "thread", "process")
MODE_LABELS = {"sequential": "sekwencyjnie", "thread": "wątki", "process": "procesy"}

README_START = "<!-- BENCHMARK:START -->"
README_END = "<!-- BENCHMARK:END -->"


# --------------------------------------------------------------------------- #
# Workloads (module level => picklable for the process pool)
# --------------------------------------------------------------------------- #
def io_task(path: Path) -> int:
    """Simulate waiting for a slow disk / network (releases the GIL)."""
    time.sleep(IO_DELAY_SECONDS)
    return path.stat().st_size


def python_checksum_task(path: Path) -> int:
    """Adler-32 written in pure Python: a CPU-bound loop that holds the GIL."""
    with path.open("rb") as handle:
        data = handle.read(PYTHON_BYTES)
    a, b = 1, 0
    for byte in data:
        a = (a + byte) % 65521
        b = (b + a) % 65521
    return (b << 16) | a


def sha256_task(path: Path) -> str:
    """SHA-256 of a file; ``hashlib`` releases the GIL for large buffers."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


SCENARIOS: dict[str, Callable[[Path], object]] = {
    "I/O (symulowane oczekiwanie)": io_task,
    "CPU - czysty Python (Adler-32)": python_checksum_task,
    "CPU w bibliotece C (SHA-256)": sha256_task,
}


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkRow:
    """Best time of one scenario in one execution mode."""

    scenario: str
    mode: str
    seconds: float
    speedup: float  # relative to the sequential run of the same scenario


@dataclass
class BenchmarkReport:
    """All measurements plus a description of the machine."""

    system: dict[str, object] = field(default_factory=dict)
    rows: list[BenchmarkRow] = field(default_factory=list)


def describe_system(workers: int, file_count: int, size_mb: float) -> dict[str, object]:
    """Collect facts needed to interpret the numbers."""
    gil_enabled = True
    if hasattr(sys, "_is_gil_enabled"):  # Python 3.13+
        gil_enabled = bool(sys._is_gil_enabled())
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": f"{platform.system()} {platform.release()}",
        "cpu_count": os.cpu_count(),
        "gil_enabled": gil_enabled,
        "workers": workers,
        "files": file_count,
        "file_size_mb": size_mb,
    }


def generate_test_files(directory: Path, count: int, size_bytes: int) -> list[Path]:
    """Create ``count`` files filled with random data."""
    paths = []
    for index in range(count):
        path = directory / f"sample_{index:02d}.bin"
        path.write_bytes(os.urandom(size_bytes))
        paths.append(path)
    return paths


def _time_once(
    func: Callable[[Path], object], paths: Sequence[Path], mode: str, workers: int
) -> float:
    started = time.perf_counter()
    outcomes = parallel_map(func, list(paths), mode, workers, allow_fallback=False)
    elapsed = time.perf_counter() - started
    failed = [o for o in outcomes if not o.ok]
    if failed:
        raise RuntimeError(f"{func.__name__} ({mode}): {failed[0].error}")
    return elapsed


def run_benchmark(
    file_count: int = 8,
    size_mb: float = 8,
    workers: int | None = None,
    repeats: int = 3,
    on_step: Callable[[str], None] | None = None,
) -> BenchmarkReport:
    """Measure every scenario in every mode and keep the best of ``repeats``."""
    if file_count < 1 or repeats < 1:
        raise ValueError("file_count i repeats muszą być >= 1")
    workers = workers or min(file_count, os.cpu_count() or 2)
    report = BenchmarkReport(system=describe_system(workers, file_count, size_mb))

    with tempfile.TemporaryDirectory(prefix="sortify_bench_") as tmp:
        paths = generate_test_files(Path(tmp), file_count, int(size_mb * 1024 * 1024))
        for scenario, func in SCENARIOS.items():
            baseline = 0.0
            for mode in MODES:
                if on_step:
                    on_step(f"{scenario} - {MODE_LABELS[mode]}")
                best = min(_time_once(func, paths, mode, workers) for _ in range(repeats))
                if mode == "sequential":
                    baseline = best
                report.rows.append(
                    BenchmarkRow(scenario, mode, best, baseline / best if best else 0.0)
                )
    return report


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def format_markdown(report: BenchmarkReport) -> str:
    """Render the results as a Markdown table with a machine description."""
    s = report.system
    gil = "włączony" if s["gil_enabled"] else "wyłączony (free-threaded)"
    lines = [
        f"Środowisko: {s['implementation']} {s['python']}, {s['system']}, "
        f"rdzeni CPU: {s['cpu_count']}, GIL: {gil}. "
        f"Zadań: {s['files']} plików po {s['file_size_mb']} MB, workerów: {s['workers']}.",
        "",
        "| Scenariusz | Sekwencyjnie | Wątki | Procesy |",
        "|---|---|---|---|",
    ]
    for scenario in SCENARIOS:
        cells = []
        for mode in MODES:
            row = next(r for r in report.rows if r.scenario == scenario and r.mode == mode)
            suffix = "" if mode == "sequential" else f" (x{row.speedup:.2f})"
            cells.append(f"{row.seconds:.2f} s{suffix}")
        lines.append(f"| {scenario} | " + " | ".join(cells) + " |")
    lines += ["", "W nawiasach: przyspieszenie względem wykonania sekwencyjnego."]
    return "\n".join(lines)


def write_to_readme(report: BenchmarkReport, readme: Path) -> None:
    """Replace the text between the benchmark markers in ``readme``."""
    text = readme.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(README_START) + r".*?" + re.escape(README_END), re.DOTALL
    )
    if not pattern.search(text):
        raise ValueError(f"Brak znaczników {README_START} / {README_END} w {readme}")
    block = f"{README_START}\n{format_markdown(report)}\n{README_END}"
    readme.write_text(pattern.sub(lambda _m: block, text), encoding="utf-8")


def save_chart(report: BenchmarkReport, path: Path) -> bool:
    """Save a grouped bar chart; returns ``False`` if matplotlib is missing."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    scenarios = list(SCENARIOS)
    width = 0.25
    figure, axis = plt.subplots(figsize=(10, 5))
    for offset, mode in enumerate(MODES):
        values = [
            next(r.seconds for r in report.rows if r.scenario == s and r.mode == mode)
            for s in scenarios
        ]
        positions = [i + (offset - 1) * width for i in range(len(scenarios))]
        axis.bar(positions, values, width, label=MODE_LABELS[mode])
    axis.set_xticks(range(len(scenarios)))
    axis.set_xticklabels(scenarios, fontsize=9)
    axis.set_ylabel("czas [s] (mniej = lepiej)")
    axis.set_title("Wpływ GIL: sekwencyjnie vs wątki vs procesy")
    axis.legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=130)
    plt.close(figure)
    return True


def build_parser(parser: argparse.ArgumentParser | None = None) -> argparse.ArgumentParser:
    """Arguments shared by ``python main.py benchmark`` and ``-m benchmarks...``."""
    parser = parser or argparse.ArgumentParser(description="Benchmark GIL")
    parser.add_argument("--files", type=int, default=8, help="liczba plików (domyślnie 8)")
    parser.add_argument("--size-mb", type=float, default=8, help="rozmiar pliku w MB")
    parser.add_argument("--workers", type=int, default=None, help="liczba workerów")
    parser.add_argument("--repeats", type=int, default=3, help="liczba powtórzeń (best-of)")
    parser.add_argument("--chart", type=Path, help="zapisz wykres PNG (wymaga matplotlib)")
    parser.add_argument("--json", type=Path, help="zapisz surowe wyniki jako JSON")
    parser.add_argument(
        "--write-readme", action="store_true", help="wstaw tabelę do README.md"
    )
    return parser


def run_from_args(args: argparse.Namespace) -> int:
    """Execute the benchmark described by parsed ``args``."""
    print("Trwa pomiar - to może zająć kilkadziesiąt sekund...")
    report = run_benchmark(
        args.files, args.size_mb, args.workers, args.repeats,
        on_step=lambda step: print(f"  {step}"),
    )
    print()
    print(format_markdown(report))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {"system": report.system, "rows": [asdict(r) for r in report.rows]},
                indent=2, ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    if args.chart:
        if save_chart(report, args.chart):
            print(f"\nWykres zapisano: {args.chart}")
        else:
            print("\nBrak matplotlib - pomijam wykres (pip install matplotlib).")
    if args.write_readme:
        readme = Path(__file__).resolve().parent.parent / "README.md"
        write_to_readme(report, readme)
        print(f"\nTabela zapisana w {readme}")
    return 0


if __name__ == "__main__":
    sys.exit(run_from_args(build_parser().parse_args()))
