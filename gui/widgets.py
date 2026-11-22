"""Small GUI helpers shared by all pages.

Worker threads must never touch widgets directly. :func:`run_in_background`
runs a function off the UI thread and delivers its result back through
``widget.after`` - and silently drops it if the user already left the page
(the widget no longer exists).
"""
from __future__ import annotations

import functools
import logging
import threading
import tkinter
from typing import Any, Callable, TypeVar

import customtkinter as ctk

logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


def ui_safe(func: F) -> F:
    """Decorator: ignore ``TclError`` raised because a widget was destroyed.

    Callbacks of background tasks can arrive after the user switched to
    another section; touching the old widgets must not crash anything.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except tkinter.TclError:
            logger.debug("Widget został zniszczony: %s", func.__name__)
            return None

    return wrapper  # type: ignore[return-value]


def post_to_ui(widget: Any, callback: Callable[..., None], *args: Any) -> None:
    """Schedule ``callback(*args)`` on the UI thread if ``widget`` still exists."""

    def invoke() -> None:
        try:
            if widget.winfo_exists():
                callback(*args)
        except tkinter.TclError:
            logger.debug("Pominięto callback - widget nie istnieje.")

    try:
        widget.after(0, invoke)
    except (RuntimeError, tkinter.TclError):
        # The main loop is no longer running (application is closing).
        logger.debug("Nie można zaplanować callbacku - aplikacja się zamyka.")


def run_in_background(
    widget: Any,
    work: Callable[[], T],
    on_done: Callable[[T], None],
    on_error: Callable[[Exception], None] | None = None,
) -> threading.Thread:
    """Run ``work`` in a daemon thread and report back on the UI thread."""

    def runner() -> None:
        try:
            result = work()
        except Exception as error:  # noqa: BLE001 - delivered to on_error
            logger.exception("Zadanie w tle zakończyło się błędem")
            if on_error is not None:
                post_to_ui(widget, on_error, error)
        else:
            post_to_ui(widget, on_done, result)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


def page_header(parent: Any, title: str, subtitle: str, columnspan: int = 1) -> None:
    """Title + grey subtitle in rows 0 and 1 of ``parent``'s grid."""
    ctk.CTkLabel(
        parent, text=title, font=ctk.CTkFont(size=32, weight="bold")
    ).grid(row=0, column=0, columnspan=columnspan, sticky="w", pady=(0, 8))
    ctk.CTkLabel(
        parent, text=subtitle, font=ctk.CTkFont(size=14), text_color="gray"
    ).grid(row=1, column=0, columnspan=columnspan, sticky="w", pady=(0, 24))


def set_textbox(box: Any, text: str) -> None:
    """Replace the content of a read-only ``CTkTextbox``."""
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", text)
    box.configure(state="disabled")
