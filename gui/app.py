"""Graphical interface for Sortify Pro."""
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.file_scanner import ScanResult, scan_folder
from core.file_sorter import (
    MoveResult,
    SortOperation,
    create_sort_plan,
    execute_moves,
    get_category,
)
from core.history import OperationHistory
from core.settings import Settings
from gui.pages.duplicates_page import DuplicatesPage
from gui.pages.history_page import HistoryPage
from gui.pages.requirements_page import RequirementsPage
from gui.pages.settings_page import SettingsPage
from gui.pages.space_page import SpacePage
from gui.widgets import run_in_background, ui_safe
from utils.fs import format_size


class SortifyApp(ctk.CTk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Sortify Pro")
        self.geometry("1100x720")
        self.minsize(900, 600)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.selected_folder: Path | None = None
        self.sort_folder: Path | None = None
        self.sort_plan: list[SortOperation] = []
        self.sort_busy = False
        self.last_scan: ScanResult | None = None
        self.settings = Settings.load()
        self.history = OperationHistory()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=30, pady=28)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self._show_section("Dashboard")

    def _build_sidebar(self) -> None:
        """Create the navigation sidebar."""
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="SORTIFY PRO",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).pack(padx=20, pady=(30, 35))

        sections = (
            "Dashboard",
            "Sortowanie plików",
            "Duplikaty",
            "Analiza miejsca",
            "Historia operacji",
            "Wymagania",
            "Ustawienia",
        )
        for label in sections:
            ctk.CTkButton(
                sidebar,
                text=label,
                anchor="w",
                fg_color="transparent",
                hover_color=("#DCEBFA", "#263B55"),
                text_color=("gray10", "white"),
                command=lambda name=label: self._show_section(name),
            ).pack(fill="x", padx=14, pady=5)

    def _clear_content(self) -> None:
        """Remove the currently displayed section."""
        for widget in self.content.winfo_children():
            widget.destroy()
        # Reset grid weights left over from the previous section.
        for index in range(8):
            self.content.grid_columnconfigure(index, weight=0)
            self.content.grid_rowconfigure(index, weight=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

    def _show_section(self, section: str) -> None:
        """Display the selected application section."""
        self._clear_content()
        if section == "Dashboard":
            self._build_dashboard()
        elif section == "Sortowanie plików":
            self._build_sorting_page()
        elif section == "Duplikaty":
            self._place_page(DuplicatesPage(self.content, self.settings, self.history))
        elif section == "Analiza miejsca":
            self._place_page(SpacePage(self.content, self.settings))
        elif section == "Historia operacji":
            self._place_page(HistoryPage(self.content, self.history))
        elif section == "Wymagania":
            self._place_page(RequirementsPage(self.content))
        elif section == "Ustawienia":
            self._place_page(SettingsPage(self.content, self.settings))
        else:
            self._build_placeholder(section)

    def _place_page(self, page: ctk.CTkFrame) -> None:
        """Show a page that fills the whole content area."""
        page.grid(row=0, column=0, columnspan=3, sticky="nsew")

    def _build_dashboard(self) -> None:
        """Build the dashboard view."""
        self.content.grid_columnconfigure((0, 1, 2), weight=1)
        self.content.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            self.content,
            text="Dashboard",
            font=ctk.CTkFont(size=32, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            self.content,
            text="Wybierz folder, aby przeanalizować znajdujące się w nim pliki.",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 24))

        self.folder_label = ctk.CTkLabel(
            self.content,
            text=str(self.selected_folder) if self.selected_folder else "Nie wybrano folderu",
            anchor="w",
        )
        self.folder_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 12))

        ctk.CTkButton(
            self.content,
            text="Wybierz folder",
            command=self._choose_scan_folder,
        ).grid(row=2, column=2, sticky="ew")

        self.file_count_value = self._stat_card(self.content, "Pliki", "—", 3, 0)
        self.folder_count_value = self._stat_card(self.content, "Foldery", "—", 3, 1)
        self.total_size_value = self._stat_card(self.content, "Łączny rozmiar", "—", 3, 2)

        self.status_label = ctk.CTkLabel(
            self.content,
            text="Gotowy do skanowania",
            text_color="gray",
            anchor="w",
        )
        self.status_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(28, 8))

        self.scan_button = ctk.CTkButton(
            self.content,
            text="Skanuj ponownie" if self.selected_folder else "Skanuj folder",
            height=42,
            command=self._start_scan,
            state="normal" if self.selected_folder else "disabled",
        )
        self.scan_button.grid(row=5, column=0, sticky="w", pady=8)

        self.results_box = ctk.CTkTextbox(self.content, height=230, corner_radius=10)
        self.results_box.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(20, 0))
        self.results_box.insert("1.0", "Wybierz folder i rozpocznij skanowanie.\n")
        self.results_box.configure(state="disabled")
        if self.last_scan is not None:
            self._show_scan_result(self.last_scan)

    def _stat_card(self, parent, title: str, value: str, row: int, column: int):
        """Create one dashboard statistic card."""
        card = ctk.CTkFrame(parent, corner_radius=12)
        card.grid(row=row, column=column, sticky="nsew", padx=5, pady=22)
        ctk.CTkLabel(card, text=title, text_color="gray").pack(
            anchor="w", padx=16, pady=(14, 4)
        )
        value_label = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        value_label.pack(anchor="w", padx=16, pady=(0, 14))
        return value_label

    def _choose_scan_folder(self) -> None:
        """Choose a folder for dashboard analysis."""
        selected = filedialog.askdirectory(title="Wybierz folder do analizy")
        if selected:
            self.selected_folder = Path(selected)
            self.folder_label.configure(text=str(self.selected_folder))
            self.scan_button.configure(state="normal")
            self.status_label.configure(text="Folder wybrany. Możesz rozpocząć skanowanie.")

    def _start_scan(self) -> None:
        """Run scanning on a worker thread to keep the UI responsive."""
        if self.selected_folder is None:
            return
        folder = self.selected_folder
        self.scan_button.configure(state="disabled", text="Skanowanie...")
        self.status_label.configure(text="Trwa skanowanie folderu...")

        def work() -> ScanResult:
            result = scan_folder(folder)
            self.last_scan = result
            return result

        run_in_background(self, work, self._show_scan_result, self._show_scan_error)

    @ui_safe
    def _show_scan_result(self, result: ScanResult) -> None:
        """Update dashboard with scan results."""
        self.file_count_value.configure(text=str(result.file_count))
        self.folder_count_value.configure(text=str(result.folder_count))
        self.total_size_value.configure(text=format_size(result.total_bytes))
        self.status_label.configure(text="Skanowanie zakończone.")
        self.scan_button.configure(state="normal", text="Skanuj ponownie")

        lines = [
            f"Folder: {result.root}",
            f"Liczba plików: {result.file_count}",
            f"Liczba podfolderów: {result.folder_count}",
            f"Łączny rozmiar: {format_size(result.total_bytes)}",
            "",
            "Najczęstsze rozszerzenia:",
        ]
        lines.extend(
            f"  {extension or '[bez rozszerzenia]'}: {count}"
            for extension, count in result.extensions.most_common(10)
        )
        self.results_box.configure(state="normal")
        self.results_box.delete("1.0", "end")
        self.results_box.insert("1.0", "\n".join(lines))
        self.results_box.configure(state="disabled")

    @ui_safe
    def _show_scan_error(self, error: Exception) -> None:
        """Display scanning errors."""
        self.status_label.configure(text="Nie udało się przeskanować folderu.")
        self.scan_button.configure(state="normal", text="Skanuj folder")
        messagebox.showerror("Błąd skanowania", str(error))

    def _build_sorting_page(self) -> None:
        """Build the file-sorting view."""
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_columnconfigure(1, weight=1)
        self.content.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            self.content,
            text="Sortowanie plików",
            font=ctk.CTkFont(size=32, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        ctk.CTkLabel(
            self.content,
            text="Uporządkuj pliki w folderze według ich rodzaju.",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 24))

        self.sort_folder_label = ctk.CTkLabel(
            self.content,
            text="Nie wybrano folderu",
            anchor="w",
        )
        self.sort_folder_label.grid(row=2, column=0, sticky="ew", padx=(0, 12))

        ctk.CTkButton(
            self.content,
            text="Wybierz folder",
            command=self._choose_sort_folder,
        ).grid(row=2, column=1, sticky="ew")

        self.sort_status_label = ctk.CTkLabel(
            self.content,
            text="Wybierz folder, aby przygotować plan sortowania.",
            text_color="gray",
            anchor="w",
        )
        self.sort_status_label.grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(22, 10)
        )

        buttons = ctk.CTkFrame(self.content, fg_color="transparent")
        buttons.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self.preview_button = ctk.CTkButton(
            buttons,
            text="Przygotuj podgląd",
            command=self._start_sort_preview,
            state="disabled",
        )
        self.preview_button.pack(side="left", padx=(0, 10))

        self.execute_button = ctk.CTkButton(
            buttons,
            text="Rozpocznij sortowanie",
            command=self._confirm_sort,
            state="disabled",
            fg_color="#238636",
            hover_color="#1A6E2C",
        )
        self.execute_button.pack(side="left")

        self.sort_results_box = ctk.CTkTextbox(
            self.content,
            height=300,
            corner_radius=10,
        )
        self.sort_results_box.grid(
            row=5, column=0, columnspan=2, sticky="nsew", pady=(10, 0)
        )
        self._set_sort_text(
            "Tutaj pojawi się podgląd.\n\n"
            "Sortify Pro nie przeniesie żadnych plików, dopóki nie zatwierdzisz operacji."
        )

    def _choose_sort_folder(self) -> None:
        """Choose the folder whose top-level files will be sorted."""
        selected = filedialog.askdirectory(title="Wybierz folder do uporządkowania")
        if not selected:
            return

        self.sort_folder = Path(selected)
        self.sort_plan = []
        self.sort_folder_label.configure(text=str(self.sort_folder))
        self.sort_status_label.configure(
            text="Folder wybrany. Przygotuj podgląd przed sortowaniem."
        )
        self.preview_button.configure(state="normal")
        self.execute_button.configure(state="disabled")
        self._set_sort_text(
            "Wybrany folder:\n"
            f"{self.sort_folder}\n\n"
            "Kliknij „Przygotuj podgląd”, aby zobaczyć planowane przeniesienia."
        )

    def _start_sort_preview(self) -> None:
        """Create the sorting plan in a worker thread."""
        if self.sort_folder is None or self.sort_busy:
            return

        self.sort_busy = True
        self.preview_button.configure(state="disabled", text="Analizowanie...")
        self.execute_button.configure(state="disabled")
        self.sort_status_label.configure(text="Przygotowywanie planu sortowania...")
        folder = self.sort_folder
        group_by_date = self.settings.group_by_date
        run_in_background(
            self,
            lambda: create_sort_plan(folder, group_by_date=group_by_date),
            self._show_sort_preview,
            self._show_sort_error,
        )

    @ui_safe
    def _show_sort_preview(self, plan: list[SortOperation]) -> None:
        """Display the planned moves without changing any files."""
        self.sort_busy = False
        self.sort_plan = plan
        self.preview_button.configure(state="normal", text="Odśwież podgląd")

        if not plan:
            self.sort_status_label.configure(text="Nie znaleziono plików do posortowania.")
            self.execute_button.configure(state="disabled")
            self._set_sort_text("W wybranym folderze nie ma plików do przeniesienia.")
            return

        category_counts: dict[str, int] = {}
        for operation in plan:
            category = get_category(operation.source)
            category_counts[category] = category_counts.get(category, 0) + 1

        lines = [
            f"Folder źródłowy: {self.sort_folder}",
            f"Liczba plików do przeniesienia: {len(plan)}",
            "",
            "Podsumowanie kategorii:",
        ]
        lines.extend(
            f"  {category}: {count}"
            for category, count in sorted(category_counts.items())
        )
        lines.extend(["", "Szczegółowy podgląd:"])
        lines.extend(
            f"  {operation.source.name}  →  {operation.destination.parent.name}/"
            for operation in plan[:100]
        )
        if len(plan) > 100:
            lines.append(f"  ... oraz kolejnych {len(plan) - 100} plików")

        lines.extend([
            "",
            "Pliki zostaną przeniesione do podfolderów kategorii w wybranym folderze.",
            "Istniejące pliki nie będą nadpisywane.",
        ])
        self.sort_status_label.configure(
            text=f"Gotowy podgląd: {len(plan)} plików do uporządkowania."
        )
        self.execute_button.configure(state="normal")
        self._set_sort_text("\n".join(lines))

    def _confirm_sort(self) -> None:
        """Ask for confirmation before moving files."""
        if not self.sort_plan or self.sort_busy:
            return

        approved = messagebox.askyesno(
            "Potwierdź sortowanie",
            f"Czy przenieść {len(self.sort_plan)} plików do folderów kategorii "
            "w wybranym katalogu?\n\nOperację można cofnąć w sekcji „Historia operacji”.",
        )
        if not approved:
            return

        self.sort_busy = True
        self.preview_button.configure(state="disabled")
        self.execute_button.configure(state="disabled", text="Sortowanie...")
        self.sort_status_label.configure(text="Trwa przenoszenie plików...")
        plan = list(self.sort_plan)
        folder = self.sort_folder

        def work() -> MoveResult:
            result = execute_moves(plan)
            label = f"Sortowanie: {folder}" if folder else "Sortowanie"
            self.history.record_batch(label, result.moved)
            return result

        run_in_background(self, work, self._show_sort_result, self._show_sort_error)

    @ui_safe
    def _show_sort_result(self, result: MoveResult) -> None:
        """Display the result of the sorting operation."""
        moved_count, errors = result.moved_count, result.errors
        self.sort_busy = False
        self.sort_plan = []
        self.preview_button.configure(state="normal", text="Przygotuj podgląd")
        self.execute_button.configure(state="disabled", text="Rozpocznij sortowanie")

        lines = [
            "Sortowanie zakończone.",
            f"Poprawnie przeniesione pliki: {moved_count}",
            f"Błędy: {len(errors)}",
        ]
        if errors:
            lines.extend(["", "Szczegóły błędów:"])
            lines.extend(f"  - {error}" for error in errors)

        self.sort_status_label.configure(
            text=f"Sortowanie zakończone. Przeniesiono {moved_count} plików."
        )
        self._set_sort_text("\n".join(lines))
        if self.sort_folder is not None:
            messagebox.showinfo(
                "Sortowanie zakończone",
                f"Przeniesiono plików: {moved_count}\nBłędy: {len(errors)}",
            )

    @ui_safe
    def _show_sort_error(self, error: Exception) -> None:
        """Display errors raised while preparing or executing a sort."""
        self.sort_busy = False
        self.preview_button.configure(state="normal", text="Przygotuj podgląd")
        self.execute_button.configure(state="disabled")
        self.sort_status_label.configure(text="Nie udało się wykonać operacji.")
        messagebox.showerror("Błąd sortowania", str(error))

    def _set_sort_text(self, text: str) -> None:
        """Replace the text in the sorting results box."""
        self.sort_results_box.configure(state="normal")
        self.sort_results_box.delete("1.0", "end")
        self.sort_results_box.insert("1.0", text)
        self.sort_results_box.configure(state="disabled")

    def _build_placeholder(self, section: str) -> None:
        """Display a temporary view for sections not implemented yet."""
        self.content.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self.content,
            text=section,
            font=ctk.CTkFont(size=32, weight="bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))
        ctk.CTkLabel(
            self.content,
            text="Ta sekcja zostanie zaimplementowana w kolejnym etapie.",
            text_color="gray",
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, sticky="w")
