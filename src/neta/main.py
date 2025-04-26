"""Main entry point for NETA application."""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# Add the src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neta.core.automation import NetaAutomation
from neta.utils.logging import setup_logger

# Load environment variables
load_dotenv()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="NETA: WhatsApp-AI chat integration bridge")

    parser.add_argument(
        "--config", type=str, help="Path to configuration file (default: from env or config.json)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default="automation.log",
        help="Path to log file (default: automation.log)",
    )

    return parser.parse_args()


def main():
    """Main entry point for NETA application."""
    args = parse_arguments()

    # Set up logging with specified level
    log_level = getattr(logging, args.log_level)
    logger = setup_logger(log_level, args.log_file)

    logger.info("Starting NETA application")

    try:
        # Initialize and run automation
        automation = NetaAutomation(args.config)
        automation.run()
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)

    logger.info("NETA application terminated")


if __name__ == "__main__":
    main()
