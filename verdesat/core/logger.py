"""
Module for centralized, configurable logging across VerdeSat packages.
"""

import logging
import os
import json
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs log records in JSON format with keys:
    timestamp (in ISO8601 with UTC timezone), level, name, message.
    """

    def format(self, record):
        record_dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(record_dict)


class Logger:
    """
    Central logging setup for all modules.
    """

    _configured = False

    @staticmethod
    def setup(
        level: int | None = None,
        fmt: str | None = None,
        datefmt: str = "%Y-%m-%d %H:%M:%S",
    ) -> None:
        """
        Configure the logging system.

        If level is not provided, reads from the VERDESAT_LOG_LEVEL environment variable.
        """
        if Logger._configured:
            return
        if level is None:
            env_level = os.getenv("VERDESAT_LOG_LEVEL", "INFO").upper()
            effective_level = getattr(logging, env_level, logging.INFO)
        else:
            effective_level = level

        fmt_mode = fmt if fmt is not None else os.getenv("VERDESAT_LOG_FMT", "")
        default_fmt = "%(asctime)s [%(levelname)s] %(name)s – %(message)s"
        root = logging.getLogger()
        root.handlers.clear()

        if fmt_mode.lower() == "json":
            # Structured JSON output
            handler = logging.StreamHandler()
            handler.setFormatter(JSONFormatter(datefmt=datefmt))
            # Clear existing handlers to avoid duplicates
            root.handlers.clear()
            root.addHandler(handler)
            root.setLevel(effective_level)
        else:
            # Standard text output
            # Clear handlers so basicConfig can reinitialize
            root.handlers.clear()
            logging.basicConfig(
                level=effective_level,
                format=fmt_mode or default_fmt,
                datefmt=datefmt,
            )
        Logger._configured = True

    @staticmethod
    def get_logger(
        name: str = "verdesat", *, level: int | None = None, fmt: str | None = None
    ) -> logging.Logger:
        """
        Get a logger with the specified name.

        Parameters:
            name: The name of the logger.
            level: Optional logging level to set up.
            fmt: Optional format string for log messages.

        Returns:
            logging.Logger: The configured logger instance.
        """
        Logger.setup(level=level, fmt=fmt)
        logger = logging.getLogger(name)
        return logger
