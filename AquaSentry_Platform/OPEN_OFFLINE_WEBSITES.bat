@echo off
title AquaSentry Offline Web Viewer
color 0A
cd /d "%~dp0"

echo ===============================================================================
echo                      AQUASENTRY - OFFLINE WEB VIEWER
echo ===============================================================================
echo.
echo Opening the AquaSentry portals directly in your default browser...
echo.
echo  * Zero installation required!
echo  * The AquaNet-V3 neural network runs in the browser (352 weights), English and Hindi.
echo  * Safety steps, authority report, 3D device view, market and sales pages.
echo.

start "" "%~dp0frontend\index.html"

echo Opened: %~dp0frontend\index.html
echo.
echo You can reach every page from the sidebar:
echo   - Live dashboard: result, what to do, contact authorities, test, AquaNet, 3D device (index.html)
echo   - Market research with charts and globe (market-research.html)
echo   - Sales and expansion with ROI calculator (sales-expansion.html)
echo   - MAS-G1 device simulator (device-simulator.html)
echo.
echo To run the full system with live API database ingestion and the Gemini AI chatbot,
echo run "START_AQUASENTRY.bat" instead.
echo.
pause
