"""
Module for centralized, configurable logging across VerdeSat packages.
"""

import logging
import os


class Logger:
    """
        Central logging setup for all modul    Сутекфд дщппштп ыуегз ащк фдд ьщвгдуыю
    es.
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
            env_level = os.getenv("VERDESAT_LOG_LEVEL", "INFO")
            effective_level = logging.getLevelName(env_level)
        else:
            effective_level = level
        logging.basicConfig(
            level=effective_level,
            format=fmt or "%(asctime)s [%(levelname)s] %(name)s – %(message)s",
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
