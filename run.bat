@echo off
title FitBuddy Setup and Run
cd /d "%~dp0"

echo ==========================================
echo          FitBuddy - NM Project
echo ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo Please install Python 3.10 or later and tick "Add Python to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo Installing/updating required packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Package installation failed. Check your internet connection.
    pause
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo A new .env file has been created.
    echo Put your Gemini API key into the .env file.
    echo Notepad will open now.
    start "" notepad ".env"
    echo.
    pause
)

echo.
echo Starting FitBuddy at http://127.0.0.1:8000
echo Keep this window open while using the app.
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5050/generate-workout"
".venv\Scripts\python.exe" app.py

pause
