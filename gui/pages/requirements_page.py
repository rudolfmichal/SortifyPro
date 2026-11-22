"""Overview of the lecturer's requirements and where each one lives in the code."""
from __future__ import annotations

import customtkinter as ctk

from gui.widgets import page_header, set_textbox

#: (requirement, where it is implemented, where the user can see it)
REQUIREMENTS: tuple[tuple[str, str, str], ...] = (
    ("1. Dekoratory funkcji (>=2, z parametrami, wraps)",
     "utils/decorators.py: measure_time, retry(attempts, delay), require_directory",
     "scan_folder, create_sort_plan, move_file, analyze_space"),
    ("2. Dekoratory metod + property/classmethod/staticmethod",
     "utils/decorators.py: synchronized, non_reentrant, log_call; core/settings.py, core/duplicates.py",
     "OperationHistory, DuplicateFinder, Settings"),
    ("3. Iterator (__iter__/__next__)",
     "core/iterators.py: ChunkReader, BatchIterator",
     "hashowanie plików, paczki zadań procesów"),
    ("4. Generatory (yield, yield from, wyrażenia generatorowe)",
     "core/generators.py: iter_files -> filter_by_pattern -> with_sizes -> files_at_least",
     "Duplikaty, Analiza miejsca"),
    ("5. Regex (>=2 wzorce, grupy nazwane)",
     "core/patterns.py: DATE_IN_NAME_RE, COPY_SUFFIX_RE, SIZE_RE",
     "sortowanie wg daty, pole „Minimalny rozmiar”, wykluczenia"),
    ("6. Wątki (I/O, Lock/Queue)",
     "core/concurrency.py: threaded_map (Queue + Lock), ProgressCounter",
     "Duplikaty -> tryb „thread”, tło GUI"),
    ("7. Procesy (CPU-bound)",
     "core/concurrency.py: _process_map (ProcessPoolExecutor)",
     "Duplikaty -> tryb „process”"),
    ("8. GIL - pomiar i wnioski",
     "benchmarks/gil_benchmark.py; wnioski w README.md",
     "Ustawienia -> „Uruchom benchmark GIL”"),
    ("Dodatki: testy, CLI, logowanie, cofanie operacji",
     "tests/, main.py, utils/logging_config.py, core/history.py",
     "python main.py --help; Historia operacji"),
)


class RequirementsPage(ctk.CTkFrame):
    """Read-only table: requirement -> code -> visible feature."""

    def __init__(self, parent: ctk.CTkBaseClass) -> None:
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        page_header(self, "Wymagania projektu",
                    "Gdzie w kodzie zrealizowano każdy punkt wymagań prowadzącego.")
        box = ctk.CTkTextbox(self, corner_radius=10, wrap="word")
        box.grid(row=2, column=0, sticky="nsew")
        lines: list[str] = []
        for title, where, demo in REQUIREMENTS:
            lines += [title, f"   Kod:  {where}", f"   Demo: {demo}", ""]
        set_textbox(box, "\n".join(lines))
