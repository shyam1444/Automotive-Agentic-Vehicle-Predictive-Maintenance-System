"""
FastAPI Predictive Service - Phase 3
=====================================
REST API for querying ML predictions and alerts

Endpoints:
- GET /health
- GET /predict/{vehicle_id} - Latest prediction for vehicle
- GET /predict/{vehicle_id}/history - Historical predictions
- POST /predict - Real-time prediction from telemetry
- GET /alerts - Recent alerts
- GET /alerts/{vehicle_id} - Alerts for specific vehicle
- POST /alerts/{alert_id}/acknowledge - Mark alert as acknowledged
- GET /vehicle/{vehicle_id}/status - Vehicle health status
- GET /stats/predictions - Prediction statistics
- GET /stats/alerts - Alert statistics
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from clickhouse_driver import Client
from loguru import logger
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# ClickHouse
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '9000'))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_pass')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'telemetry_db')

# ML Model
MODEL_PATH = os.getenv('MODEL_PATH', 'models/vehicle_failure_model.pkl')

# API Settings
API_TITLE = "Vehicle Predictive Maintenance API"
API_VERSION = "3.0.0"
API_DESCRIPTION = """
🚗 Real-time predictive maintenance API with ML-powered failure prediction.

## Features
- 🎯 ML-based failure prediction
- 🚨 Real-time alert monitoring
- 📊 Historical analysis
- ⚡ Real-time inference
"""

# ============================================================================
# DATA MODELS
# ============================================================================

class HealthStatus(str, Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    CRITICAL = "Critical"

class AlertSeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

# Request Models
class TelemetryInput(BaseModel):
    """Real-time telemetry for prediction"""
    vehicle_id: str
    engine_rpm: float
    engine_temp: float
    vibration: float
    speed: float
    fuel_level: float
    battery_voltage: float
    rolling_avg_rpm: Optional[float] = None
    rolling_avg_temp: Optional[float] = None
    rolling_avg_vibration: Optional[float] = None
    rolling_avg_speed: Optional[float] = None

class AcknowledgeRequest(BaseModel):
    """Acknowledge alert request"""
    acknowledged_by: str = Field(..., description="User who acknowledged the alert")

# Response Models
class PredictionResponse(BaseModel):
    """Prediction result"""
    vehicle_id: str
    timestamp: datetime
    failure_probability: float
    health_status: HealthStatus
    reason: str
    model_version: str
    predicted_at: datetime
    metrics: Dict[str, float]

class AlertResponse(BaseModel):
    """Alert record"""
    alert_id: str
    vehicle_id: str
    timestamp: datetime
    failure_probability: float
    health_status: HealthStatus
    reason: str
    severity: AlertSeverity
    acknowledged: bool
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    created_at: datetime

class VehicleStatusResponse(BaseModel):
    """Current vehicle health status"""
    vehicle_id: str
    current_status: HealthStatus
    latest_prediction: Optional[PredictionResponse]
    recent_alerts: List[AlertResponse]
    metrics_summary: Dict[str, Any]

class PredictionStatsResponse(BaseModel):
    """Prediction statistics"""
    total_predictions: int
    healthy_count: int
    warning_count: int
    critical_count: int
    avg_failure_probability: float
    recent_predictions: List[PredictionResponse]

class AlertStatsResponse(BaseModel):
    """Alert statistics"""
    total_alerts: int
    warning_count: int
    critical_count: int
    acknowledged_count: int
    unacknowledged_count: int
    recent_alerts: List[AlertResponse]

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# GLOBAL STATE
# ============================================================================

clickhouse_client: Optional[Client] = None
ml_model = None
model_metadata = {}

# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize connections on startup"""
    global clickhouse_client, ml_model, model_metadata
    
    logger.info("🚀 Starting Predictive API Service...")
    
    # Connect to ClickHouse
    try:
        clickhouse_client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            database=CLICKHOUSE_DATABASE,
            settings={'use_numpy': False}
        )
        clickhouse_client.execute('SELECT 1')
        logger.info(f"✅ Connected to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    except Exception as e:
        logger.error(f"❌ Failed to connect to ClickHouse: {e}")
        raise
    
    # Load ML model
    try:
        if not os.path.exists(MODEL_PATH):
            logger.warning(f"⚠️ Model not found: {MODEL_PATH}")
        else:
            model_data = joblib.load(MODEL_PATH)
            ml_model = model_data['model']
            model_metadata = {
                'version': model_data.get('version', '1.0.0'),
                'trained_at': model_data.get('trained_at', 'unknown'),
                'model_type': model_data.get('model_type', 'unknown')
            }
            logger.info(f"✅ ML model loaded - v{model_metadata['version']}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load model: {e}")
    
    logger.info(f"✅ Predictive API started on http://0.0.0.0:8001")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    if clickhouse_client:
        clickhouse_client.disconnect()
    logger.info("🛑 Predictive API shut down")

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Predictive API",
        "version": API_VERSION,
        "model_loaded": ml_model is not None,
        "model_version": model_metadata.get('version', 'N/A'),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/predict/{vehicle_id}", response_model=PredictionResponse)
async def get_latest_prediction(vehicle_id: str):
    """Get latest prediction for a vehicle"""
    try:
        query = """
        SELECT 
            vehicle_id, timestamp, failure_probability, health_status,
            engine_temp, vibration, engine_rpm, speed, fuel_level,
            battery_voltage, reason, model_version, predicted_at
        FROM vehicle_predictions
        WHERE vehicle_id = %(vehicle_id)s
        ORDER BY timestamp DESC
        LIMIT 1
        """
        
        result = clickhouse_client.execute(query, {'vehicle_id': vehicle_id})
        
        if not result:
            raise HTTPException(status_code=404, detail=f"No predictions found for vehicle {vehicle_id}")
        
        row = result[0]
        return PredictionResponse(
            vehicle_id=row[0],
            timestamp=row[1],
            failure_probability=row[2],
            health_status=row[3],
            reason=row[10],
            model_version=row[11],
            predicted_at=row[12],
            metrics={
                'engine_temp': row[4],
                'vibration': row[5],
                'engine_rpm': row[6],
                'speed': row[7],
                'fuel_level': row[8],
                'battery_voltage': row[9]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/predict/{vehicle_id}/history", response_model=List[PredictionResponse])
async def get_prediction_history(
    vehicle_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)")
):
    """Get prediction history for a vehicle"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        query = """
        SELECT 
            vehicle_id, timestamp, failure_probability, health_status,
            engine_temp, vibration, engine_rpm, speed, fuel_level,
            battery_voltage, reason, model_version, predicted_at
        FROM vehicle_predictions
        WHERE vehicle_id = %(vehicle_id)s
          AND timestamp >= %(since)s
        ORDER BY timestamp DESC
        LIMIT 1000
        """
        
        results = clickhouse_client.execute(query, {
            'vehicle_id': vehicle_id,
            'since': since
        })
        
        return [
            PredictionResponse(
                vehicle_id=row[0],
                timestamp=row[1],
                failure_probability=row[2],
                health_status=row[3],
                reason=row[10],
                model_version=row[11],
                predicted_at=row[12],
                metrics={
                    'engine_temp': row[4],
                    'vibration': row[5],
                    'engine_rpm': row[6],
                    'speed': row[7],
                    'fuel_level': row[8],
                    'battery_voltage': row[9]
                }
            )
            for row in results
        ]
    
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/predict", response_model=PredictionResponse)
async def predict_real_time(telemetry: TelemetryInput):
    """Run real-time prediction on telemetry data"""
    if ml_model is None:
        raise HTTPException(status_code=503, detail="ML model not loaded")
    
    try:
        # Prepare features (use input values as rolling averages if not provided)
        features = [
            telemetry.engine_rpm,
            telemetry.engine_temp,
            telemetry.vibration,
            telemetry.speed,
            telemetry.fuel_level,
            telemetry.battery_voltage,
            telemetry.rolling_avg_rpm or telemetry.engine_rpm,
            telemetry.rolling_avg_temp or telemetry.engine_temp,
            telemetry.rolling_avg_vibration or telemetry.vibration,
            telemetry.rolling_avg_speed or telemetry.speed
        ]
        
        X = np.array([features])
        
        # Run prediction
        probability = float(ml_model.predict_proba(X)[0, 1])
        
        # Determine health status
        if probability >= 0.8:
            health_status = HealthStatus.CRITICAL
            reason = generate_failure_reason(telemetry, "critical")
        elif probability >= 0.5:
            health_status = HealthStatus.WARNING
            reason = generate_failure_reason(telemetry, "warning")
        else:
            health_status = HealthStatus.HEALTHY
            reason = "All systems normal"
        
        return PredictionResponse(
            vehicle_id=telemetry.vehicle_id,
            timestamp=datetime.now(),
            failure_probability=probability,
            health_status=health_status,
            reason=reason,
            model_version=model_metadata.get('version', '1.0.0'),
            predicted_at=datetime.now(),
            metrics={
                'engine_temp': telemetry.engine_temp,
                'vibration': telemetry.vibration,
                'engine_rpm': telemetry.engine_rpm,
                'speed': telemetry.speed,
                'fuel_level': telemetry.fuel_level,
                'battery_voltage': telemetry.battery_voltage
            }
        )
    
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts", response_model=List[AlertResponse])
async def get_recent_alerts(
    limit: int = Query(100, ge=1, le=1000, description="Max number of alerts"),
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None
):
    """Get recent alerts"""
    try:
        conditions = []
        params = {}
        
        if severity:
            conditions.append("severity = %(severity)s")
            params['severity'] = severity.value
        
        if acknowledged is not None:
            conditions.append("acknowledged = %(acknowledged)s")
            params['acknowledged'] = acknowledged
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = f"""
        SELECT 
            alert_id, vehicle_id, timestamp, failure_probability,
            health_status, reason, severity, acknowledged,
            acknowledged_by, acknowledged_at, created_at
        FROM vehicle_alerts
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT %(limit)s
        """
        
        params['limit'] = limit
        results = clickhouse_client.execute(query, params)
        
        return [
            AlertResponse(
                alert_id=row[0],
                vehicle_id=row[1],
                timestamp=row[2],
                failure_probability=row[3],
                health_status=row[4],
                reason=row[5],
                severity=row[6],
                acknowledged=row[7],
                acknowledged_by=row[8],
                acknowledged_at=row[9],
                created_at=row[10]
            )
            for row in results
        ]
    
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/{vehicle_id}", response_model=List[AlertResponse])
async def get_vehicle_alerts(
    vehicle_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history")
):
    """Get alerts for a specific vehicle"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        query = """
        SELECT 
            alert_id, vehicle_id, timestamp, failure_probability,
            health_status, reason, severity, acknowledged,
            acknowledged_by, acknowledged_at, created_at
        FROM vehicle_alerts
        WHERE vehicle_id = %(vehicle_id)s
          AND timestamp >= %(since)s
        ORDER BY created_at DESC
        """
        
        results = clickhouse_client.execute(query, {
            'vehicle_id': vehicle_id,
            'since': since
        })
        
        return [
            AlertResponse(
                alert_id=row[0],
                vehicle_id=row[1],
                timestamp=row[2],
                failure_probability=row[3],
                health_status=row[4],
                reason=row[5],
                severity=row[6],
                acknowledged=row[7],
                acknowledged_by=row[8],
                acknowledged_at=row[9],
                created_at=row[10]
            )
            for row in results
        ]
    
    except Exception as e:
        logger.error(f"Error fetching vehicle alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: AcknowledgeRequest):
    """Mark an alert as acknowledged"""
    try:
        # Note: ClickHouse doesn't support UPDATE well, so we'd typically
        # insert an acknowledgment record or use a specialized approach
        # For simplicity, we'll use ALTER UPDATE (not recommended for production)
        
        query = """
        ALTER TABLE vehicle_alerts
        UPDATE 
            acknowledged = true,
            acknowledged_by = %(acknowledged_by)s,
            acknowledged_at = %(acknowledged_at)s
        WHERE alert_id = %(alert_id)s
        """
        
        clickhouse_client.execute(query, {
            'alert_id': alert_id,
            'acknowledged_by': request.acknowledged_by,
            'acknowledged_at': datetime.now()
        })
        
        return {"status": "success", "message": f"Alert {alert_id} acknowledged"}
    
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/vehicle/{vehicle_id}/status", response_model=VehicleStatusResponse)
async def get_vehicle_status(vehicle_id: str):
    """Get comprehensive vehicle health status"""
    try:
        # Get latest prediction
        pred_query = """
        SELECT 
            vehicle_id, timestamp, failure_probability, health_status,
            engine_temp, vibration, engine_rpm, speed, fuel_level,
            battery_voltage, reason, model_version, predicted_at
        FROM vehicle_predictions
        WHERE vehicle_id = %(vehicle_id)s
        ORDER BY timestamp DESC
        LIMIT 1
        """
        
        pred_result = clickhouse_client.execute(pred_query, {'vehicle_id': vehicle_id})
        
        latest_prediction = None
        current_status = HealthStatus.HEALTHY
        
        if pred_result:
            row = pred_result[0]
            current_status = row[3]
            latest_prediction = PredictionResponse(
                vehicle_id=row[0],
                timestamp=row[1],
                failure_probability=row[2],
                health_status=row[3],
                reason=row[10],
                model_version=row[11],
                predicted_at=row[12],
                metrics={
                    'engine_temp': row[4],
                    'vibration': row[5],
                    'engine_rpm': row[6],
                    'speed': row[7],
                    'fuel_level': row[8],
                    'battery_voltage': row[9]
                }
            )
        
        # Get recent alerts (last 24 hours)
        alert_query = """
        SELECT 
            alert_id, vehicle_id, timestamp, failure_probability,
            health_status, reason, severity, acknowledged,
            acknowledged_by, acknowledged_at, created_at
        FROM vehicle_alerts
        WHERE vehicle_id = %(vehicle_id)s
          AND timestamp >= %(since)s
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        since = datetime.now() - timedelta(hours=24)
        alert_results = clickhouse_client.execute(alert_query, {
            'vehicle_id': vehicle_id,
            'since': since
        })
        
        recent_alerts = [
            AlertResponse(
                alert_id=row[0],
                vehicle_id=row[1],
                timestamp=row[2],
                failure_probability=row[3],
                health_status=row[4],
                reason=row[5],
                severity=row[6],
                acknowledged=row[7],
                acknowledged_by=row[8],
                acknowledged_at=row[9],
                created_at=row[10]
            )
            for row in alert_results
        ]
        
        # Get metrics summary
        metrics_query = """
        SELECT 
            avg(failure_probability) as avg_prob,
            max(failure_probability) as max_prob,
            count() as prediction_count
        FROM vehicle_predictions
        WHERE vehicle_id = %(vehicle_id)s
          AND timestamp >= %(since)s
        """
        
        metrics_result = clickhouse_client.execute(metrics_query, {
            'vehicle_id': vehicle_id,
            'since': since
        })
        
        metrics_summary = {}
        if metrics_result and metrics_result[0][0] is not None:
            metrics_summary = {
                'avg_failure_probability': float(metrics_result[0][0]),
                'max_failure_probability': float(metrics_result[0][1]),
                'prediction_count': int(metrics_result[0][2]),
                'alert_count': len(recent_alerts),
                'unacknowledged_alerts': sum(1 for a in recent_alerts if not a.acknowledged)
            }
        
        return VehicleStatusResponse(
            vehicle_id=vehicle_id,
            current_status=current_status,
            latest_prediction=latest_prediction,
            recent_alerts=recent_alerts,
            metrics_summary=metrics_summary
        )
    
    except Exception as e:
        logger.error(f"Error fetching vehicle status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/predictions", response_model=PredictionStatsResponse)
async def get_prediction_stats(
    hours: int = Query(24, ge=1, le=168, description="Hours of history")
):
    """Get prediction statistics"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        # Get aggregate stats
        stats_query = """
        SELECT 
            count() as total,
            countIf(health_status = 'Healthy') as healthy,
            countIf(health_status = 'Warning') as warning,
            countIf(health_status = 'Critical') as critical,
            avg(failure_probability) as avg_prob
        FROM vehicle_predictions
        WHERE timestamp >= %(since)s
        """
        
        stats_result = clickhouse_client.execute(stats_query, {'since': since})
        
        # Get recent predictions
        recent_query = """
        SELECT 
            vehicle_id, timestamp, failure_probability, health_status,
            engine_temp, vibration, engine_rpm, speed, fuel_level,
            battery_voltage, reason, model_version, predicted_at
        FROM vehicle_predictions
        WHERE timestamp >= %(since)s
        ORDER BY timestamp DESC
        LIMIT 10
        """
        
        recent_results = clickhouse_client.execute(recent_query, {'since': since})
        
        recent_predictions = [
            PredictionResponse(
                vehicle_id=row[0],
                timestamp=row[1],
                failure_probability=row[2],
                health_status=row[3],
                reason=row[10],
                model_version=row[11],
                predicted_at=row[12],
                metrics={
                    'engine_temp': row[4],
                    'vibration': row[5],
                    'engine_rpm': row[6],
                    'speed': row[7],
                    'fuel_level': row[8],
                    'battery_voltage': row[9]
                }
            )
            for row in recent_results
        ]
        
        stats = stats_result[0]
        
        return PredictionStatsResponse(
            total_predictions=stats[0],
            healthy_count=stats[1],
            warning_count=stats[2],
            critical_count=stats[3],
            avg_failure_probability=float(stats[4]) if stats[4] else 0.0,
            recent_predictions=recent_predictions
        )
    
    except Exception as e:
        logger.error(f"Error fetching prediction stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats/alerts", response_model=AlertStatsResponse)
async def get_alert_stats(
    hours: int = Query(24, ge=1, le=168, description="Hours of history")
):
    """Get alert statistics"""
    try:
        since = datetime.now() - timedelta(hours=hours)
        
        # Get aggregate stats
        stats_query = """
        SELECT 
            count() as total,
            countIf(severity = 'WARNING') as warning,
            countIf(severity = 'CRITICAL') as critical,
            countIf(acknowledged = true) as acknowledged,
            countIf(acknowledged = false) as unacknowledged
        FROM vehicle_alerts
        WHERE timestamp >= %(since)s
        """
        
        stats_result = clickhouse_client.execute(stats_query, {'since': since})
        
        # Get recent alerts
        recent_query = """
        SELECT 
            alert_id, vehicle_id, timestamp, failure_probability,
            health_status, reason, severity, acknowledged,
            acknowledged_by, acknowledged_at, created_at
        FROM vehicle_alerts
        WHERE timestamp >= %(since)s
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        recent_results = clickhouse_client.execute(recent_query, {'since': since})
        
        recent_alerts = [
            AlertResponse(
                alert_id=row[0],
                vehicle_id=row[1],
                timestamp=row[2],
                failure_probability=row[3],
                health_status=row[4],
                reason=row[5],
                severity=row[6],
                acknowledged=row[7],
                acknowledged_by=row[8],
                acknowledged_at=row[9],
                created_at=row[10]
            )
            for row in recent_results
        ]
        
        stats = stats_result[0]
        
        return AlertStatsResponse(
            total_alerts=stats[0],
            warning_count=stats[1],
            critical_count=stats[2],
            acknowledged_count=stats[3],
            unacknowledged_count=stats[4],
            recent_alerts=recent_alerts
        )
    
    except Exception as e:
        logger.error(f"Error fetching alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_failure_reason(telemetry: TelemetryInput, severity: str) -> str:
    """Generate human-readable failure reason"""
    reasons = []
    
    if telemetry.engine_temp > 100:
        reasons.append(f"High engine temp ({telemetry.engine_temp:.1f}°C)")
    if telemetry.vibration > 3.0:
        reasons.append(f"Excessive vibration ({telemetry.vibration:.1f})")
    if telemetry.engine_rpm > 5000:
        reasons.append(f"High RPM ({telemetry.engine_rpm})")
    if telemetry.engine_rpm < 500 and telemetry.speed > 10:
        reasons.append(f"Engine stalling (RPM: {telemetry.engine_rpm})")
    if telemetry.battery_voltage < 11.0:
        reasons.append(f"Low battery ({telemetry.battery_voltage:.1f}V)")
    if telemetry.fuel_level < 10:
        reasons.append(f"Low fuel ({telemetry.fuel_level:.1f}%)")
    
    if not reasons:
        if severity == "critical":
            reasons.append("Multiple sensor anomalies detected")
        else:
            reasons.append("Elevated sensor readings")
    
    return " | ".join(reasons)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fastapi_predictive_service:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
