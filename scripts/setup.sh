#!/bin/bash
# Script to set up NETA development environment

# Go to project root directory
cd "$(dirname "$0")/.." || exit 1

# Create directories
mkdir -p data logs

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env file from example. Please edit with your specific settings."
fi

# Install dependencies with Poetry
if command -v poetry &> /dev/null; then
  echo "Installing dependencies with Poetry..."
  poetry install
else
  echo "Poetry not found. Please install Poetry first:"
  echo "curl -sSL https://install.python-poetry.org | python3 -"
  exit 1
fi

# Make scripts executable
chmod +x scripts/*.sh

echo "
Setup complete! Next steps:
1. Edit .env file with your configuration
2. Review config/default.json for AI mappings
3. Run the application with: scripts/run.sh
"