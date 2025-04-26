"""Logging utilities for NETA."""

import logging
import os
from pathlib import Path


def setup_logger(log_level=logging.INFO, log_file="automation.log"):
    """
    Set up application logger with file and console handlers.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: automation.log)
        
    Returns:
        Logger instance
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    if log_path.parent != Path("."):
        os.makedirs(log_path.parent, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)