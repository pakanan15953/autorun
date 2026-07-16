@echo off
title Cookie Run AI Bot Installer
cd /d "%~dp0"
echo ===================================================
echo   Cookie Run AI Bot - Setup and Dependencies Installer
echo ===================================================
echo.
echo [*] Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to PATH!
    echo Please install Python 3.8 or newer from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Make sure to check the box "Add Python to PATH" 
    echo during the installation setup window!
    echo.
    pause
    exit
)

echo [OK] Python detected.
echo.

if not exist ".venv" (
    echo [*] Creating local Python environment [.venv]...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit
    )
    echo [OK] local environment [.venv] created successfully.
) else (
    echo [OK] local environment [.venv] already exists. Skipping creation.
)

echo.
echo [*] Activating environment and installing required libraries...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo.
echo [*] Downloading and installing dependencies (ultralytics, opencv, pywin32)...
echo [*] This might take a couple of minutes depending on your internet connection...
pip install opencv-python numpy pywin32 ultralytics customtkinter
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Installation failed! Please check your internet connection.
    pause
    exit
)

echo.
echo ===================================================
echo   Setup completed successfully!
echo   You can now run the bot by double-clicking 'Run_Bot.bat'.
echo ===================================================
pause
