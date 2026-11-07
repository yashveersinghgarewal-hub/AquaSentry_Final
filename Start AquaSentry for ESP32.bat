@echo off
REM Starts AquaSentry so the ESP32 on your Wi-Fi can send readings (port 8000).
REM Run "Start AquaSentry Desktop.bat" once first so the .venv folder exists.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Run "Start AquaSentry Desktop.bat" once first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" desktop_app.py --lan --browser
pause
