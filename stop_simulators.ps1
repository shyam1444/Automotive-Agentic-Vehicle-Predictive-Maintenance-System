# Stop all vehicle simulator jobs
# Usage: .\stop_simulators.ps1

Write-Host "🛑 Stopping all vehicle simulators..." -ForegroundColor Yellow

$jobs = Get-Job
if ($jobs.Count -eq 0) {
    Write-Host "No running simulator jobs found." -ForegroundColor Yellow
} else {
    Write-Host "Found $($jobs.Count) running job(s)" -ForegroundColor Cyan
    
    # Stop all jobs
    Get-Job | Stop-Job
    Write-Host "✅ Stopped all jobs" -ForegroundColor Green
    
    # Remove all jobs
    Get-Job | Remove-Job
    Write-Host "✅ Removed all jobs" -ForegroundColor Green
}

