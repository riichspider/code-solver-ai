"""Test cases for utils/logger.py"""

import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from utils.logger import setup_logger


class TestSetupLogger:
    """Test cases for the setup_logger function."""

    def test_setup_logger_default_configuration(self):
        """Test logger setup with default parameters."""
        logger = setup_logger()

        assert logger.name == "code_solver"
        assert logger.level == logging.INFO
        # Should have both console and file handlers by default
        assert len(logger.handlers) == 2
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "FileHandler" in handler_types

    def test_setup_logger_custom_name(self):
        """Test logger setup with custom name."""
        custom_name = "custom_logger"
        logger = setup_logger(name=custom_name)

        assert logger.name == custom_name

    def test_setup_logger_different_log_levels(self):
        """Test logger setup with different log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level_str in levels:
            logger = setup_logger(level=level_str)
            expected_level = getattr(logging, level_str)
            assert logger.level == expected_level

    def test_setup_logger_with_file_handler(self):
        """Test logger setup with file handler."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            logger = setup_logger(console=False, log_file=log_file)

            # Should have only file handler (console disabled)
            assert len(logger.handlers) == 1

            # Check file handler exists
            file_handlers = [h for h in logger.handlers if isinstance(
                h, logging.FileHandler)]
            assert len(file_handlers) == 1

            # Test writing to file
            logger.info("Test message")
            assert os.path.exists(log_file)

            # Check file content
            with open(log_file, 'r') as f:
                content = f.read()
                assert "Test message" in content

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

    def test_setup_logger_console_only(self):
        """Test logger setup with console only (no file)."""
        logger = setup_logger(console=True, log_file=None)

        # Should have console handler and default file handler
        assert len(logger.handlers) == 2
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "StreamHandler" in handler_types
        assert "FileHandler" in handler_types

    def test_setup_logger_file_only(self):
        """Test logger setup with file only (no console)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            logger = setup_logger(console=False, log_file=log_file)

            # Should have only file handler
            assert len(logger.handlers) == 1
            assert isinstance(logger.handlers[0], logging.FileHandler)

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

    def test_setup_logger_creates_log_directory(self):
        """Test that logger creates log directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_log_file = os.path.join(temp_dir, "logs", "test.log")

            # Directory doesn't exist initially
            assert not os.path.exists(os.path.dirname(nested_log_file))

            logger = setup_logger(console=False, log_file=nested_log_file)
            logger.info("Test message")

            # Directory should be created
            assert os.path.exists(os.path.dirname(nested_log_file))
            assert os.path.exists(nested_log_file)

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

    def test_setup_logger_default_log_file(self):
        """Test logger setup with default log file path."""
        with patch('os.makedirs') as mock_makedirs:
            logger = setup_logger(log_file=None)  # Should use default

            # Should not try to create directory if no log file specified
            mock_makedirs.assert_not_called()

    def test_setup_logger_idempotent(self):
        """Test that calling setup_logger multiple times doesn't duplicate handlers."""
        logger = setup_logger(name="test_idempotent")
        initial_handler_count = len(logger.handlers)

        # Call setup_logger again with same name
        logger2 = setup_logger(name="test_idempotent")

        # Should not add duplicate handlers
        assert len(logger2.handlers) == initial_handler_count

    def test_setup_logger_log_format(self):
        """Test that log messages have proper format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            logger = setup_logger(console=False, log_file=log_file)

            logger.info("Test message")

            with open(log_file, 'r') as f:
                content = f.read()
                # Should contain timestamp, level, and message
                assert "INFO" in content
                assert "Test message" in content

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

    def test_setup_logger_different_message_types(self):
        """Test logger with different types of log messages."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            logger = setup_logger(
                level="DEBUG", console=False, log_file=log_file)

            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")

            with open(log_file, 'r') as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content
                assert "Warning message" in content
                assert "Error message" in content
                assert "Critical message" in content

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()

    def test_setup_logger_with_path_object(self):
        """Test logger setup with Path object for log file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "test.log"
            logger = setup_logger(console=False, log_file=str(log_path))

            logger.info("Test message")
            assert log_path.exists()

            with open(log_path, 'r') as f:
                content = f.read()
                assert "Test message" in content

            # Close all handlers to allow Windows to delete temp directory
            for handler in logger.handlers:
                handler.close()
            logger.handlers.clear()
