# Start 11 vehicle simulators in background
# Usage: .\start_simulators.ps1

Write-Host "🚗 Starting 11 vehicle simulators..." -ForegroundColor Cyan

# Get current directory and Python path
$currentDir = Get-Location
$pythonPath = (Get-Command python).Source

# Check if Python is available
if (-not $pythonPath) {
    Write-Host "❌ Python not found! Please activate your virtual environment." -ForegroundColor Red
    exit 1
}

# Check if simulator file exists
if (-not (Test-Path "simulators/vehicle_simulator.py")) {
    Write-Host "❌ Simulator file not found: simulators/vehicle_simulator.py" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Python found: $pythonPath" -ForegroundColor Green
Write-Host "✅ Working directory: $currentDir" -ForegroundColor Green
Write-Host ""

# Start simulators as background jobs
$jobs = @()
for ($i = 1; $i -le 11; $i++) {
    Write-Host "Starting simulator $i/11..." -ForegroundColor Yellow -NoNewline
    
    $job = Start-Job -ScriptBlock {
        param($dir, $pyPath, $scriptPath)
        Set-Location $dir
        & $pyPath $scriptPath
    } -ArgumentList $currentDir, $pythonPath, "simulators/vehicle_simulator.py"
    
    $jobs += $job
    Write-Host " [Job ID: $($job.Id)]" -ForegroundColor Green
    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Host "✅ Started 11 simulators in background!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Useful commands:" -ForegroundColor Cyan
Write-Host "  Get-Job                    # Check running jobs" -ForegroundColor White
Write-Host "  Receive-Job -Id <JobId>    # View output from a job" -ForegroundColor White
Write-Host "  .\stop_simulators.ps1      # Stop all simulators" -ForegroundColor White
Write-Host ""

# Show running jobs
Get-Job | Format-Table -AutoSize

