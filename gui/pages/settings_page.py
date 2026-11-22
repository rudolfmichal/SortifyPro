"""'Ustawienia' section: tune the analyses and run the GIL benchmark."""
from __future__ import annotations

import customtkinter as ctk

from benchmarks.gil_benchmark import format_markdown, run_benchmark
from core.concurrency import MODES
from core.patterns import parse_size
from core.settings import Settings
from gui.widgets import page_header, post_to_ui, run_in_background, set_textbox, ui_safe
from utils.fs import format_size


class SettingsPage(ctk.CTkScrollableFrame):
    """Edit :class:`Settings` and measure sequential / threads / processes."""

    def __init__(self, parent: ctk.CTkBaseClass, settings: Settings) -> None:
        super().__init__(parent, fg_color="transparent")
        self._settings = settings
        self._benchmark_running = False
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        page_header(
            self, "Ustawienia",
            "Parametry wyszukiwania duplikatów oraz pomiar wpływu GIL.", columnspan=2,
        )
        s = self._settings

        self.workers_entry = self._row(2, "Liczba workerów (wątki / procesy)", str(s.workers))
        ctk.CTkLabel(self, text="Tryb pełnego skrótu SHA-256", anchor="w").grid(
            row=3, column=0, sticky="w", pady=8
        )
        self.mode_menu = ctk.CTkOptionMenu(self, values=list(MODES))
        self.mode_menu.set(s.hash_mode)
        self.mode_menu.grid(row=3, column=1, sticky="w", pady=8)
        self.size_entry = self._row(4, "Minimalny rozmiar pliku (np. 500 KB, 2 MB)",
                                    format_size(s.min_duplicate_size))
        self.exclude_entry = self._row(5, "Pomijaj nazwy plików (regex, puste = nic)",
                                       s.exclude_pattern)
        self.date_var = ctk.BooleanVar(value=s.group_by_date)
        ctk.CTkSwitch(
            self, text="Sortowanie: grupuj pliki wg daty w nazwie (RRRR-MM)",
            variable=self.date_var,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=8)

        ctk.CTkButton(self, text="Zapisz ustawienia", command=self._save).grid(
            row=7, column=0, sticky="w", pady=(14, 4)
        )
        self.message_label = ctk.CTkLabel(self, text="", anchor="w")
        self.message_label.grid(row=7, column=1, sticky="w", padx=14, pady=(14, 4))

        ctk.CTkLabel(
            self, text="Benchmark GIL", font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=(30, 4))
        ctk.CTkLabel(
            self,
            text="Porównuje wykonanie sekwencyjne, na wątkach i na procesach "
                 "(szybka wersja: 6 plików po 4 MB).",
            text_color="gray", anchor="w",
        ).grid(row=9, column=0, columnspan=2, sticky="w")
        self.benchmark_button = ctk.CTkButton(
            self, text="Uruchom benchmark", command=self._start_benchmark
        )
        self.benchmark_button.grid(row=10, column=0, sticky="w", pady=12)
        self.benchmark_status = ctk.CTkLabel(self, text="", text_color="gray", anchor="w")
        self.benchmark_status.grid(row=10, column=1, sticky="w", padx=14)
        self.benchmark_box = ctk.CTkTextbox(
            self, height=260, corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.benchmark_box.grid(row=11, column=0, columnspan=2, sticky="ew")
        set_textbox(self.benchmark_box, "Wyniki pojawią się tutaj.")

    def _row(self, row: int, label: str, value: str) -> ctk.CTkEntry:
        ctk.CTkLabel(self, text=label, anchor="w").grid(row=row, column=0, sticky="w", pady=8)
        entry = ctk.CTkEntry(self)
        entry.insert(0, value)
        entry.grid(row=row, column=1, sticky="ew", pady=8, padx=(14, 0))
        return entry

    # -- saving ------------------------------------------------------------------
    def _save(self) -> None:
        try:
            workers = int(self.workers_entry.get().strip())
            min_size = parse_size(self.size_entry.get())
            # Assigning goes through the validating property setters.
            self._settings.workers = workers
            self._settings.hash_mode = self.mode_menu.get()
            self._settings.min_duplicate_size = min_size
            self._settings.exclude_pattern = self.exclude_entry.get()
            self._settings.group_by_date = bool(self.date_var.get())
        except ValueError as error:
            self.message_label.configure(text=f"Błąd: {error}", text_color="#F85149")
            return
        self._settings.save()
        self.message_label.configure(text="Zapisano.", text_color="#3FB950")

    # -- benchmark ---------------------------------------------------------------
    def _start_benchmark(self) -> None:
        if self._benchmark_running:
            return
        self._benchmark_running = True
        workers = self._settings.workers
        self.benchmark_button.configure(state="disabled", text="Pomiar...")
        set_textbox(self.benchmark_box, "Pomiar w toku...")

        def on_step(step: str) -> None:
            post_to_ui(self, self._show_step, step)

        run_in_background(
            self,
            lambda: run_benchmark(6, 4, workers, repeats=1, on_step=on_step),
            self._show_benchmark,
            self._show_benchmark_error,
        )

    @ui_safe
    def _show_step(self, step: str) -> None:
        self.benchmark_status.configure(text=step)

    @ui_safe
    def _show_benchmark(self, report) -> None:  # type: ignore[no-untyped-def]
        self._benchmark_running = False
        self.benchmark_button.configure(state="normal", text="Uruchom ponownie")
        self.benchmark_status.configure(text="Gotowe.")
        set_textbox(self.benchmark_box, format_markdown(report))

    @ui_safe
    def _show_benchmark_error(self, error: Exception) -> None:
        self._benchmark_running = False
        self.benchmark_button.configure(state="normal", text="Uruchom benchmark")
        self.benchmark_status.configure(text="Błąd pomiaru.")
        set_textbox(self.benchmark_box, f"Błąd: {error}")
