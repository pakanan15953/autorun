@echo off
title Cookie Run AI Bot Launcher
cd /d "%~dp0"
echo ===================================================
echo   Cookie Run AI Background Bot (MuMu Player)
echo ===================================================
echo.
echo [*] Checking virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo [OK] Virtual environment found. Starting bot...
    echo.
    .venv\Scripts\python.exe main.py
) else (
    echo [!] Warning: .venv folder not found. Running using system python...
    echo.
    python main.py
)
echo.
echo ===================================================
echo   Bot has been stopped.
echo ===================================================
pause
