"""Entry point of Sortify Pro: GUI (default) and a command line interface.

Examples::

    python main.py                       # dashboard (GUI)
    python main.py demo-data             # create ./test_data
    python main.py scan test_data
    python main.py sort test_data --apply [--by-date]
    python main.py duplicates test_data --mode process --move
    python main.py space test_data
    python main.py undo --list | --last
    python main.py benchmark --write-readme --chart docs/gil.png
"""
from __future__ import annotations

import argparse
import logging
import multiprocessing
import sys
from pathlib import Path

from utils.logging_config import setup_logging

logger = logging.getLogger("sortifypro")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all sub-commands."""
    from benchmarks import gil_benchmark
    from core.concurrency import MODES

    parser = argparse.ArgumentParser(prog="sortifypro", description="Sortify Pro")
    parser.add_argument("-v", "--verbose", action="store_true", help="logi DEBUG")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="uruchom dashboard (domyślnie)")

    demo = sub.add_parser("demo-data", help="wygeneruj dane testowe")
    demo.add_argument("folder", nargs="?", type=Path, default=Path("test_data"))
    demo.add_argument("--seed", type=int, default=42)

    scan = sub.add_parser("scan", help="statystyki folderu")
    scan.add_argument("folder", type=Path)

    sort = sub.add_parser("sort", help="posortuj pliki w kategorie")
    sort.add_argument("folder", type=Path)
    sort.add_argument("--apply", action="store_true", help="wykonaj (bez tego tylko podgląd)")
    sort.add_argument("--by-date", action="store_true", help="podfoldery według daty z nazwy")

    dup = sub.add_parser("duplicates", help="znajdź duplikaty")
    dup.add_argument("folder", type=Path)
    dup.add_argument("--mode", choices=MODES, default=None)
    dup.add_argument("--workers", type=int, default=None)
    dup.add_argument("--move", action="store_true", help="przenieś kopie do _Duplikaty")

    space = sub.add_parser("space", help="analiza zajętego miejsca")
    space.add_argument("folder", type=Path)
    space.add_argument("--top", type=int, default=10)

    undo = sub.add_parser("undo", help="cofnij operację")
    undo.add_argument("--list", action="store_true", help="pokaż historię")
    undo.add_argument("--last", action="store_true", help="cofnij ostatnią operację")

    bench = sub.add_parser("benchmark", help="pomiar GIL: sekwencyjnie / wątki / procesy")
    gil_benchmark.build_parser(bench)
    return parser


def cmd_gui(_: argparse.Namespace) -> int:
    from gui.app import SortifyApp

    SortifyApp().mainloop()
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    from scripts.generate_test_data import generate

    files = generate(args.folder, args.seed)
    print(f"Utworzono {len(files)} plików w {args.folder}")
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    from core.file_scanner import scan_folder
    from utils.fs import format_size

    result = scan_folder(args.folder)
    print(f"Folder: {result.root}")
    print(f"Pliki: {result.file_count}, foldery: {result.folder_count}, "
          f"rozmiar: {format_size(result.total_bytes)}")
    for extension, count in result.extensions.most_common(10):
        print(f"  {extension or '[brak]'}: {count}")
    return 0


def cmd_sort(args: argparse.Namespace) -> int:
    from core.file_sorter import create_sort_plan, execute_moves
    from core.history import OperationHistory
    from core.settings import Settings

    settings = Settings.load()
    plan = create_sort_plan(args.folder, group_by_date=args.by_date or settings.group_by_date)
    print(f"Plan: {len(plan)} plików")
    for operation in plan[:50]:
        print(f"  {operation.source.name} -> {operation.destination.parent.name}/")
    if not args.apply:
        print("To tylko podgląd. Dodaj --apply, aby przenieść pliki.")
        return 0
    result = execute_moves(plan)
    OperationHistory().record_batch("sort", result.moved)
    print(f"Przeniesiono: {result.moved_count}, błędy: {len(result.errors)}")
    for error in result.errors:
        print(f"  ! {error}")
    return 1 if result.errors else 0


def cmd_duplicates(args: argparse.Namespace) -> int:
    from core.duplicates import DuplicateFinder, move_duplicates
    from core.history import OperationHistory
    from core.settings import Settings
    from utils.fs import format_size

    finder = DuplicateFinder.from_settings(Settings.load())
    if args.mode:
        finder.mode = args.mode
    if args.workers:
        finder.workers = args.workers
    report = finder.find(
        args.folder,
        progress=lambda stage, done, total: logger.debug("%s %d/%d", stage, done, total),
    )
    print(f"Tryb: {report.mode}, przejrzano: {report.scanned_files}, "
          f"zahashowano: {report.hashed_files}")
    for group in report.groups:
        print(f"\n[{format_size(group.size)}] oryginał: {group.original.name}")
        for copy in group.duplicates:
            print(f"    kopia: {copy.name}")
    print(f"\nDuplikaty: {report.duplicate_count}, "
          f"do odzyskania: {format_size(report.wasted_bytes)}")
    for stage, seconds in report.timings.items():
        print(f"  czas {stage}: {seconds:.3f} s")
    if args.move and report.groups:
        result = move_duplicates(report, OperationHistory())
        print(f"Przeniesiono do _Duplikaty: {result.moved_count}")
    return 0


def cmd_space(args: argparse.Namespace) -> int:
    from core.settings import Settings
    from core.space_analyzer import analyze_space
    from utils.fs import format_size

    report = analyze_space(args.folder, args.top, Settings.load().compiled_exclude)
    print(f"Plików: {report.file_count}, razem: {format_size(report.total_bytes)}")
    print("Kategorie:")
    for name, size in sorted(report.by_category.items(), key=lambda i: -i[1]):
        print(f"  {name}: {format_size(size)}")
    print(f"Największe pliki (top {args.top}):")
    for path, size in report.largest:
        print(f"  {format_size(size):>10}  {path.name}")
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    from core.history import OperationHistory

    history = OperationHistory()
    if args.list or not args.last:
        for batch in history.batches():
            print(f"{batch.batch_id[:8]}  {batch.label}")
        if not args.last:
            return 0
    active = [b for b in history.batches() if not b.undone]
    if not active:
        print("Brak operacji do cofnięcia.")
        return 0
    result = history.undo(active[-1].batch_id)
    print(f"Przywrócono: {result.restored}, błędy: {len(result.errors)}")
    for error in result.errors:
        print(f"  ! {error}")
    return 1 if result.errors else 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from benchmarks import gil_benchmark

    return gil_benchmark.run_from_args(args)


COMMANDS = {
    "gui": cmd_gui, "demo-data": cmd_demo, "scan": cmd_scan, "sort": cmd_sort,
    "duplicates": cmd_duplicates, "space": cmd_space, "undo": cmd_undo,
    "benchmark": cmd_benchmark,
}


def main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` and run the chosen command; returns the exit code."""
    args = build_parser().parse_args(argv)
    setup_logging(args.verbose)
    handler = COMMANDS[args.command or "gui"]
    try:
        return handler(args)
    except (OSError, ValueError, RuntimeError) as error:
        logger.debug("Szczegóły błędu", exc_info=True)
        print(f"Błąd: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
