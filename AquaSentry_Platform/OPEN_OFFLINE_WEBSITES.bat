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
echo  * The AquaNet-V1 Neural Network runs in-browser (23 nodes, 112 synapses)!
echo  * Multi-analyte catalog, Savitzky-Golay ASV processing, and UI styleguide.
echo.

start "" "%~dp0frontend\index.html"

echo Opened: %~dp0frontend\index.html
echo.
echo You can navigate to all sections using the top navigation bar or the sidebar:
echo   - Water Quality Overview & Empty State (index.html)
echo   - Multi-Contaminant Registry (#section-contaminants)
echo   - Voltammetric Signal Processing (#section-voltammetry)
echo   - Neural Network Classifier (#section-neural)
echo   - Component Styleguide (styleguide.html)
echo   - Commercial Sales & Expansion (sales-expansion.html)
echo   - Market & Economic Research (market-research.html)
echo.
echo To run the full system with live API database ingestion and the Gemini AI chatbot,
echo run "START_AQUASENTRY.bat" instead.
echo.
pause
