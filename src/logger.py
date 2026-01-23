import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    """
    Sets up a unified logger for the application.
    Logs INFO to console and DEBUG to 'application.log'.
    Uses RotatingFileHandler to manage log size.
    """
    logger = logging.getLogger("EldenRingTimer")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # File Handler (Rotating)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_file = os.path.join(project_root, "application.log")
    
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Singleton access
logger = setup_logger()
