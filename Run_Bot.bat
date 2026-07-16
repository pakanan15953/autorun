@echo off
title Cookie Run AI Bot Launcher
cd /d "%~dp0"
echo ===================================================
echo   Cookie Run AI Background Bot (MuMu Player)
echo ===================================================
echo.
echo [*] Checking virtual environment...
if exist ".venv\Scripts\activate.bat" (
    echo [OK] Virtual environment found. Activating...
    call .venv\Scripts\activate.bat
) else (
    echo [!] Warning: .venv folder not found. Running using system python...
)
echo.
echo [*] Starting yolo_bot.py...
python yolo_bot.py
echo.
echo ===================================================
echo   Bot has been stopped.
echo ===================================================
pause
