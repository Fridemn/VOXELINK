@echo off
setlocal enabledelayedexpansion

REM Change to the script directory
cd /d "%~dp0"

echo Checking for Conda...
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Conda not found. Please install Miniconda or Anaconda and ensure it's in your PATH.
    pause
    exit /b 1
)

echo Activating backend environment...
call conda activate backend
if %errorlevel% neq 0 (
    echo Error: Failed to activate 'backend' environment. Please ensure the environment exists.
    echo You can create it with: conda create -n backend python=3.x
    pause
    exit /b 1
)

echo Starting GUI application...
start "" pythonw gui.py
if %errorlevel% neq 0 (
    echo Error: Failed to start gui.py.
    pause
    exit /b 1
)

endlocal