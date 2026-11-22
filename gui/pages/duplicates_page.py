"""'Duplikaty' section: find identical files and move the copies aside."""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.duplicates import (
    DUPLICATES_DIR_NAME,
    DuplicateFinder,
    DuplicateReport,
    move_duplicates,
)
from core.file_sorter import MoveResult
from core.history import OperationHistory
from core.settings import Settings
from gui.widgets import page_header, post_to_ui, run_in_background, set_textbox, ui_safe
from utils.fs import format_size

STAGE_LABELS = {
    "scan": "Skanowanie plików",
    "partial": "Szybki skrót początku pliku (wątki)",
    "full": "Pełny skrót SHA-256",
}
MAX_GROUPS_SHOWN = 60


class DuplicatesPage(ctk.CTkFrame):
    """Search for duplicates, review them and move the copies to ``_Duplikaty``."""

    def __init__(
        self, parent: ctk.CTkBaseClass, settings: Settings, history: OperationHistory
    ) -> None:
        super().__init__(parent, fg_color="transparent")
        self._settings = settings
        self._history = history
        self._folder: Path | None = None
        self._report: DuplicateReport | None = None
        self._cancel = threading.Event()
        self._busy = False
        self._build()

    def destroy(self) -> None:
        """Stop a running search when the user leaves the page."""
        self._cancel.set()
        super().destroy()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(6, weight=1)
        page_header(
            self,
            "Duplikaty",
            "Znajdź pliki o identycznej zawartości. Nic nie jest usuwane - kopie "
            f"trafiają do folderu „{DUPLICATES_DIR_NAME}”.",
            columnspan=2,
        )

        self.folder_label = ctk.CTkLabel(self, text="Nie wybrano folderu", anchor="w")
        self.folder_label.grid(row=2, column=0, sticky="ew", padx=(0, 12))
        ctk.CTkButton(self, text="Wybierz folder", command=self._choose_folder).grid(
            row=2, column=1, sticky="ew"
        )

        self.status_label = ctk.CTkLabel(
            self, text=self._settings_summary(), text_color="gray", anchor="w"
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(20, 8))

        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.search_button = ctk.CTkButton(
            buttons, text="Szukaj duplikatów", command=self._start_search, state="disabled"
        )
        self.search_button.pack(side="left", padx=(0, 10))
        self.cancel_button = ctk.CTkButton(
            buttons, text="Anuluj", command=self._cancel.set, state="disabled",
            fg_color="#6E7681", hover_color="#57606A",
        )
        self.cancel_button.pack(side="left", padx=(0, 10))
        self.move_button = ctk.CTkButton(
            buttons, text="Przenieś duplikaty", command=self._confirm_move,
            state="disabled", fg_color="#238636", hover_color="#1A6E2C",
        )
        self.move_button.pack(side="left")

        self.results_box = ctk.CTkTextbox(self, corner_radius=10)
        self.results_box.grid(row=6, column=0, columnspan=2, sticky="nsew")
        set_textbox(
            self.results_box,
            "Wybierz folder i kliknij „Szukaj duplikatów”.\n\n"
            "Oryginałem jest plik, którego nazwa nie wygląda na kopię "
            "(np. „zdjęcie (1).jpg”, „raport - Kopia.docx”), położony płycej i starszy.",
        )

    def _settings_summary(self) -> str:
        s = self._settings
        return (
            f"Tryb: {s.hash_mode} | workerów: {s.workers} | "
            f"pomijane pliki mniejsze niż {format_size(s.min_duplicate_size)} "
            "(zmienisz to w Ustawieniach)"
        )

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Wybierz folder do przeszukania")
        if not selected:
            return
        self._folder = Path(selected)
        self._report = None
        self.folder_label.configure(text=str(self._folder))
        self.status_label.configure(text=self._settings_summary())
        self.search_button.configure(state="normal")
        self.move_button.configure(state="disabled")
        self.progress.set(0)

    # -- search ---------------------------------------------------------------
    def _start_search(self) -> None:
        if self._folder is None or self._busy:
            return
        self._busy = True
        self._cancel.clear()
        finder = DuplicateFinder.from_settings(self._settings)
        folder, cancel = self._folder, self._cancel

        self.search_button.configure(state="disabled", text="Szukanie...")
        self.move_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.progress.set(0)
        self.status_label.configure(text="Skanowanie plików...")

        def on_progress(stage: str, done: int, total: int) -> None:
            post_to_ui(self, self._show_progress, stage, done, total)

        run_in_background(
            self,
            lambda: finder.find(folder, on_progress, cancel),
            self._show_report,
            self._show_error,
        )

    @ui_safe
    def _show_progress(self, stage: str, done: int, total: int) -> None:
        label = STAGE_LABELS.get(stage, stage)
        if stage == "full":
            label = f"{label} - tryb {self._settings.hash_mode}"
        self.status_label.configure(text=f"{label}: {done}/{total}")
        self.progress.set(done / total if total else 1)

    @ui_safe
    def _show_report(self, report: DuplicateReport) -> None:
        self._busy = False
        self._report = report
        self.search_button.configure(state="normal", text="Szukaj ponownie")
        self.cancel_button.configure(state="disabled")
        self.progress.set(1)

        if report.cancelled:
            self.status_label.configure(text="Wyszukiwanie przerwane.")
        else:
            self.status_label.configure(
                text=f"Gotowe: {report.duplicate_count} zbędnych kopii, "
                f"do odzyskania {format_size(report.wasted_bytes)}."
            )
        self.move_button.configure(
            state="normal" if report.groups and not report.cancelled else "disabled"
        )
        set_textbox(self.results_box, _format_report(report))

    @ui_safe
    def _show_error(self, error: Exception) -> None:
        self._busy = False
        self.search_button.configure(state="normal", text="Szukaj duplikatów")
        self.cancel_button.configure(state="disabled")
        self.status_label.configure(text="Nie udało się przeszukać folderu.")
        messagebox.showerror("Błąd wyszukiwania", str(error))

    # -- moving ------------------------------------------------------------------
    def _confirm_move(self) -> None:
        report = self._report
        if report is None or not report.groups or self._busy:
            return
        approved = messagebox.askyesno(
            "Potwierdź przeniesienie",
            f"Przenieść {report.duplicate_count} kopii do folderu "
            f"„{DUPLICATES_DIR_NAME}” w {report.root.name}?\n\n"
            "Oryginały zostaną na miejscu. Operację możesz cofnąć w sekcji "
            "„Historia operacji”.",
        )
        if not approved:
            return
        self._busy = True
        self.move_button.configure(state="disabled", text="Przenoszenie...")
        self.search_button.configure(state="disabled")
        run_in_background(
            self,
            lambda: move_duplicates(report, self._history),
            self._show_moved,
            self._show_error,
        )

    @ui_safe
    def _show_moved(self, result: MoveResult) -> None:
        self._busy = False
        self._report = None
        self.search_button.configure(state="normal")
        self.move_button.configure(state="disabled", text="Przenieś duplikaty")
        lines = [
            "Przenoszenie zakończone.",
            f"Przeniesiono: {result.moved_count}",
            f"Błędy: {len(result.errors)}",
        ]
        if result.errors:
            lines += ["", "Szczegóły błędów:"] + [f"  - {e}" for e in result.errors]
        self.status_label.configure(text=f"Przeniesiono {result.moved_count} plików.")
        set_textbox(self.results_box, "\n".join(lines))


def _format_report(report: DuplicateReport) -> str:
    """Render a :class:`DuplicateReport` as text for the results box."""
    t = report.timings
    lines = [
        f"Folder: {report.root}",
        f"Przeskanowane pliki (po filtrach): {report.scanned_files}",
        f"Grupy duplikatów: {len(report.groups)}",
        f"Zbędne kopie: {report.duplicate_count} ({format_size(report.wasted_bytes)})",
        f"Czas: skan {t.get('scan', 0):.2f} s | szybki skrót {t.get('partial', 0):.2f} s | "
        f"pełny skrót ({report.mode}) {t.get('full', 0):.2f} s",
    ]
    if report.cancelled:
        lines.append("UWAGA: wyszukiwanie zostało przerwane - wynik jest niepełny.")
    if report.errors:
        lines.append(f"Pliki pominięte z powodu błędów: {len(report.errors)}")

    for number, group in enumerate(report.groups[:MAX_GROUPS_SHOWN], start=1):
        lines += ["", f"Grupa {number}: {len(group.files)} pliki po {format_size(group.size)}"]
        for index, path in enumerate(group.files):
            try:
                shown = path.relative_to(report.root)
            except ValueError:
                shown = path
            lines.append(f"  {'ORYGINAŁ' if index == 0 else 'kopia   '}  {shown}")
    hidden = len(report.groups) - MAX_GROUPS_SHOWN
    if hidden > 0:
        lines += ["", f"... oraz {hidden} kolejnych grup."]
    if not report.groups and not report.cancelled:
        lines += ["", "Nie znaleziono duplikatów."]
    if report.errors:
        lines += ["", "Błędy:"] + [f"  - {e}" for e in report.errors[:20]]
    return "\n".join(lines)
