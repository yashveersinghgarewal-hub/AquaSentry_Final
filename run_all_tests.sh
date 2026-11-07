#!/usr/bin/env bash
# ==============================================================================
# AquaSentry Universal Test Runner (macOS & Linux)
# Runs all 110 tests across the Neural Network and Web Platform
# ==============================================================================

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "AquaSentry_Platform/.venv/bin/activate" ]; then
    source AquaSentry_Platform/.venv/bin/activate
fi

python3 main.py --test
