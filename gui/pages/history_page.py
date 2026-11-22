"""'Historia operacji' section: review past operations and undo them."""
from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from core.history import OperationHistory, UndoResult
from gui.widgets import page_header, run_in_background, ui_safe


class HistoryPage(ctk.CTkFrame):
    """Lists recorded batches; every batch that was not undone has an *Undo* button."""

    def __init__(self, parent: ctk.CTkBaseClass, history: OperationHistory) -> None:
        super().__init__(parent, fg_color="transparent")
        self._history = history
        self._busy = False
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        page_header(
            self, "Historia operacji",
            "Każde sortowanie i przeniesienie duplikatów można cofnąć.",
        )
        self.status_label = ctk.CTkLabel(self, text="", text_color="gray", anchor="w")
        self.status_label.grid(row=2, column=0, sticky="w", pady=(0, 10))
        self.list_frame = ctk.CTkScrollableFrame(self, corner_radius=10)
        self.list_frame.grid(row=3, column=0, sticky="nsew")
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the list from the history file."""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        batches = self._history.batches()
        if not batches:
            ctk.CTkLabel(
                self.list_frame, text="Brak zapisanych operacji.", text_color="gray"
            ).pack(anchor="w", padx=12, pady=12)
            return

        for batch in batches:
            row = ctk.CTkFrame(self.list_frame, corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=batch.label, anchor="w").pack(
                side="left", padx=14, pady=12
            )
            ctk.CTkButton(
                row, text="Cofnij", width=90,
                state="disabled" if batch.undone else "normal",
                command=lambda batch_id=batch.batch_id: self._confirm_undo(batch_id),
            ).pack(side="right", padx=12)

    def _confirm_undo(self, batch_id: str) -> None:
        if self._busy:
            return
        if not messagebox.askyesno(
            "Cofnij operację", "Przywrócić pliki do poprzednich lokalizacji?"
        ):
            return
        self._busy = True
        self.status_label.configure(text="Cofanie operacji...")
        run_in_background(
            self, lambda: self._history.undo(batch_id), self._show_undone, self._show_error
        )

    @ui_safe
    def _show_undone(self, result: UndoResult) -> None:
        self._busy = False
        text = f"Przywrócono plików: {result.restored}."
        if result.errors:
            text += f" Błędy: {len(result.errors)}."
        self.status_label.configure(text=text)
        self.refresh()
        if result.errors:
            messagebox.showwarning("Cofanie zakończone z błędami", "\n".join(result.errors[:15]))

    @ui_safe
    def _show_error(self, error: Exception) -> None:
        self._busy = False
        self.status_label.configure(text="Nie udało się cofnąć operacji.")
        messagebox.showerror("Błąd", str(error))
