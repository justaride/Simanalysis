"""Logging helpers for Simanalysis."""

from __future__ import annotations

import logging
from typing import Literal

from rich.logging import RichHandler

_LOGGER_NAME = "simanalysis"


def init_logger(level: Literal["info", "debug"] = "info") -> logging.Logger:
    """Configure and return the shared Simanalysis logger."""

    logger = logging.getLogger(_LOGGER_NAME)
    logging_level = logging.DEBUG if level == "debug" else logging.INFO

    if not any(isinstance(handler, RichHandler) for handler in logger.handlers):
        handler = RichHandler(show_time=False, rich_tracebacks=True)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False

    logger.setLevel(logging_level)
    for handler in logger.handlers:
        handler.setLevel(logging_level)
    return logger
