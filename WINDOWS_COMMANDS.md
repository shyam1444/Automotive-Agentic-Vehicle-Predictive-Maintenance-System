# Windows PowerShell Commands Reference

## Running Multiple Vehicle Simulators

### Option 1: Using Start-Job (Recommended)
```powershell
1..11 | ForEach-Object { Start-Job -ScriptBlock { python simulators/vehicle_simulator.py } }
```

### Option 2: Using Start-Process with full Python path
```powershell
$pythonPath = (Get-Command python).Source
1..11 | ForEach-Object { Start-Process $pythonPath -ArgumentList "simulators/vehicle_simulator.py" -WindowStyle Hidden }
```

### Option 3: Simple loop (runs sequentially, not in background)
```powershell
for ($i=1; $i -le 11; $i++) { python simulators/vehicle_simulator.py }
```

## Managing Background Jobs

### View running jobs
```powershell
Get-Job
```

### View output from a job
```powershell
Receive-Job -Id <JobId>
```

### Stop all simulator jobs
```powershell
Get-Job | Stop-Job
Get-Job | Remove-Job
```

### Stop specific job
```powershell
Stop-Job -Id <JobId>
Remove-Job -Id <JobId>
```

## Other Common Commands

### Initialize ClickHouse (Windows)
```powershell
python init_clickhouse.py
```

### Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### If you get execution policy error:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

