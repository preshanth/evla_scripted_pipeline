#!/usr/bin/env bash
set -euo pipefail

# Convenience script to create a venv and install developer deps using constraints
# Usage: ./scripts/setup_dev_env.sh [venv-path]

VENV_DIR=${1:-".venv"}

python -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

# Install core deps for development (pinned via constraints.txt)
pip install -c ../constraints.txt -r ../dev-requirements.txt

echo "Virtualenv created at $VENV_DIR and dev dependencies installed. Activate with: source $VENV_DIR/bin/activate"