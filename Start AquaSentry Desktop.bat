@echo off
REM ======================================================================
REM  AquaSentry Desktop (Windows) - double-click to run.
REM  First run: creates .venv and installs packages (a few minutes).
REM  Later runs: opens straight away.
REM ======================================================================
cd /d "%~dp0"
title AquaSentry Desktop

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during setup.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [*] Creating virtual environment .venv ...
  python -m venv .venv
)

if not exist ".venv\.desktop_ready" (
  echo [*] Installing packages - first run only ...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-desktop.txt
  if errorlevel 1 (
    echo [ERROR] Package install failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
  echo ok> ".venv\.desktop_ready"
)

echo [*] Starting AquaSentry ... (close the AquaSentry window to stop)
".venv\Scripts\python.exe" desktop_app.py
if errorlevel 1 pause
