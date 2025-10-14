"""
FastAPI Telemetry Service - Phase 2
Automotive Predictive Maintenance System

REST API service for querying vehicle telemetry data from ClickHouse.
Provides endpoints for dashboards, ML consumers, and real-time monitoring.

Features:
- Latest telemetry by vehicle
- Time-range queries with filtering
- Anomaly retrieval
- Fleet-wide statistics
- Vehicle health scores
- Async query execution for high performance
"""

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from clickhouse_driver import Client
from loguru import logger
import os
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ============================================================================
# DATA MODELS
# ============================================================================

class TelemetryResponse(BaseModel):
    """Single telemetry record response"""
    vehicle_id: str
    timestamp: datetime
    engine_rpm: int
    engine_temp: float
    vibration: float
    speed: float
    gps_lat: float
    gps_lon: float
    fuel_level: float
    battery_voltage: float
    rolling_avg_rpm: Optional[float] = None
    rolling_avg_temp: Optional[float] = None
    rolling_avg_vibration: Optional[float] = None
    rolling_avg_speed: Optional[float] = None
    engine_health_score: Optional[float] = None
    battery_health_status: Optional[str] = None
    fuel_status: Optional[str] = None
    received_at: Optional[datetime] = None

class AnomalyResponse(BaseModel):
    """Anomaly record response"""
    vehicle_id: str
    timestamp: datetime
    anomaly_type: str
    severity: str
    metric_name: str
    metric_value: float
    threshold: float
    message: str
    detected_at: datetime

class VehicleStatsResponse(BaseModel):
    """Vehicle statistics response"""
    vehicle_id: str
    total_messages: int
    avg_rpm: float
    avg_temp: float
    avg_vibration: float
    avg_speed: float
    avg_fuel: float
    avg_battery: float
    max_temp: float
    max_vibration: float
    min_battery: float
    min_fuel: float
    anomaly_count: int
    first_seen: datetime
    last_seen: datetime

class FleetStatsResponse(BaseModel):
    """Fleet-wide statistics"""
    total_vehicles: int
    active_vehicles_24h: int
    total_messages: int
    fleet_avg_temp: float
    fleet_avg_battery: float
    fleet_avg_fuel: float
    vehicles_low_battery: int
    vehicles_low_fuel: int
    vehicles_high_temp: int
    critical_anomalies: int
    warning_anomalies: int

class HealthCheckResponse(BaseModel):
    """API health check response"""
    status: str
    clickhouse_connected: bool
    database: str
    timestamp: datetime

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Automotive Telemetry API",
    description="REST API for vehicle predictive maintenance telemetry data",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ClickHouse client (initialized on startup)
clickhouse_client: Optional[Client] = None

# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize ClickHouse connection on startup"""
    global clickhouse_client
    try:
        clickhouse_client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
            settings={'use_numpy': False}
        )
        # Test connection
        clickhouse_client.execute('SELECT 1')
        logger.info(f"✅ FastAPI connected to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to ClickHouse: {e}")
        clickhouse_client = None

@app.on_event("shutdown")
async def shutdown_event():
    """Close ClickHouse connection on shutdown"""
    global clickhouse_client
    if clickhouse_client:
        clickhouse_client.disconnect()
        logger.info("✅ ClickHouse connection closed")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def execute_query(query: str, params: Optional[Dict] = None) -> List[Dict]:
    """Execute ClickHouse query and return results as list of dicts"""
    if not clickhouse_client:
        raise HTTPException(status_code=503, detail="ClickHouse connection not available")
    
    try:
        result = clickhouse_client.execute(query, params, with_column_types=True)
        rows, columns = result[0], [col[0] for col in result[1]]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=f"Query execution failed: {str(e)}")

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint"""
    return HealthCheckResponse(
        status="healthy" if clickhouse_client else "degraded",
        clickhouse_connected=clickhouse_client is not None,
        database=CLICKHOUSE_DATABASE,
        timestamp=datetime.now()
    )

@app.get("/telemetry/latest/{vehicle_id}", response_model=TelemetryResponse)
async def get_latest_telemetry(
    vehicle_id: str = Path(..., description="Vehicle ID")
):
    """
    Get the latest telemetry record for a specific vehicle
    """
    query = """
    SELECT 
        vehicle_id,
        timestamp,
        engine_rpm,
        engine_temp,
        vibration,
        speed,
        gps_lat,
        gps_lon,
        fuel_level,
        battery_voltage,
        rolling_avg_rpm,
        rolling_avg_temp,
        rolling_avg_vibration,
        rolling_avg_speed,
        engine_health_score,
        battery_health_status,
        fuel_status,
        received_at
    FROM telemetry
    WHERE vehicle_id = %(vehicle_id)s
    ORDER BY timestamp DESC
    LIMIT 1
    """
    
    result = execute_query(query, {'vehicle_id': vehicle_id})
    
    if not result:
        raise HTTPException(status_code=404, detail=f"No telemetry found for vehicle {vehicle_id}")
    
    return TelemetryResponse(**result[0])

@app.get("/telemetry/range/{vehicle_id}", response_model=List[TelemetryResponse])
async def get_telemetry_range(
    vehicle_id: str = Path(..., description="Vehicle ID"),
    start: Optional[datetime] = Query(None, description="Start timestamp (ISO format)"),
    end: Optional[datetime] = Query(None, description="End timestamp (ISO format)"),
    limit: int = Query(1000, ge=1, le=10000, description="Maximum records to return")
):
    """
    Get telemetry records for a vehicle within a time range
    """
    # Default to last 24 hours if no range specified
    if not start:
        start = datetime.now() - timedelta(hours=24)
    if not end:
        end = datetime.now()
    
    query = """
    SELECT 
        vehicle_id,
        timestamp,
        engine_rpm,
        engine_temp,
        vibration,
        speed,
        gps_lat,
        gps_lon,
        fuel_level,
        battery_voltage,
        rolling_avg_rpm,
        rolling_avg_temp,
        rolling_avg_vibration,
        rolling_avg_speed,
        engine_health_score,
        battery_health_status,
        fuel_status,
        received_at
    FROM telemetry
    WHERE vehicle_id = %(vehicle_id)s
      AND timestamp BETWEEN %(start)s AND %(end)s
    ORDER BY timestamp DESC
    LIMIT %(limit)s
    """
    
    result = execute_query(query, {
        'vehicle_id': vehicle_id,
        'start': start,
        'end': end,
        'limit': limit
    })
    
    return [TelemetryResponse(**row) for row in result]

@app.get("/telemetry/anomalies/{vehicle_id}", response_model=List[AnomalyResponse])
async def get_vehicle_anomalies(
    vehicle_id: str = Path(..., description="Vehicle ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, WARNING, INFO")
):
    """
    Get anomalies detected for a specific vehicle in the last N hours
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    query = """
    SELECT 
        vehicle_id,
        timestamp,
        anomaly_type,
        severity,
        metric_name,
        metric_value,
        threshold,
        message,
        detected_at
    FROM anomalies
    WHERE vehicle_id = %(vehicle_id)s
      AND timestamp >= %(start_time)s
    """
    
    params = {
        'vehicle_id': vehicle_id,
        'start_time': start_time
    }
    
    if severity:
        query += " AND severity = %(severity)s"
        params['severity'] = severity
    
    query += " ORDER BY timestamp DESC LIMIT 1000"
    
    result = execute_query(query, params)
    
    return [AnomalyResponse(**row) for row in result]

@app.get("/fleet/anomalies", response_model=List[AnomalyResponse])
async def get_fleet_anomalies(
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, WARNING, INFO"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return")
):
    """
    Get recent anomalies across the entire fleet
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    query = """
    SELECT 
        vehicle_id,
        timestamp,
        anomaly_type,
        severity,
        metric_name,
        metric_value,
        threshold,
        message,
        detected_at
    FROM anomalies
    WHERE timestamp >= %(start_time)s
    """
    
    params = {'start_time': start_time}
    
    if severity:
        query += " AND severity = %(severity)s"
        params['severity'] = severity
    
    query += " ORDER BY detected_at DESC LIMIT %(limit)s"
    params['limit'] = limit
    
    result = execute_query(query, params)
    
    return [AnomalyResponse(**row) for row in result]

@app.get("/vehicle/{vehicle_id}/stats", response_model=VehicleStatsResponse)
async def get_vehicle_stats(
    vehicle_id: str = Path(..., description="Vehicle ID"),
    hours: int = Query(24, ge=1, le=720, description="Hours to aggregate over")
):
    """
    Get aggregated statistics for a specific vehicle
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    query = """
    SELECT 
        vehicle_id,
        count() AS total_messages,
        avg(engine_rpm) AS avg_rpm,
        avg(engine_temp) AS avg_temp,
        avg(vibration) AS avg_vibration,
        avg(speed) AS avg_speed,
        avg(fuel_level) AS avg_fuel,
        avg(battery_voltage) AS avg_battery,
        max(engine_temp) AS max_temp,
        max(vibration) AS max_vibration,
        min(battery_voltage) AS min_battery,
        min(fuel_level) AS min_fuel,
        min(timestamp) AS first_seen,
        max(timestamp) AS last_seen
    FROM telemetry
    WHERE vehicle_id = %(vehicle_id)s
      AND timestamp >= %(start_time)s
    GROUP BY vehicle_id
    """
    
    result = execute_query(query, {
        'vehicle_id': vehicle_id,
        'start_time': start_time
    })
    
    if not result:
        raise HTTPException(status_code=404, detail=f"No data found for vehicle {vehicle_id}")
    
    # Get anomaly count
    anomaly_query = """
    SELECT count() AS anomaly_count
    FROM anomalies
    WHERE vehicle_id = %(vehicle_id)s
      AND timestamp >= %(start_time)s
    """
    
    anomaly_result = execute_query(anomaly_query, {
        'vehicle_id': vehicle_id,
        'start_time': start_time
    })
    
    result[0]['anomaly_count'] = anomaly_result[0]['anomaly_count'] if anomaly_result else 0
    
    return VehicleStatsResponse(**result[0])

@app.get("/fleet/stats", response_model=FleetStatsResponse)
async def get_fleet_stats():
    """
    Get fleet-wide statistics and health overview
    """
    # Get basic fleet stats
    query = """
    SELECT 
        uniq(vehicle_id) AS total_vehicles,
        count() AS total_messages,
        avg(engine_temp) AS fleet_avg_temp,
        avg(battery_voltage) AS fleet_avg_battery,
        avg(fuel_level) AS fleet_avg_fuel,
        countIf(battery_voltage < 11.5) AS vehicles_low_battery,
        countIf(fuel_level < 15) AS vehicles_low_fuel,
        countIf(engine_temp > 100) AS vehicles_high_temp
    FROM telemetry
    WHERE timestamp >= now() - INTERVAL 24 HOUR
    """
    
    result = execute_query(query)
    
    if not result:
        raise HTTPException(status_code=503, detail="Unable to retrieve fleet statistics")
    
    # Get active vehicles in last 24h
    active_query = """
    SELECT uniq(vehicle_id) AS active_vehicles_24h
    FROM telemetry
    WHERE timestamp >= now() - INTERVAL 24 HOUR
    """
    
    active_result = execute_query(active_query)
    
    # Get anomaly counts by severity
    anomaly_query = """
    SELECT 
        countIf(severity = 'CRITICAL') AS critical_anomalies,
        countIf(severity = 'WARNING') AS warning_anomalies
    FROM anomalies
    WHERE timestamp >= now() - INTERVAL 24 HOUR
    """
    
    anomaly_result = execute_query(anomaly_query)
    
    fleet_data = {
        **result[0],
        'active_vehicles_24h': active_result[0]['active_vehicles_24h'] if active_result else 0,
        'critical_anomalies': anomaly_result[0]['critical_anomalies'] if anomaly_result else 0,
        'warning_anomalies': anomaly_result[0]['warning_anomalies'] if anomaly_result else 0
    }
    
    return FleetStatsResponse(**fleet_data)

@app.get("/vehicles/list")
async def list_vehicles(
    active_only: bool = Query(True, description="Only show vehicles active in last 24h")
):
    """
    Get list of all vehicles with their last activity
    """
    query = """
    SELECT 
        vehicle_id,
        max(timestamp) AS last_seen,
        count() AS message_count
    FROM telemetry
    """
    
    if active_only:
        query += " WHERE timestamp >= now() - INTERVAL 24 HOUR"
    
    query += " GROUP BY vehicle_id ORDER BY last_seen DESC"
    
    result = execute_query(query)
    
    return {
        "count": len(result),
        "vehicles": result
    }

@app.get("/telemetry/hourly/{vehicle_id}")
async def get_hourly_aggregates(
    vehicle_id: str = Path(..., description="Vehicle ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours to retrieve")
):
    """
    Get hourly aggregated telemetry for dashboard charts
    """
    start_time = datetime.now() - timedelta(hours=hours)
    
    query = """
    SELECT 
        timestamp_hour,
        message_count,
        avg_rpm,
        avg_temp,
        avg_vibration,
        avg_speed,
        avg_fuel,
        avg_battery,
        max_temp,
        max_vibration,
        min_battery,
        min_fuel
    FROM telemetry_hourly
    WHERE vehicle_id = %(vehicle_id)s
      AND timestamp_hour >= %(start_time)s
    ORDER BY timestamp_hour ASC
    """
    
    result = execute_query(query, {
        'vehicle_id': vehicle_id,
        'start_time': start_time
    })
    
    return {
        "vehicle_id": vehicle_id,
        "hours": hours,
        "data": result
    }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Configure logger
    logger.add(
        "logs/fastapi_telemetry_{time}.log",
        rotation="100 MB",
        retention="7 days",
        level="INFO"
    )
    
    logger.info(f"🚀 Starting FastAPI Telemetry Service on {API_HOST}:{API_PORT}")
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info"
    )
