@echo off
REM Windows Batch script to set up Python virtual environment
REM This is a fallback if PowerShell script doesn't work

echo === Python Virtual Environment Setup ===

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.11+ from:
    echo   1. Microsoft Store: Search for "Python 3.11" or "Python 3.12"
    echo   2. Official website: https://www.python.org/downloads/
    echo   3. Anaconda: https://www.anaconda.com/download
    echo.
    echo After installing Python, make sure to:
    echo   - Check "Add Python to PATH" during installation
    echo   - Restart your terminal
    exit /b 1
)

REM Remove existing venv if it exists
if exist venv (
    echo Removing existing virtual environment...
    rmdir /s /q venv
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment!
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies from requirements.txt...
if exist requirements.txt (
    python -m pip install -r requirements.txt
    if %errorlevel% equ 0 (
        echo.
        echo === Setup Complete! ===
        echo Virtual environment is ready at: venv
        echo.
        echo To activate the virtual environment in the future, run:
        echo   venv\Scripts\activate.bat
        echo.
        echo To deactivate, run:
        echo   deactivate
    ) else (
        echo ERROR: Failed to install some dependencies!
        echo Please check the error messages above.
        exit /b 1
    )
) else (
    echo ERROR: requirements.txt not found!
    exit /b 1
)

