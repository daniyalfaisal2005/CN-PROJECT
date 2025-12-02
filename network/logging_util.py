"""
Logging configuration and utilities for the P2P election system.
"""
import logging
import os
from datetime import datetime
import threading


# Global log callbacks for unified logging
_log_callbacks = []
_callbacks_lock = threading.Lock()


def add_log_callback(callback):
    """Add a callback function to be called when a log is created.
    Callback signature: callback(level, logger_name, message)
    """
    with _callbacks_lock:
        _log_callbacks.append(callback)


def remove_log_callback(callback):
    """Remove a log callback."""
    with _callbacks_lock:
        if callback in _log_callbacks:
            _log_callbacks.remove(callback)


class CallbackHandler(logging.Handler):
    """Custom handler that calls registered callbacks."""
    
    def emit(self, record):
        try:
            with _callbacks_lock:
                for callback in _log_callbacks:
                    try:
                        callback(record.levelname, record.name, record.getMessage())
                    except Exception:
                        pass
        except Exception:
            pass


def setup_logging(log_dir: str = 'logs', level=logging.DEBUG):
    """Configure logging for the application."""
    os.makedirs(log_dir, exist_ok=True)

    # Use single log file that gets overwritten
    log_file = os.path.join(log_dir, 'p2p_election.log')

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler (mode='w' to overwrite, not append)
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Callback handler for unified logging
    callback_handler = CallbackHandler()
    callback_handler.setLevel(level)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(callback_handler)

    return log_file


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)


class LogBuffer:
    """Buffer for collecting recent log messages."""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.logs = []
        self.lock = __import__('asyncio').Lock()

    async def add(self, level: str, message: str):
        """Add a log message."""
        async with self.lock:
            self.logs.append({
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'message': message
            })
            if len(self.logs) > self.max_size:
                self.logs.pop(0)

    async def get_recent(self, count: int = 100) -> list:
        """Get recent log messages."""
        async with self.lock:
            return self.logs[-count:]

    async def clear(self):
        """Clear log buffer."""
        async with self.lock:
            self.logs.clear()
