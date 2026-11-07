@echo off
title AquaSentry Test Suite Runner
color 0A
cd /d "%~dp0"

echo ===============================================================================
echo                AQUASENTRY AUTOMATED SCIENTIFIC TEST SUITE
echo ===============================================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_tests.py
) else (
    python run_tests.py
)

echo.
echo ===============================================================================
pause
