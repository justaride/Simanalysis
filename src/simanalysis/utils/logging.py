"""
Logging configuration for Simanalysis.

Provides structured logging with console and file output support.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


# Default log format
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Default log directory
DEFAULT_LOG_DIR = Path.home() / '.simanalysis' / 'logs'


class ColoredConsoleFormatter(logging.Formatter):
    """
    Colored console formatter for better readability.

    Uses ANSI color codes to colorize log levels:
    - DEBUG: Cyan
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Red + Bold
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[1;31m', # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Color the level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        result = super().format(record)

        # Reset levelname for other handlers
        record.levelname = levelname

        return result


def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console: bool = True,
    colored: bool = True,
    file_rotation: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
) -> logging.Logger:
    """
    Configure application-wide logging for Simanalysis.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, no file logging.
        console: Enable console (stderr) logging
        colored: Use colored output for console (only if console=True)
        file_rotation: Use rotating file handler (only if log_file provided)
        max_bytes: Maximum log file size before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
        format_string: Custom log format string
        date_format: Custom date format string

    Returns:
        Root logger instance

    Example:
        >>> setup_logging(level="DEBUG", log_file=Path("analysis.log"))
        >>> logger = logging.getLogger(__name__)
        >>> logger.info("Starting analysis")
    """
    # Get root logger for simanalysis
    root_logger = logging.getLogger("simanalysis")

    # Convert level string to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers = []

    # Set format
    fmt = format_string or DEFAULT_LOG_FORMAT
    date_fmt = date_format or DEFAULT_DATE_FORMAT

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(log_level)

        if colored and sys.stderr.isatty():
            # Use colored formatter for TTY
            console_formatter = ColoredConsoleFormatter(fmt, datefmt=date_fmt)
        else:
            # Plain formatter for pipes/redirects
            console_formatter = logging.Formatter(fmt, datefmt=date_fmt)

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        # Ensure log directory exists
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if file_rotation:
            # Rotating file handler
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
        else:
            # Simple file handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')

        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(fmt, datefmt=date_fmt)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Don't propagate to root logger
    root_logger.propagate = False

    return root_logger


def get_default_log_file() -> Path:
    """
    Get default log file path.

    Returns:
        Path to default log file: ~/.simanalysis/logs/simanalysis.log
    """
    return DEFAULT_LOG_DIR / 'simanalysis.log'


def configure_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger for a specific module.

    Args:
        name: Logger name (usually __name__)
        level: Optional log level override

    Returns:
        Configured logger instance

    Example:
        >>> logger = configure_logger(__name__)
        >>> logger.info("Module initialized")
    """
    logger = logging.getLogger(name)

    if level:
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    return logger


def silence_logger(name: str):
    """
    Silence a specific logger.

    Args:
        name: Logger name to silence

    Example:
        >>> silence_logger("simanalysis.parsers.dbpf")
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.CRITICAL + 1)  # Above CRITICAL


def reset_logging():
    """
    Reset all logging configuration.

    Removes all handlers and resets log levels.
    Useful for testing.
    """
    root_logger = logging.getLogger("simanalysis")
    root_logger.handlers = []
    root_logger.setLevel(logging.NOTSET)
    root_logger.propagate = True


def log_exception(logger: logging.Logger, exc: Exception, message: Optional[str] = None):
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance
        exc: Exception to log
        message: Optional custom message

    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_exception(logger, e, "Operation failed")
    """
    if message:
        logger.error(f"{message}: {exc}", exc_info=True)
    else:
        logger.error(f"{type(exc).__name__}: {exc}", exc_info=True)


# Module-level logger for this utils module
logger = configure_logger(__name__)
