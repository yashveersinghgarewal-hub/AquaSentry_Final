@echo off
REM Optional: build a standalone AquaSentry.exe (no Python needed on the target PC).
REM Run "Start AquaSentry Desktop.bat" once first so .venv exists.
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m pip install pyinstaller
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --name AquaSentry ^
  --paths AquaSentry_Platform ^
  --hidden-import app.main ^
  --collect-submodules uvicorn ^
  --collect-all reportlab ^
  --add-data "AquaSentry_Platform\frontend;frontend" ^
  --add-data "AquaSentry_Platform\aquasentry.db;." ^
  desktop_app.py
echo.
echo Done. Your app is in: dist\AquaSentry\AquaSentry.exe
echo Copy the whole dist\AquaSentry folder to share it.
pause
