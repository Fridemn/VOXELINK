@echo off
setlocal enabledelayedexpansion

REM Change to the script directory
cd /d "%~dp0"

echo Checking for Python runtime...
if not exist "runtime\pythonw.exe" (
    echo Error: Python runtime not found at runtime\pythonw.exe
    pause
    exit /b 1
)

echo Starting GUI application...
start "" runtime\pythonw.exe gui.py
if %errorlevel% neq 0 (
    echo Error: Failed to start gui.py.
    pause
    exit /b 1
)

endlocal