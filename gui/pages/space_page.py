"""'Analiza miejsca' section: which categories and files use the most space."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.settings import Settings
from core.space_analyzer import SpaceReport, analyze_space
from gui.widgets import page_header, run_in_background, set_textbox, ui_safe
from utils.fs import format_size

BAR_WIDTH = 28


class SpacePage(ctk.CTkFrame):
    """Shows disk usage by category, by extension and the biggest files."""

    def __init__(self, parent: ctk.CTkBaseClass, settings: Settings) -> None:
        super().__init__(parent, fg_color="transparent")
        self._settings = settings
        self._folder: Path | None = None
        self._busy = False
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)
        page_header(
            self, "Analiza miejsca",
            "Sprawdź, które kategorie i pliki zajmują najwięcej miejsca.", columnspan=2,
        )
        self.folder_label = ctk.CTkLabel(self, text="Nie wybrano folderu", anchor="w")
        self.folder_label.grid(row=2, column=0, sticky="ew", padx=(0, 12))
        ctk.CTkButton(self, text="Wybierz folder", command=self._choose_folder).grid(
            row=2, column=1, sticky="ew"
        )
        self.status_label = ctk.CTkLabel(
            self, text="Wybierz folder do analizy.", text_color="gray", anchor="w"
        )
        self.status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(20, 8))
        self.analyze_button = ctk.CTkButton(
            self, text="Analizuj", command=self._start, state="disabled"
        )
        self.analyze_button.grid(row=4, column=0, sticky="w", pady=(0, 12))
        self.results_box = ctk.CTkTextbox(
            self, corner_radius=10, font=ctk.CTkFont(family="Consolas", size=13)
        )
        self.results_box.grid(row=5, column=0, columnspan=2, sticky="nsew")
        set_textbox(self.results_box, "Tutaj pojawi się raport zajętości miejsca.")

    def _choose_folder(self) -> None:
        selected = filedialog.askdirectory(title="Wybierz folder do analizy")
        if not selected:
            return
        self._folder = Path(selected)
        self.folder_label.configure(text=str(self._folder))
        self.analyze_button.configure(state="normal")
        self.status_label.configure(text="Folder wybrany. Kliknij „Analizuj”.")

    def _start(self) -> None:
        if self._folder is None or self._busy:
            return
        self._busy = True
        folder, exclude = self._folder, self._settings.compiled_exclude
        self.analyze_button.configure(state="disabled", text="Analizowanie...")
        self.status_label.configure(text="Trwa analiza...")
        run_in_background(
            self, lambda: analyze_space(folder, 15, exclude), self._show, self._show_error
        )

    @ui_safe
    def _show(self, report: SpaceReport) -> None:
        self._busy = False
        self.analyze_button.configure(state="normal", text="Analizuj ponownie")
        self.status_label.configure(
            text=f"Gotowe: {report.file_count} plików, {format_size(report.total_bytes)}."
        )
        set_textbox(self.results_box, format_space_report(report))

    @ui_safe
    def _show_error(self, error: Exception) -> None:
        self._busy = False
        self.analyze_button.configure(state="normal", text="Analizuj")
        self.status_label.configure(text="Nie udało się przeanalizować folderu.")
        messagebox.showerror("Błąd analizy", str(error))


def _bar(fraction: float) -> str:
    filled = round(fraction * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def format_space_report(report: SpaceReport) -> str:
    """Render a :class:`SpaceReport` with simple text bars."""
    total = report.total_bytes or 1
    lines = [
        f"Folder: {report.root}",
        f"Pliki: {report.file_count} | łącznie: {format_size(report.total_bytes)}",
        "",
        "Według kategorii:",
    ]
    for category, size in sorted(report.by_category.items(), key=lambda i: i[1], reverse=True):
        lines.append(f"  {category:<14} {_bar(size / total)} {size / total:6.1%}  {format_size(size)}")

    lines += ["", "Rozszerzenia zajmujące najwięcej miejsca:"]
    for extension, size in report.top_extensions(10):
        lines.append(f"  {extension or '[brak]':<14} {_bar(size / total)} {size / total:6.1%}  {format_size(size)}")

    lines += ["", f"Największe pliki (top {len(report.largest)}):"]
    for path, size in report.largest:
        try:
            shown = path.relative_to(report.root)
        except ValueError:
            shown = path
        lines.append(f"  {format_size(size):>10}  {shown}")
    return "\n".join(lines)
