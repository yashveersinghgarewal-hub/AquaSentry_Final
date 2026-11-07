@echo off
REM ==============================================================================
REM AquaSentry Universal Test Runner (Windows)
REM Runs every test across the Neural Network toolkit and the Web Platform
REM ==============================================================================

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "AquaSentry_Platform\.venv\Scripts\activate.bat" (
    call AquaSentry_Platform\.venv\Scripts\activate.bat
)

python main.py --test
pause
