"""Central logging configuration for the application and the CLI."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from utils.fs import app_data_dir

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def setup_logging(verbose: bool = False) -> None:
    """Configure console logging and, when possible, a rotating log file."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_dir = app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_dir / "sortifypro.log",
                maxBytes=512_000,
                backupCount=2,
                encoding="utf-8",
            )
        )
    except OSError:
        # Logging to a file is a convenience; never block the application.
        pass

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
        force=True,
    )
