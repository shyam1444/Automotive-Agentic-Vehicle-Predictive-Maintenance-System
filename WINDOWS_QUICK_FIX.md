# Windows Quick Fix Guide

## PowerShell Commands (Instead of Bash)

### ⚠️ IMPORTANT: PowerShell uses different syntax than Bash!

### Start Multiple Simulators

**❌ WRONG (Bash syntax - doesn't work in PowerShell):**
```powershell
for i in {1..11}; do python simulators/vehicle_simulator.py & done
```

**✅ CORRECT (PowerShell syntax):**

**Option 1: Use the script (EASIEST)**
```powershell
.\start_simulators.ps1
```

**Option 2: Direct PowerShell command**
```powershell
1..11 | ForEach-Object { Start-Job -ScriptBlock { Set-Location $using:PWD; python simulators/vehicle_simulator.py } }
```

**Option 3: PowerShell for loop**
```powershell
for ($i=1; $i -le 11; $i++) { Start-Job -ScriptBlock { python simulators/vehicle_simulator.py } }
```

**Option 4: Simple one-liner (if script doesn't work)**
```powershell
$currentDir = Get-Location; 1..11 | ForEach-Object { Start-Job -ScriptBlock { Set-Location $using:currentDir; python simulators/vehicle_simulator.py } }
```

### Stop Simulators
```powershell
.\stop_simulators.ps1
```

### Check Running Jobs
```powershell
Get-Job
```

### View Job Output
```powershell
Receive-Job -Id <JobId>
```

## Python Commands

### Use `python` not `python3` on Windows
```powershell
# ✅ Correct
python init_clickhouse.py
python consumers/clickhouse_ingest.py

# ❌ Wrong
python3 init_clickhouse.py
```

## Common Issues Fixed

1. ✅ Signal handling - Fixed for Windows compatibility
2. ✅ Datetime errors - Fixed `tzinfo` attribute error
3. ✅ PowerShell syntax - Created helper scripts

