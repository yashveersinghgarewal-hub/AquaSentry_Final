@echo off
REM scripts\ lives one level below the repository root
cd /d "%~dp0.."
REM ==============================================================================
REM AquaSentry Universal All-In-One Launcher (Windows)
REM ==============================================================================
REM This script configures a brand-new Windows PC to run AquaSentry in 1 click:
REM   1. Detects Python 3
REM   2. Creates a clean, isolated local virtual environment (.venv)
REM   3. Installs all required packages from requirements.txt
REM   4. Launches the AquaSentry web application and opens the dashboard
REM ==============================================================================

setlocal enabledelayedexpansion
title AquaSentry Universal Launcher

echo ======================================================================
echo     AquaSentry Universal All-In-One Automated Launcher
echo ======================================================================

REM 1. Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Python was not found on this computer.
        echo Please install Python 3.9+ from https://www.python.org/
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py -3
    )
) else (
    set PYTHON_CMD=python
)

echo [+] Using Python: %PYTHON_CMD%

REM 2. Create virtual environment if missing
if not exist ".venv" (
    echo [*] Creating fresh virtual environment in .venv...
    %PYTHON_CMD% -m venv .venv
)

REM 3. Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Could not find .venv\Scripts\activate.bat
    pause
    exit /b 1
)

REM 4. Install dependencies
echo [*] Verifying and installing requirements...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet

REM 5. Open browser and start server
set PORT=8000
echo.
echo ======================================================================
echo   AquaSentry is ready! Starting web server on http://localhost:%PORT%
echo   Press Ctrl+C in this window to stop the server anytime.
echo ======================================================================
echo.

start "" "http://localhost:%PORT%"
python main.py --serve --port %PORT%

pause
