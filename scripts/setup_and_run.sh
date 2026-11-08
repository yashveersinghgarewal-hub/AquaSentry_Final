#!/usr/bin/env bash
# ==============================================================================
# AquaSentry Universal All-In-One Launcher (macOS & Linux)
# ==============================================================================
# This script configures a brand-new computer to run AquaSentry in 1 click:
#   1. Detects Python 3
#   2. Creates a clean, isolated local virtual environment (.venv)
#   3. Installs all required packages from requirements.txt
#   4. Runs verification health check
#   5. Launches the AquaSentry web application and opens the dashboard
# ==============================================================================

set -e

# Change to script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR/.."   # scripts/ lives one level below the repository root

echo "======================================================================"
echo "    AquaSentry Universal All-In-One Automated Launcher"
echo "======================================================================"

# 1. Check Python installation
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python 3 was not found on your system."
    echo "Please install Python 3.9+ from https://www.python.org/ or via package manager."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version)
echo "[+] Detected: $PYTHON_VERSION"

# 2. Create or verify virtual environment
if [ ! -d ".venv" ]; then
    echo "[*] Creating fresh virtual environment in .venv..."
    $PYTHON_CMD -m venv .venv
fi

# 3. Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "[ERROR] Could not find .venv/bin/activate."
    exit 1
fi

echo "[+] Virtual environment active: $(which python)"

# 4. Install dependencies
echo "[*] Verifying & installing dependencies from requirements.txt..."
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

# 5. Quick verification test
echo "[*] Running verification check..."
python main.py --version

# 6. Open browser and start server
PORT=8000
echo ""
echo "======================================================================"
echo "  AquaSentry is ready! Starting web server on http://localhost:$PORT"
echo "  Press Ctrl+C to stop the server anytime."
echo "======================================================================"
echo ""

# Try opening browser in background after short delay
(
    sleep 2
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:$PORT"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:$PORT"
    fi
) &

python main.py --serve --port "$PORT"
