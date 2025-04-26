#!/bin/bash
# Script to run NETA with standard settings

# Go to project root directory
cd "$(dirname "$0")/.." || exit 1

# Ensure required directories exist
mkdir -p data logs

# Set environment if .env exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Default config path
CONFIG_PATH=${CONFIG_PATH:-config/default.json}

# Run the application
if command -v poetry &> /dev/null; then
  # Using Poetry if available
  poetry run neta --config "$CONFIG_PATH" --log-file logs/neta.log
else
  # Direct Python execution as fallback
  python -m src.neta.main --config "$CONFIG_PATH" --log-file logs/neta.log
fi