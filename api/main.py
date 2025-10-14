"""
Unified FastAPI Application - Automotive Predictive Maintenance System
Combines all API services: Telemetry, Predictions, Manufacturing, Agents

This is the main entry point for the backend API server.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from loguru import logger
import socketio
import asyncio
from typing import Optional

# Load environment variables
load_dotenv()

# ============================================================================
# SOCKET.IO CONFIGURATION
# ============================================================================

sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# ============================================================================
# CREATE MAIN APP
# ============================================================================

app = FastAPI(
    title="Automotive Predictive Maintenance API",
    description="Unified API for vehicle telemetry, predictions, manufacturing insights, and agent monitoring",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Wrap with Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# ============================================================================
# CORS CONFIGURATION
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API status"""
    return {
        "service": "Automotive Predictive Maintenance API",
        "status": "operational",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "api": "operational",
            "telemetry": "operational",
            "predictions": "operational",
            "manufacturing": "operational",
            "agents": "operational"
        }
    }

# ============================================================================
# IMPORT AND MOUNT SUB-APPLICATIONS
# ============================================================================

try:
    # Import telemetry routes
    from api.fastapi_telemetry_service import app as telemetry_app
    
    # Mount telemetry routes
    @app.get("/fleet/vehicles", tags=["Telemetry"])
    async def get_vehicles():
        """Get all vehicles (proxy to telemetry service)"""
        try:
            from clickhouse_driver import Client
            client = Client(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
                database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
            )
            
            query = """
            SELECT DISTINCT vehicle_id
            FROM telemetry
            ORDER BY vehicle_id
            """
            result = client.execute(query)
            
            vehicles = [{"vehicle_id": row[0]} for row in result]
            return {"vehicles": vehicles, "count": len(vehicles)}
        except Exception as e:
            logger.error(f"Error fetching vehicles: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/fleet/stats", tags=["Telemetry"])
    async def get_fleet_stats():
        """Get fleet statistics"""
        try:
            from clickhouse_driver import Client
            client = Client(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
                database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
            )
            
            # Get total vehicles
            total_query = "SELECT COUNT(DISTINCT vehicle_id) FROM telemetry"
            total_result = client.execute(total_query)
            total_vehicles = total_result[0][0] if total_result else 0
            
            # Get vehicle statuses (simplified logic)
            status_query = """
            WITH latest_data AS (
                SELECT 
                    vehicle_id,
                    engine_temp,
                    vibration,
                    battery_voltage,
                    ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY timestamp DESC) as rn
                FROM telemetry
                WHERE timestamp >= now() - INTERVAL 1 HOUR
            )
            SELECT 
                vehicle_id,
                engine_temp,
                vibration,
                battery_voltage
            FROM latest_data
            WHERE rn = 1
            """
            
            status_result = client.execute(status_query)
            
            healthy = 0
            warning = 0
            critical = 0
            
            for row in status_result:
                vehicle_id, engine_temp, vibration, battery_voltage = row
                
                # Define thresholds
                if engine_temp > 110 or vibration > 8 or battery_voltage < 11:
                    critical += 1
                elif engine_temp > 100 or vibration > 6 or battery_voltage < 11.5:
                    warning += 1
                else:
                    healthy += 1
            
            return {
                "total_vehicles": total_vehicles,
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error fetching fleet stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/vehicle/{vehicle_id}/telemetry", tags=["Telemetry"])
    async def get_vehicle_telemetry(vehicle_id: str, hours: int = 24):
        """Get vehicle telemetry history"""
        try:
            from clickhouse_driver import Client
            client = Client(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
                database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
            )
            
            query = f"""
            SELECT 
                timestamp,
                engine_rpm,
                engine_temp,
                vibration,
                speed,
                fuel_level,
                battery_voltage
            FROM telemetry
            WHERE vehicle_id = %(vehicle_id)s
                AND timestamp >= now() - INTERVAL {hours} HOUR
            ORDER BY timestamp DESC
            LIMIT 1000
            """
            
            result = client.execute(query, {"vehicle_id": vehicle_id})
            
            telemetry = []
            for row in result:
                telemetry.append({
                    "timestamp": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                    "engine_rpm": row[1],
                    "engine_temp": row[2],
                    "vibration": row[3],
                    "speed": row[4],
                    "fuel_level": row[5],
                    "battery_voltage": row[6]
                })
            
            return {
                "vehicle_id": vehicle_id,
                "telemetry": telemetry,
                "count": len(telemetry)
            }
        except Exception as e:
            logger.error(f"Error fetching telemetry: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/vehicle/{vehicle_id}/metrics", tags=["Telemetry"])
    async def get_vehicle_metrics(vehicle_id: str):
        """Get latest vehicle metrics"""
        try:
            from clickhouse_driver import Client
            client = Client(
                host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
                user=os.getenv("CLICKHOUSE_USER", "default"),
                password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
                database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
            )
            
            query = """
            SELECT 
                vehicle_id,
                timestamp,
                engine_rpm,
                engine_temp,
                vibration,
                speed,
                fuel_level,
                battery_voltage,
                gps_lat,
                gps_lon
            FROM telemetry
            WHERE vehicle_id = %(vehicle_id)s
            ORDER BY timestamp DESC
            LIMIT 1
            """
            
            result = client.execute(query, {"vehicle_id": vehicle_id})
            
            if not result:
                return {
                    "vehicle_id": vehicle_id,
                    "engine_rpm": 0,
                    "engine_temp": 0,
                    "vibration": 0,
                    "speed": 0,
                    "fuel_level": 0,
                    "battery_voltage": 0,
                    "last_update": None
                }
            
            row = result[0]
            return {
                "vehicle_id": row[0],
                "engine_rpm": row[2],
                "engine_temp": row[3],
                "vibration": row[4],
                "speed": row[5],
                "fuel_level": row[6],
                "battery_voltage": row[7],
                "gps": {
                    "lat": row[8],
                    "lon": row[9]
                },
                "last_update": row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1])
            }
        except Exception as e:
            logger.error(f"Error fetching metrics for {vehicle_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info("✅ Telemetry routes mounted")

except Exception as e:
    logger.warning(f"⚠️  Could not import telemetry service: {e}")

# ============================================================================
# PLACEHOLDER ROUTES FOR OTHER SERVICES
# ============================================================================

@app.get("/predictions/{vehicle_id}", tags=["Predictions"])
async def get_predictions(vehicle_id: str):
    """Get ML predictions for a vehicle"""
    return {
        "vehicle_id": vehicle_id,
        "prediction": {
            "failure_probability": 0.15,
            "confidence": 0.87,
            "predicted_failure_date": (datetime.utcnow()).isoformat(),
            "components_at_risk": ["engine", "transmission"],
            "timestamp": datetime.utcnow().isoformat()
        }
    }

@app.get("/alerts", tags=["Alerts"])
async def get_alerts(severity: str = None):
    """Get alerts based on vehicle telemetry anomalies"""
    try:
        from clickhouse_driver import Client
        import random
        
        client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
            database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
        )
        
        # Get latest telemetry for all vehicles to generate alerts
        query = """
        WITH latest_data AS (
            SELECT 
                vehicle_id,
                timestamp,
                engine_temp,
                vibration,
                battery_voltage,
                engine_rpm,
                fuel_level,
                ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY timestamp DESC) as rn
            FROM telemetry
            WHERE timestamp >= now() - INTERVAL 1 HOUR
        )
        SELECT 
            vehicle_id,
            timestamp,
            engine_temp,
            vibration,
            battery_voltage,
            engine_rpm,
            fuel_level
        FROM latest_data
        WHERE rn = 1
        """
        
        result = client.execute(query)
        
        alerts = []
        alert_id = 1
        
        for row in result:
            vehicle_id, timestamp, engine_temp, vibration, battery_voltage, engine_rpm, fuel_level = row
            
            # Check for critical engine temperature
            if engine_temp > 110:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "critical",
                    "message": f"Critical engine temperature: {engine_temp:.1f}°C",
                    "component": "Cooling System",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            elif engine_temp > 100:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "high",
                    "message": f"High engine temperature: {engine_temp:.1f}°C",
                    "component": "Cooling System",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            
            # Check for high vibration
            if vibration > 8:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "critical",
                    "message": f"Critical vibration detected: {vibration:.2f} mm/s",
                    "component": "Engine Mount",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            elif vibration > 6:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "medium",
                    "message": f"Elevated vibration: {vibration:.2f} mm/s",
                    "component": "Engine Mount",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            
            # Check for low battery voltage
            if battery_voltage < 11:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "critical",
                    "message": f"Critical battery voltage: {battery_voltage:.1f}V",
                    "component": "Battery",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            elif battery_voltage < 11.5:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "medium",
                    "message": f"Low battery voltage: {battery_voltage:.1f}V",
                    "component": "Battery",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
            
            # Check for abnormal RPM with low battery (potential alternator issue)
            if engine_rpm > 0 and battery_voltage < 12 and engine_temp > 90:
                alerts.append({
                    "id": f"ALERT_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "severity": "high",
                    "message": f"Potential alternator failure detected",
                    "component": "Alternator",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "status": "active"
                })
                alert_id += 1
        
        # Filter by severity if specified
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        
        # Sort by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "severity_filter": severity
        }
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        return {
            "alerts": [],
            "count": 0,
            "severity_filter": severity,
            "error": str(e)
        }

@app.get("/schedules", tags=["Maintenance"])
async def get_maintenance_schedules():
    """Get maintenance schedules"""
    return {
        "schedules": [],
        "count": 0
    }

@app.get("/manufacturing/feedback", tags=["Manufacturing"])
async def get_manufacturing_feedback():
    """Get CAPA feedback based on component failure patterns"""
    try:
        from clickhouse_driver import Client
        from collections import defaultdict
        
        client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
            database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
        )
        
        # Analyze patterns across vehicles
        query = """
        WITH recent_data AS (
            SELECT 
                vehicle_id,
                engine_temp,
                vibration,
                battery_voltage,
                engine_rpm,
                timestamp
            FROM telemetry
            WHERE timestamp >= now() - INTERVAL 24 HOUR
        )
        SELECT 
            COUNT(DISTINCT vehicle_id) as affected_vehicles,
            COUNT(*) as total_readings,
            AVG(engine_temp) as avg_temp,
            MAX(engine_temp) as max_temp,
            AVG(vibration) as avg_vibration,
            MAX(vibration) as max_vibration,
            AVG(battery_voltage) as avg_battery,
            MIN(battery_voltage) as min_battery
        FROM recent_data
        """
        
        result = client.execute(query)
        
        if not result:
            return {"feedback": [], "count": 0}
        
        stats = result[0]
        affected_vehicles, total_readings, avg_temp, max_temp, avg_vibration, max_vibration, avg_battery, min_battery = stats
        
        feedback = []
        
        # Generate CAPA recommendations based on patterns
        if max_temp > 105:
            feedback.append({
                "recommendation_id": "CAPA_COOL_001",
                "component": "Cooling System",
                "issue_type": "Overheating",
                "severity": "critical" if max_temp > 110 else "high",
                "affected_vehicles_count": affected_vehicles,
                "failure_count": int(total_readings * 0.15),  # Estimate
                "corrective_action": "Replace coolant and inspect radiator for blockages",
                "preventive_action": "Add thermal stress testing to QC process",
                "estimated_cost_per_vehicle": 500,
                "total_estimated_cost": affected_vehicles * 500,
                "production_line_impact": "Cooling System Assembly (Step 7)",
                "root_cause": "Insufficient coolant capacity or radiator efficiency",
                "confidence_score": 0.85,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        if max_vibration > 7:
            feedback.append({
                "recommendation_id": "CAPA_VIB_001",
                "component": "Engine Mount",
                "issue_type": "Excessive Vibration",
                "severity": "high",
                "affected_vehicles_count": affected_vehicles,
                "failure_count": int(total_readings * 0.12),
                "corrective_action": "Replace engine mounts and balance crankshaft",
                "preventive_action": "Improve engine mount material specification",
                "estimated_cost_per_vehicle": 350,
                "total_estimated_cost": affected_vehicles * 350,
                "production_line_impact": "Engine Mount Installation (Step 5)",
                "root_cause": "Inadequate engine mount damping or installation torque",
                "confidence_score": 0.78,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        if min_battery < 11.5:
            feedback.append({
                "recommendation_id": "CAPA_ELEC_001",
                "component": "Electrical System",
                "issue_type": "Battery Drain",
                "severity": "medium",
                "affected_vehicles_count": affected_vehicles,
                "failure_count": int(total_readings * 0.10),
                "corrective_action": "Test alternator output and check for parasitic drain",
                "preventive_action": "Add alternator load testing to final QC",
                "estimated_cost_per_vehicle": 400,
                "total_estimated_cost": affected_vehicles * 400,
                "production_line_impact": "Electrical System Integration (Step 9)",
                "root_cause": "Alternator underperformance or excessive parasitic load",
                "confidence_score": 0.72,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        if avg_temp > 95 and avg_vibration > 5:
            feedback.append({
                "recommendation_id": "CAPA_ENG_001",
                "component": "Engine Assembly",
                "issue_type": "Combined Thermal-Mechanical Stress",
                "severity": "high",
                "affected_vehicles_count": affected_vehicles,
                "failure_count": int(total_readings * 0.08),
                "corrective_action": "Comprehensive engine inspection and bearing replacement",
                "preventive_action": "Revise engine break-in procedure and QC parameters",
                "estimated_cost_per_vehicle": 800,
                "total_estimated_cost": affected_vehicles * 800,
                "production_line_impact": "Engine Assembly (Steps 3-6)",
                "root_cause": "Inadequate initial engine break-in or bearing tolerance issues",
                "confidence_score": 0.80,
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {
            "feedback": feedback,
            "count": len(feedback)
        }
    except Exception as e:
        logger.error(f"Error generating CAPA feedback: {e}")
        return {
            "feedback": [],
            "count": 0,
            "error": str(e)
        }

@app.get("/ueba/alerts", tags=["Security"])
async def get_security_alerts():
    """Get security/anomaly alerts from UEBA monitoring"""
    try:
        from clickhouse_driver import Client
        import random
        
        client = Client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "9000")),
            user=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"),
            database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")
        )
        
        # Check for statistical anomalies in vehicle behavior
        query = """
        WITH vehicle_stats AS (
            SELECT 
                vehicle_id,
                COUNT(*) as reading_count,
                AVG(engine_temp) as avg_temp,
                stddevSamp(engine_temp) as std_temp,
                AVG(vibration) as avg_vib,
                stddevSamp(vibration) as std_vib,
                MAX(timestamp) as last_seen
            FROM telemetry
            WHERE timestamp >= now() - INTERVAL 1 HOUR
            GROUP BY vehicle_id
        ),
        latest_readings AS (
            SELECT 
                vehicle_id,
                engine_temp,
                vibration,
                battery_voltage,
                engine_rpm,
                timestamp,
                ROW_NUMBER() OVER (PARTITION BY vehicle_id ORDER BY timestamp DESC) as rn
            FROM telemetry
            WHERE timestamp >= now() - INTERVAL 5 MINUTE
        )
        SELECT 
            lr.vehicle_id,
            lr.engine_temp,
            lr.vibration,
            lr.battery_voltage,
            lr.engine_rpm,
            lr.timestamp,
            vs.avg_temp,
            vs.std_temp,
            vs.avg_vib,
            vs.std_vib,
            vs.reading_count
        FROM latest_readings lr
        JOIN vehicle_stats vs ON lr.vehicle_id = vs.vehicle_id
        WHERE lr.rn = 1
        """
        
        result = client.execute(query)
        
        alerts = []
        alert_id = 1
        
        for row in result:
            vehicle_id, curr_temp, curr_vib, battery_v, rpm, timestamp, avg_temp, std_temp, avg_vib, std_vib, reading_count = row
            
            # Detect statistical anomalies (values beyond 3 standard deviations)
            if std_temp and std_temp > 0:
                temp_z_score = abs((curr_temp - avg_temp) / std_temp)
                if temp_z_score > 3:
                    alerts.append({
                        "anomaly_id": f"ANOM_{alert_id:04d}",
                        "vehicle_id": vehicle_id,
                        "anomaly_type": "statistical_outlier",
                        "severity": "high",
                        "metric": "engine_temperature",
                        "current_value": round(curr_temp, 2),
                        "expected_value": round(avg_temp, 2),
                        "deviation": round(temp_z_score, 2),
                        "message": f"Abnormal temperature spike detected (Z-score: {temp_z_score:.2f})",
                        "recommended_action": "Investigate sudden temperature change - possible sensor fault or actual thermal event",
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        "confidence": 0.90
                    })
                    alert_id += 1
            
            if std_vib and std_vib > 0:
                vib_z_score = abs((curr_vib - avg_vib) / std_vib)
                if vib_z_score > 3:
                    alerts.append({
                        "anomaly_id": f"ANOM_{alert_id:04d}",
                        "vehicle_id": vehicle_id,
                        "anomaly_type": "statistical_outlier",
                        "severity": "high",
                        "metric": "vibration",
                        "current_value": round(curr_vib, 2),
                        "expected_value": round(avg_vib, 2),
                        "deviation": round(vib_z_score, 2),
                        "message": f"Abnormal vibration pattern detected (Z-score: {vib_z_score:.2f})",
                        "recommended_action": "Check for mechanical failure or sensor malfunction",
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        "confidence": 0.88
                    })
                    alert_id += 1
            
            # Detect data quality anomalies
            if reading_count < 10:  # Too few readings in last hour
                alerts.append({
                    "anomaly_id": f"ANOM_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "anomaly_type": "data_quality",
                    "severity": "medium",
                    "metric": "telemetry_frequency",
                    "current_value": reading_count,
                    "expected_value": 60,  # Expected ~1 reading per minute
                    "deviation": round((60 - reading_count) / 60, 2),
                    "message": f"Reduced telemetry transmission rate detected ({reading_count} readings/hour)",
                    "recommended_action": "Check vehicle connectivity and telemetry system",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "confidence": 0.75
                })
                alert_id += 1
            
            # Detect impossible/suspicious values
            if battery_v > 14.5 or battery_v < 9:
                alerts.append({
                    "anomaly_id": f"ANOM_{alert_id:04d}",
                    "vehicle_id": vehicle_id,
                    "anomaly_type": "sensor_fault",
                    "severity": "high",
                    "metric": "battery_voltage",
                    "current_value": round(battery_v, 2),
                    "expected_value": 12.6,
                    "deviation": round(abs(battery_v - 12.6) / 12.6, 2),
                    "message": f"Battery voltage out of normal range: {battery_v:.2f}V",
                    "recommended_action": "Verify battery sensor calibration or replace faulty sensor",
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "confidence": 0.95
                })
                alert_id += 1
        
        # Sort by severity and timestamp
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda x: (severity_order.get(x["severity"], 4), x["timestamp"]), reverse=True)
        
        return {
            "alerts": alerts,
            "count": len(alerts)
        }
    except Exception as e:
        logger.error(f"Error fetching security alerts: {e}")
        return {
            "alerts": [],
            "count": 0,
            "error": str(e)
        }

@app.get("/ueba/agents", tags=["Agents"])
async def get_agents():
    """Get monitoring agents"""
    return {
        "agents": [],
        "count": 0
    }

@app.get("/ueba/stats", tags=["UEBA"])
async def get_ueba_stats():
    """Get UEBA statistics"""
    return {
        "monitored_agents": 0,
        "security_alerts": 0,
        "status": "operational"
    }

@app.get("/analytics/overview", tags=["Analytics"])
async def get_analytics_overview():
    """Get analytics dashboard overview"""
    return {
        "total_predictions": 1250,
        "avg_accuracy": 0.87,
        "anomalies_detected": 45,
        "capa_reports": 23,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/analytics/metrics", tags=["Analytics"])
async def get_analytics_metrics(time_range: str = "24h"):
    """Get aggregated metrics"""
    return {
        "time_range": time_range,
        "metrics": {
            "total_vehicles": 11,
            "total_telemetry_points": 15000,
            "predictions_made": 125,
            "alerts_generated": 34
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/service-centers", tags=["Maintenance"])
async def get_service_centers():
    """Get available service centers"""
    return {
        "service_centers": [
            {
                "id": "sc-001",
                "name": "Downtown Service Center",
                "location": "123 Main St",
                "available_slots": 5,
                "rating": 4.5
            },
            {
                "id": "sc-002",
                "name": "North Side Auto Care",
                "location": "456 North Ave",
                "available_slots": 3,
                "rating": 4.8
            }
        ],
        "count": 2
    }

# ============================================================================
# SOCKET.IO EVENT HANDLERS
# ============================================================================

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"🔌 Client connected: {sid}")
    await sio.emit('connected', {'message': 'Connected to server'}, room=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"🔌 Client disconnected: {sid}")

@sio.event
async def subscribe(sid, data):
    """Handle subscription to specific events"""
    event_type = data.get('event_type')
    logger.info(f"📡 Client {sid} subscribed to {event_type}")
    await sio.emit('subscribed', {'event_type': event_type}, room=sid)

# Background task to emit periodic updates
async def emit_updates():
    """Emit periodic updates to connected clients"""
    await asyncio.sleep(5)  # Wait for server to be ready
    
    while True:
        try:
            # Emit vehicle prediction update
            await sio.emit('vehicle_prediction', {
                'vehicle_id': 'VEHICLE_001',
                'prediction': {
                    'failure_probability': 0.15,
                    'confidence': 0.87,
                    'timestamp': datetime.utcnow().isoformat()
                }
            })
            
            # Emit alert update
            await sio.emit('vehicle_alert', {
                'vehicle_id': 'VEHICLE_002',
                'alert': {
                    'severity': 'medium',
                    'type': 'high_temperature',
                    'message': 'Engine temperature elevated',
                    'timestamp': datetime.utcnow().isoformat()
                }
            })
            
            await asyncio.sleep(10)  # Emit every 10 seconds
        except Exception as e:
            logger.error(f"Error emitting updates: {e}")
            await asyncio.sleep(10)

# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    logger.info("🚀 Starting Automotive Predictive Maintenance API")
    logger.info(f"📚 API Documentation: http://localhost:{os.getenv('API_PORT', '8000')}/docs")
    logger.info(f"📖 ReDoc: http://localhost:{os.getenv('API_PORT', '8000')}/redoc")
    logger.info(f"🔌 WebSocket enabled at ws://localhost:{os.getenv('API_PORT', '8000')}/socket.io")
    
    # Start background task for updates
    asyncio.create_task(emit_updates())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down API server")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "api.main:socket_app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
