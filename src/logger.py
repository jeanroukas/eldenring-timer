import logging
import os
import json
import time
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

# Global Context Store (Simpler than ThreadLocal for this single-threaded app)
_LOG_CONTEXT: Dict[str, Any] = {
    "session_id": "startup",
    "phase": "init",
    "run_time": 0.0
}

def update_log_context(key: str, value: Any):
    """Update a specific field in the global log context."""
    _LOG_CONTEXT[key] = value

def get_log_context() -> Dict[str, Any]:
    return _LOG_CONTEXT.copy()

class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs JSON messages.
    Includes global context and extra fields passed in the log record.
    """
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "context": _LOG_CONTEXT.copy()
        }
        
        # Merge 'extra' fields if available (e.g. logger.info(..., extra={'foo': 'bar'}))
        if hasattr(record, 'data'):
            log_obj['data'] = record.data
            
        # Add source info for errors
        if record.levelno >= logging.ERROR:
            log_obj["source"] = {
                "file": record.filename,
                "line": record.lineno,
                "func": record.funcName
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

def setup_logger():
    """
    Sets up a unified logger for the application.
    Logs INFO to console (Human Readable) and DEBUG to 'application.jsonl' (Machine Readable).
    """
    logger = logging.getLogger("EldenRingTimer")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # 1. Console Handler (Text - for Humans)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    # 2. File Handler (JSON - for Machines)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_file = os.path.join(project_root, "application.jsonl") # Changed extension to .jsonl
    
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Singleton access
logger = setup_logger()
# Expose context updater
logger.update_context = update_log_context
