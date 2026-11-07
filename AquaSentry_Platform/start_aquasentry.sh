#!/usr/bin/env bash
# AquaSentry Launcher for macOS / Linux
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "==============================================================================="
echo "                     AQUASENTRY AUTONOMOUS WATER SYSTEM"
echo "          AI-Powered Arsenic Surveillance & AquaNet-V1 Neural Classifier"
echo "==============================================================================="
echo ""

# 1. Check Python installation
PYTHON_BIN=""
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "[ERROR] Python 3 is not installed or not in your PATH!"
    exit 1
fi

# 2. Check virtual environment
if [ ! -f "$DIR/.venv/bin/python" ]; then
    echo "[*] Setting up local Python virtual environment (.venv)..."
    "$PYTHON_BIN" -m venv .venv
    echo "[*] Installing required packages from requirements.txt..."
    "$DIR/.venv/bin/pip" install --upgrade pip
    "$DIR/.venv/bin/pip" install -r requirements.txt
    echo "[*] Dependencies installed successfully!"
    echo ""
fi

VENV_PYTHON="$DIR/.venv/bin/python"

cleanup() {
    echo ""
    echo "[*] Stopping AquaSentry services..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "[*] AquaSentry stopped."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 3. Launch Backend API Server (FastAPI + Uvicorn)
echo "[*] Launching FastAPI Backend on http://127.0.0.1:8000 ..."
"$VENV_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# 4. Launch Frontend Web Server
echo "[*] Launching Frontend Web Server on http://127.0.0.1:8001 ..."
(cd "$DIR/frontend" && "$VENV_PYTHON" -m http.server 8001) &
FRONTEND_PID=$!

# Wait 2 seconds
sleep 2

# 5. Open browser
echo "[*] Opening AquaSentry Scientific Water Quality Dashboard in your web browser..."
if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:8001/index.html"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:8001/index.html"
fi

echo ""
echo "==============================================================================="
echo "                       AQUASENTRY IS NOW RUNNING!"
echo "==============================================================================="
echo ""
echo "  [1] Live Water Quality Dashboard & Instrument Overview:"
echo "      -> http://localhost:8001/index.html"
echo "      -> http://localhost:8001/index.html#section-neural"
echo "      -> http://localhost:8001/styleguide.html"
echo ""
echo "  [2] Commercial Sales & Expansion Strategy:"
echo "      -> http://localhost:8001/sales-expansion.html"
echo ""
echo "  [3] Market & Economic Feasibility Research:"
echo "      -> http://localhost:8001/market-research.html"
echo ""
echo "  [4] Interactive Backend API & Neural Inference Docs:"
echo "      -> http://localhost:8000/docs"
echo ""
echo "  [5] AI Chatbot Agent:"
echo "      -> Click the glowing blue chat button on the bottom-right of any page!"
echo ""
echo "==============================================================================="
echo " Press Ctrl+C in this terminal window to stop all AquaSentry services."
echo "==============================================================================="
echo ""

wait $BACKEND_PID $FRONTEND_PID
