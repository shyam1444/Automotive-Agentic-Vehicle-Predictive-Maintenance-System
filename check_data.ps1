# Diagnostic script to check ClickHouse consumer and data
# Usage: .\check_data.ps1

Write-Host "🔍 Checking Automotive Predictive Maintenance System Data..." -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if ClickHouse consumer is running
Write-Host "1️⃣ Checking ClickHouse Ingest Consumer..." -ForegroundColor Yellow
$clickhouseProcess = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*clickhouse_ingest*" -or 
    (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*clickhouse_ingest*"
}

if ($clickhouseProcess) {
    Write-Host "   ✅ ClickHouse consumer is running (PID: $($clickhouseProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "   ❌ ClickHouse consumer is NOT running!" -ForegroundColor Red
    Write-Host "   💡 Start it with: python consumers/clickhouse_ingest.py" -ForegroundColor Yellow
}

Write-Host ""

# Check if Docker services are running
Write-Host "2️⃣ Checking Docker Services..." -ForegroundColor Yellow
try {
    $dockerServices = docker ps --format "{{.Names}}" 2>$null
    if ($dockerServices -match "clickhouse") {
        Write-Host "   ✅ ClickHouse Docker container is running" -ForegroundColor Green
    } else {
        Write-Host "   ❌ ClickHouse Docker container is NOT running!" -ForegroundColor Red
        Write-Host "   💡 Start it with: cd docker; docker-compose up -d" -ForegroundColor Yellow
    }
    
    if ($dockerServices -match "kafka") {
        Write-Host "   ✅ Kafka Docker container is running" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Kafka Docker container is NOT running!" -ForegroundColor Red
    }
} catch {
    Write-Host "   ⚠️  Could not check Docker services (Docker might not be running)" -ForegroundColor Yellow
}

Write-Host ""

# Check ClickHouse data
Write-Host "3️⃣ Checking ClickHouse Data..." -ForegroundColor Yellow
try {
    # Check total records
    $totalQuery = 'SELECT count() FROM telemetry_db.telemetry'
    $totalResult = docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q $totalQuery 2>$null
    
    if ($totalResult) {
        Write-Host "   ✅ Total telemetry records: $totalResult" -ForegroundColor Green
        
        # Check recent records (last 24 hours)
        $recentQuery = 'SELECT count() FROM telemetry_db.telemetry WHERE timestamp >= now() - INTERVAL 24 HOUR'
        $recentResult = docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q $recentQuery 2>$null
        
        if ($recentResult) {
            Write-Host "   ✅ Recent records (last 24h): $recentResult" -ForegroundColor Green
        } else {
            Write-Host "   ⚠️  No recent records in last 24 hours" -ForegroundColor Yellow
        }
        
        # Check unique vehicles
        $vehiclesQuery = 'SELECT uniq(vehicle_id) FROM telemetry_db.telemetry WHERE timestamp >= now() - INTERVAL 24 HOUR'
        $vehiclesResult = docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q $vehiclesQuery 2>$null
        
        if ($vehiclesResult) {
            Write-Host "   ✅ Unique vehicles (last 24h): $vehiclesResult" -ForegroundColor Green
        }
        
        # Check latest timestamp
        $latestQuery = 'SELECT max(timestamp) FROM telemetry_db.telemetry'
        $latestResult = docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q $latestQuery 2>$null
        
        if ($latestResult) {
            Write-Host "   ✅ Latest record timestamp: $latestResult" -ForegroundColor Green
        }
    } else {
        Write-Host "   ❌ Could not query ClickHouse (might be empty or connection issue)" -ForegroundColor Red
    }
} catch {
    Write-Host "   ⚠️  Could not check ClickHouse data: $_" -ForegroundColor Yellow
}

Write-Host ""

# Check API endpoint
Write-Host "4️⃣ Checking API Endpoint..." -ForegroundColor Yellow
try {
    $apiResponse = Invoke-RestMethod -Uri "http://localhost:8000/fleet/stats" -Method Get -ErrorAction SilentlyContinue
    if ($apiResponse) {
        Write-Host "   ✅ API is responding" -ForegroundColor Green
        Write-Host "   📊 Total vehicles: $($apiResponse.total_vehicles)" -ForegroundColor Cyan
        Write-Host "   📊 Healthy: $($apiResponse.healthy)" -ForegroundColor Green
        Write-Host "   📊 Warning: $($apiResponse.warning)" -ForegroundColor Yellow
        Write-Host "   📊 Critical: $($apiResponse.critical)" -ForegroundColor Red
    } else {
        Write-Host "   ❌ API is not responding" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ API is not responding: $_" -ForegroundColor Red
    Write-Host "   💡 Make sure API server is running: python -m uvicorn api.main:socket_app --host 0.0.0.0 --port 8000" -ForegroundColor Yellow
}

Write-Host ""

# Check vehicle simulators
Write-Host "5️⃣ Checking Vehicle Simulators..." -ForegroundColor Yellow
$simulatorProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*vehicle_simulator*" -or 
    (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*vehicle_simulator*"
}

if ($simulatorProcesses) {
    $simCount = ($simulatorProcesses | Measure-Object).Count
    Write-Host "   ✅ Found $simCount vehicle simulator process(es)" -ForegroundColor Green
} else {
    Write-Host "   ❌ No vehicle simulators running!" -ForegroundColor Red
    Write-Host "   💡 Start them with: .\start_simulators.ps1" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Diagnostic complete!" -ForegroundColor Green
Write-Host ""

