"""
Agent Dashboard API - Phase 4
==============================
FastAPI service for real-time agent monitoring and alerting
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

API_PORT = int(os.getenv('AGENT_DASHBOARD_PORT', 8002))
API_HOST = os.getenv('AGENT_DASHBOARD_HOST', '0.0.0.0')

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class AgentStatus(BaseModel):
    agent_id: str
    agent_type: str
    status: str
    last_heartbeat: datetime
    messages_processed: int
    errors_count: int
    metadata: Dict = Field(default_factory=dict)
    uptime_seconds: Optional[float] = None

class Alert(BaseModel):
    alert_id: Optional[str] = None
    vehicle_id: str
    severity: str
    reason: str
    timestamp: datetime
    resolution_status: str = "pending"
    service_scheduled: bool = False

class MaintenanceSchedule(BaseModel):
    booking_id: str
    vehicle_id: str
    customer_id: str
    scheduled_date: datetime
    service_center: str
    severity: str
    status: str
    service_type: str
    estimated_duration: int

class ManufacturingFeedback(BaseModel):
    recommendation_id: str
    component: str
    failure_count: int
    severity: str
    root_cause_analysis: str
    corrective_action: str
    preventive_action: str
    priority: int
    estimated_impact: Dict
    created_at: datetime
    status: str = "pending"

class SecurityAnomaly(BaseModel):
    anomaly_id: str
    agent_id: str
    anomaly_score: float
    severity: str
    recommended_action: str
    timestamp: datetime
    status: str = "active"

class DashboardStats(BaseModel):
    total_agents: int
    active_agents: int
    inactive_agents: int
    total_alerts: int
    critical_alerts: int
    pending_schedules: int
    capa_recommendations: int
    security_anomalies: int
    system_health: str

class AcknowledgeRequest(BaseModel):
    acknowledged_by: str = "dashboard_user"
    notes: Optional[str] = None

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

mongo_client: Optional[AsyncIOMotorClient] = None
db = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global mongo_client, db
    
    # Startup
    logger.info("🚀 Starting Agent Dashboard API...")
    mongo_client = AsyncIOMotorClient(MONGODB_URI)
    db = mongo_client[MONGODB_DATABASE]
    
    try:
        await mongo_client.admin.command('ping')
        logger.info("✅ Connected to MongoDB")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Agent Dashboard API...")
    if mongo_client:
        mongo_client.close()
    logger.info("✅ Shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Agent Dashboard API",
    description="Real-time monitoring and management of autonomous agents",
    version="1.0.0",
    lifespan=lifespan
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
# ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """API root"""
    return {
        "service": "Agent Dashboard API",
        "version": "1.0.0",
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        await db.command('ping')
        return {
            "status": "healthy",
            "mongodb": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

# ----------------------------------------------------------------------------
# AGENT STATUS ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/agents/status", response_model=List[AgentStatus])
async def get_agents_status(
    agent_type: Optional[str] = Query(None, description="Filter by agent type"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """Get status of all agents"""
    try:
        query = {}
        if agent_type:
            query['agent_type'] = agent_type
        if status:
            query['status'] = status
        
        agents = await db.agent_status.find(query).to_list(length=100)
        
        # Calculate uptime
        now = datetime.now()
        for agent in agents:
            if 'metadata' in agent and 'started_at' in agent['metadata']:
                started = datetime.fromisoformat(agent['metadata']['started_at'])
                agent['uptime_seconds'] = (now - started).total_seconds()
        
        return agents
    
    except Exception as e:
        logger.error(f"Failed to get agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str):
    """Get detailed metrics for a specific agent"""
    try:
        agent = await db.agent_status.find_one({"agent_id": agent_id})
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
        
        # Calculate additional metrics
        now = datetime.now()
        last_heartbeat = agent.get('last_heartbeat', now)
        seconds_since_heartbeat = (now - last_heartbeat).total_seconds()
        
        metrics = {
            "agent_id": agent_id,
            "agent_type": agent.get('agent_type'),
            "status": agent.get('status'),
            "messages_processed": agent.get('messages_processed', 0),
            "errors_count": agent.get('errors_count', 0),
            "error_rate": agent.get('errors_count', 0) / max(agent.get('messages_processed', 1), 1),
            "last_heartbeat": last_heartbeat,
            "seconds_since_heartbeat": seconds_since_heartbeat,
            "is_healthy": seconds_since_heartbeat < 120,
            "metadata": agent.get('metadata', {})
        }
        
        return metrics
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# ALERT ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/alerts", response_model=List[Alert])
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status"),
    limit: int = Query(100, le=500, description="Maximum alerts to return")
):
    """Get vehicle alerts"""
    try:
        query = {}
        
        if severity:
            query['severity'] = severity
        if resolution_status:
            query['resolution_status'] = resolution_status
        
        alerts = await db.alerts_history.find(query).sort("timestamp", -1).limit(limit).to_list(length=limit)
        
        return alerts
    
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/alerts/unresolved", response_model=List[Alert])
async def get_unresolved_alerts():
    """Get all unresolved alerts"""
    try:
        alerts = await db.alerts_history.find({
            "resolution_status": {"$in": ["pending", "acknowledged"]}
        }).sort("timestamp", -1).to_list(length=200)
        
        return alerts
    
    except Exception as e:
        logger.error(f"Failed to get unresolved alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/alerts/{vehicle_id}/acknowledge")
async def acknowledge_alert(vehicle_id: str, request: AcknowledgeRequest):
    """Acknowledge an alert"""
    try:
        result = await db.alerts_history.update_one(
            {
                "vehicle_id": vehicle_id,
                "resolution_status": "pending"
            },
            {
                "$set": {
                    "resolution_status": "acknowledged",
                    "acknowledged_by": request.acknowledged_by,
                    "acknowledged_at": datetime.now(),
                    "notes": request.notes
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"No pending alert for vehicle {vehicle_id}")
        
        return {
            "message": f"Alert for vehicle {vehicle_id} acknowledged",
            "acknowledged_by": request.acknowledged_by,
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# SCHEDULING ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/schedules", response_model=List[MaintenanceSchedule])
async def get_maintenance_schedules(
    status: Optional[str] = Query(None, description="Filter by status"),
    days_ahead: int = Query(7, description="Days to look ahead")
):
    """Get upcoming maintenance schedules"""
    try:
        query = {
            "scheduled_date": {
                "$gte": datetime.now(),
                "$lte": datetime.now() + timedelta(days=days_ahead)
            }
        }
        
        if status:
            query['status'] = status
        
        schedules = await db.service_schedule.find(query).sort("scheduled_date", 1).to_list(length=200)
        
        return schedules
    
    except Exception as e:
        logger.error(f"Failed to get schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schedules/{vehicle_id}")
async def get_vehicle_schedule(vehicle_id: str):
    """Get schedule for specific vehicle"""
    try:
        schedule = await db.service_schedule.find_one({
            "vehicle_id": vehicle_id,
            "status": {"$in": ["pending", "confirmed"]},
            "scheduled_date": {"$gte": datetime.now()}
        })
        
        if not schedule:
            raise HTTPException(status_code=404, detail=f"No upcoming schedule for vehicle {vehicle_id}")
        
        return schedule
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get vehicle schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# MANUFACTURING ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/manufacturing/feedback", response_model=List[ManufacturingFeedback])
async def get_manufacturing_feedback(
    priority: Optional[int] = Query(None, description="Filter by priority (1-3)"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=200, description="Maximum recommendations to return")
):
    """Get CAPA recommendations"""
    try:
        query = {}
        
        if priority:
            query['priority'] = priority
        if status:
            query['status'] = status
        
        recommendations = await db.manufacturing_reports.find(query).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        return recommendations
    
    except Exception as e:
        logger.error(f"Failed to get manufacturing feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/manufacturing/insights")
async def get_manufacturing_insights():
    """Get aggregated manufacturing insights"""
    try:
        pipeline = [
            {
                "$group": {
                    "_id": "$component",
                    "total_failures": {"$sum": "$failure_count"},
                    "recommendations": {"$sum": 1},
                    "avg_priority": {"$avg": "$priority"},
                    "total_cost": {"$sum": "$estimated_impact.total_estimated_cost"}
                }
            },
            {"$sort": {"total_failures": -1}}
        ]
        
        insights = await db.manufacturing_reports.aggregate(pipeline).to_list(length=50)
        
        return {
            "component_insights": insights,
            "total_components": len(insights),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to get manufacturing insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# SECURITY ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/security/alerts", response_model=List[SecurityAnomaly])
async def get_security_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    limit: int = Query(50, le=200, description="Maximum alerts to return")
):
    """Get UEBA security alerts"""
    try:
        query = {"type": "security_anomaly"}
        
        if severity:
            query['severity'] = severity
        if agent_id:
            query['agent_id'] = agent_id
        
        alerts = await db.alerts_history.find(query).sort("timestamp", -1).limit(limit).to_list(length=limit)
        
        return alerts
    
    except Exception as e:
        logger.error(f"Failed to get security alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/security/anomalies/active")
async def get_active_anomalies():
    """Get active security anomalies"""
    try:
        anomalies = await db.alerts_history.find({
            "type": "security_anomaly",
            "status": "active",
            "timestamp": {"$gte": datetime.now() - timedelta(hours=24)}
        }).sort("timestamp", -1).to_list(length=100)
        
        return {
            "active_anomalies": anomalies,
            "count": len(anomalies),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Failed to get active anomalies: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# DASHBOARD STATS ENDPOINT
# ----------------------------------------------------------------------------

@app.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get aggregated dashboard statistics"""
    try:
        # Agent stats
        total_agents = await db.agent_status.count_documents({})
        active_agents = await db.agent_status.count_documents({"status": "active"})
        
        # Alert stats
        total_alerts = await db.alerts_history.count_documents({})
        critical_alerts = await db.alerts_history.count_documents({
            "severity": "critical",
            "resolution_status": {"$in": ["pending", "acknowledged"]}
        })
        
        # Schedule stats
        pending_schedules = await db.service_schedule.count_documents({
            "status": {"$in": ["pending", "confirmed"]},
            "scheduled_date": {"$gte": datetime.now()}
        })
        
        # Manufacturing stats
        capa_recommendations = await db.manufacturing_reports.count_documents({
            "status": "pending"
        })
        
        # Security stats
        security_anomalies = await db.alerts_history.count_documents({
            "type": "security_anomaly",
            "status": "active",
            "timestamp": {"$gte": datetime.now() - timedelta(hours=24)}
        })
        
        # Determine system health
        inactive_agents = total_agents - active_agents
        if critical_alerts > 10 or inactive_agents > 2 or security_anomalies > 5:
            system_health = "degraded"
        elif critical_alerts > 0 or inactive_agents > 0 or security_anomalies > 0:
            system_health = "warning"
        else:
            system_health = "healthy"
        
        return DashboardStats(
            total_agents=total_agents,
            active_agents=active_agents,
            inactive_agents=inactive_agents,
            total_alerts=total_alerts,
            critical_alerts=critical_alerts,
            pending_schedules=pending_schedules,
            capa_recommendations=capa_recommendations,
            security_anomalies=security_anomalies,
            system_health=system_health
        )
    
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.add(
        "logs/agent_dashboard_{time}.log",
        rotation="100 MB",
        retention="7 days",
        level="INFO"
    )
    
    logger.info("=" * 80)
    logger.info("📊 AGENT DASHBOARD API")
    logger.info("=" * 80)
    logger.info(f"🌐 Starting on {API_HOST}:{API_PORT}")
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info"
    )
