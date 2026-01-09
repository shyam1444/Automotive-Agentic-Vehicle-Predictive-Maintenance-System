# Windows PowerShell script to set up Python virtual environment
# This script will:
# 1. Check if Python is installed
# 2. Create a virtual environment
# 3. Activate it and install dependencies

Write-Host "=== Python Virtual Environment Setup ===" -ForegroundColor Cyan

# Check for Python
$pythonCmd = $null
$pythonVersions = @("python", "python3", "py")

foreach ($cmd in $pythonVersions) {
    try {
        $version = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $pythonCmd = $cmd
            Write-Host "Found Python: $version" -ForegroundColor Green
            break
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Host "ERROR: Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.11+ from one of these sources:" -ForegroundColor Yellow
    Write-Host "  1. Microsoft Store: Search for 'Python 3.11' or 'Python 3.12'" -ForegroundColor Yellow
    Write-Host "  2. Official website: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "  3. Anaconda: https://www.anaconda.com/download" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "After installing Python, make sure to:" -ForegroundColor Yellow
    Write-Host "  - Check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    Write-Host "  - Restart your terminal/PowerShell" -ForegroundColor Yellow
    exit 1
}

# Check Python version
$versionOutput = & $pythonCmd --version 2>&1
$versionMatch = $versionOutput -match "Python (\d+)\.(\d+)"
if ($versionMatch) {
    $majorVersion = [int]$matches[1]
    $minorVersion = [int]$matches[2]
    if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 11)) {
        Write-Host "WARNING: Python 3.11+ is recommended. You have Python $majorVersion.$minorVersion" -ForegroundColor Yellow
    }
}

# Remove existing venv if it exists
if (Test-Path "venv") {
    Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

# Create virtual environment
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
& $pythonCmd -m venv venv

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create virtual environment!" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& "venv\Scripts\Activate.ps1"

if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: Failed to activate virtual environment automatically." -ForegroundColor Yellow
    Write-Host "You may need to run: venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "If you get an execution policy error, run:" -ForegroundColor Yellow
    Write-Host "  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Yellow
}

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Cyan
& python -m pip install --upgrade pip

# Install dependencies
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Cyan
if (Test-Path "requirements.txt") {
    & python -m pip install -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "=== Setup Complete! ===" -ForegroundColor Green
        Write-Host "Virtual environment is ready at: venv" -ForegroundColor Green
        Write-Host ""
        Write-Host "To activate the virtual environment in the future, run:" -ForegroundColor Cyan
        Write-Host "  venv\Scripts\Activate.ps1" -ForegroundColor White
        Write-Host ""
        Write-Host "To deactivate, run:" -ForegroundColor Cyan
        Write-Host "  deactivate" -ForegroundColor White
    } else {
        Write-Host "ERROR: Failed to install some dependencies!" -ForegroundColor Red
        Write-Host "Please check the error messages above." -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "ERROR: requirements.txt not found!" -ForegroundColor Red
    exit 1
}

