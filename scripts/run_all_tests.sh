#!/usr/bin/env bash
# ==============================================================================
# AquaSentry Universal Test Runner (macOS & Linux)
# Runs every test across the Neural Network toolkit and the Web Platform
# ==============================================================================

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."   # scripts/ lives one level below the repository root

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "AquaSentry_Platform/.venv/bin/activate" ]; then
    source AquaSentry_Platform/.venv/bin/activate
fi

python3 main.py --test
