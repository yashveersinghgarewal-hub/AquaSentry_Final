@echo off
title AquaSentry Launcher
color 0B
cd /d "%~dp0"

echo ===============================================================================
echo                      AQUASENTRY AUTONOMOUS WATER SYSTEM
echo           AI-Powered Arsenic Surveillance & AquaNet-V1 Neural Classifier
echo ===============================================================================
echo.

:: 1. Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo (Make sure to check "Add Python to PATH" during installation)
    echo.
    echo In the meantime, you can still view all websites offline without Python!
    echo Simply double-click "OPEN_OFFLINE_WEBSITES.bat" or open "frontend\index.html".
    echo.
    pause
    exit /b 1
)

:: 2. Check/create virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [*] Setting up local Python virtual environment (.venv)...
    python -m venv .venv
    echo [*] Installing required packages from requirements.txt...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    echo [*] Dependencies installed successfully!
    echo.
)

:: 3. Launch the Backend API Server (FastAPI + Uvicorn)
echo [*] Launching FastAPI Backend on http://127.0.0.1:8000 ...
start "AquaSentry API Server (Port 8000)" /D "%~dp0" ".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

:: 4. Launch the Frontend Web Server
echo [*] Launching Frontend Web Server on http://127.0.0.1:8001 ...
start "AquaSentry Web Server (Port 8001)" /D "%~dp0frontend" ".venv\Scripts\python.exe" -m http.server 8001

:: 5. Wait 2 seconds for servers to initialize
timeout /t 2 /nobreak >nul

:: 6. Automatically open in default browser
echo [*] Opening AquaSentry Scientific Water Quality Dashboard in your web browser...
start "" "http://127.0.0.1:8001/index.html"

echo.
echo ===============================================================================
echo                        AQUASENTRY IS NOW RUNNING!
echo ===============================================================================
echo.
echo   [1] Live Water Quality Dashboard & Instrument Overview:
echo       -> http://localhost:8001/index.html
echo       -> http://localhost:8001/index.html#section-neural
echo       -> http://localhost:8001/styleguide.html
echo.
echo   [2] Commercial Sales & Expansion Strategy:
echo       -> http://localhost:8001/sales-expansion.html
echo.
echo   [3] Market & Economic Feasibility Research:
echo       -> http://localhost:8001/market-research.html
echo.
echo   [4] Interactive Backend API & Neural Inference Docs:
echo       -> http://localhost:8000/docs
echo.
echo   [5] AI Chatbot Agent:
echo       -> Click the glowing blue chat button on the bottom-right of any page!
echo.
echo ===============================================================================
echo  NOTE: To stop AquaSentry, simply close the two server terminal windows.
echo ===============================================================================
echo.
pause
