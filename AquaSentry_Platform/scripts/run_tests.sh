#!/usr/bin/env bash
# AquaSentry 1-Click Automated Scientific Test Runner
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." >/dev/null 2>&1 && pwd )"

# Sync neural network before running tests
if [ -f "$DIR/AquaSentry_Complete_System/.venv/bin/python" ]; then
    "$DIR/AquaSentry_Complete_System/.venv/bin/python" "$DIR/scripts/sync_neural_network.py"
fi

cd "$DIR/AquaSentry_Complete_System"
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python run_tests.py "$@"
else
    python3 run_tests.py "$@"
fi
