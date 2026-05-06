"""Structured logging configuration for code-solver-ai."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any


def setup_logger(
    name: str = "code_solver",
    level: str = "INFO",
    log_file: str | None = None,
    console: bool = True,
) -> logging.Logger:
    """
    Set up a structured logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (default: logs/solver.log)
        console: Whether to add console handler
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Add file handler
    if log_file is None:
        log_file = "logs/solver.log"
    
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "code_solver") -> logging.Logger:
    """
    Get a logger instance, creating it if necessary.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    # Get log level from environment or default to INFO
    level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", "logs/solver.log")
    
    logger = logging.getLogger(name)
    
    # Only setup if logger hasn't been configured yet
    if not logger.handlers:
        setup_logger(name, level, log_file)
    
    return logger


def log_function_call(logger: logging.Logger, func_name: str, **kwargs: Any) -> None:
    """
    Log a function call with parameters.
    
    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function parameters
    """
    params = ", ".join(f"{k}={v}" for k, v in kwargs.items() if v is not None)
    logger.info(f"Calling {func_name}({params})")


def log_pipeline_stage(
    logger: logging.Logger,
    stage: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log pipeline stage activities.
    
    Args:
        logger: Logger instance
        stage: Pipeline stage name
        action: Action being performed
        details: Additional details to log
    """
    message = f"Pipeline {stage}: {action}"
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        message += f" ({detail_str})"
    logger.info(message)


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log an error with context and details.
    
    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Context where error occurred
        details: Additional details
    """
    message = f"Error: {type(error).__name__}: {str(error)}"
    if context:
        message += f" in {context}"
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        message += f" ({detail_str})"
    logger.error(message, exc_info=True)


def log_warning(
    logger: logging.Logger,
    message: str,
    context: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Log a warning with context and details.
    
    Args:
        logger: Logger instance
        message: Warning message
        context: Context where warning occurred
        details: Additional details
    """
    full_message = message
    if context:
        full_message += f" in {context}"
    if details:
        detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
        full_message += f" ({detail_str})"
    logger.warning(full_message)
