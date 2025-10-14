#!/usr/bin/env python3
"""
UEBA Dashboard API - Phase 6
=============================
FastAPI dashboard for monitoring UEBA agent behavior, security alerts,
and providing visualization endpoints for Kibana/Grafana integration
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from elasticsearch import AsyncElasticsearch
from loguru import logger
from dotenv import load_dotenv
import uvicorn

load_dotenv()

# Configuration
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost:9200')
API_PORT = int(os.getenv('UEBA_DASHBOARD_PORT', '8004'))

# ============================================================================
# MODELS
# ============================================================================

class SeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class AlertStatus(str, Enum):
    active = "active"
    investigating = "investigating"
    resolved = "resolved"
    false_positive = "false_positive"

class SecurityAlertResponse(BaseModel):
    alert_id: str
    agent_id: str
    anomaly_score: float
    metric: str
    current_value: float
    expected_range: Dict[str, float]
    deviation_sigma: float
    severity: str
    description: str
    timestamp: datetime
    model_type: str
    status: str = "active"

class AgentMetricsResponse(BaseModel):
    agent_id: str
    messages_per_sec: float
    error_rate: float
    avg_latency_ms: float
    action_diversity: float
    heartbeat_regularity: float
    activity_burst_score: float
    idle_time_ratio: float
    last_updated: datetime

class UEBAStatsResponse(BaseModel):
    total_agents_monitored: int
    total_alerts: int
    alerts_by_severity: Dict[str, int]
    anomalies_detected_today: int
    most_anomalous_agents: List[Dict[str, Any]]
    alert_trend_24h: List[Dict[str, Any]]

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="UEBA Dashboard API - Phase 6",
    description="User and Entity Behavior Analytics Dashboard",
    version="6.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database clients
mongo_client: Optional[AsyncIOMotorClient] = None
db = None
es_client: Optional[AsyncElasticsearch] = None

# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database connections"""
    global mongo_client, db, es_client
    
    logger.info("🚀 Starting UEBA Dashboard API...")
    
    # MongoDB
    try:
        mongo_client = AsyncIOMotorClient(MONGODB_URI)
        db = mongo_client[MONGODB_DATABASE]
        await db.command('ping')
        logger.info("✅ MongoDB connected")
    except Exception as e:
        logger.error(f"❌ MongoDB connection failed: {e}")
        raise
    
    # ElasticSearch (optional)
    try:
        es_client = AsyncElasticsearch([f'http://{ELASTICSEARCH_HOST}'])
        info = await es_client.info()
        logger.info(f"✅ ElasticSearch connected - Version: {info['version']['number']}")
    except Exception as e:
        logger.warning(f"⚠️  ElasticSearch not available: {e}")
        es_client = None
    
    logger.success("✅ UEBA Dashboard API ready")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections"""
    if mongo_client:
        mongo_client.close()
    if es_client:
        await es_client.close()
    logger.info("🛑 UEBA Dashboard API shut down")

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return {
        "service": "UEBA Dashboard API",
        "version": "6.0.0",
        "status": "operational",
        "elasticsearch_enabled": es_client is not None
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check"""
    try:
        await db.command('ping')
        mongo_status = "healthy"
    except:
        mongo_status = "unhealthy"
    
    es_status = "healthy" if es_client else "disabled"
    
    return {
        "status": "healthy" if mongo_status == "healthy" else "degraded",
        "mongodb": mongo_status,
        "elasticsearch": es_status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ----------------------------------------------------------------------------
# SECURITY ALERTS
# ----------------------------------------------------------------------------

@app.get("/ueba/alerts", response_model=List[SecurityAlertResponse], tags=["Security Alerts"])
async def get_security_alerts(
    severity: Optional[SeverityEnum] = None,
    agent_id: Optional[str] = None,
    status: Optional[AlertStatus] = None,
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get security alerts with optional filters
    
    - **severity**: Filter by severity (low, medium, high, critical)
    - **agent_id**: Filter by specific agent
    - **status**: Filter by status (active, investigating, resolved, false_positive)
    - **limit**: Maximum number of alerts to return
    - **offset**: Number of alerts to skip (pagination)
    """
    query = {}
    
    if severity:
        query["severity"] = severity.value
    
    if agent_id:
        query["agent_id"] = agent_id
    
    if status:
        query["status"] = status.value
    
    try:
        cursor = db.security_alerts_history.find(query).sort("timestamp", -1).skip(offset).limit(limit)
        alerts = await cursor.to_list(length=limit)
        
        # Add default status if missing
        for alert in alerts:
            if "status" not in alert:
                alert["status"] = "active"
        
        return alerts
    except Exception as e:
        logger.error(f"Failed to fetch alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ueba/alerts/{alert_id}", response_model=SecurityAlertResponse, tags=["Security Alerts"])
async def get_alert_by_id(alert_id: str):
    """Get specific alert by ID"""
    try:
        alert = await db.security_alerts_history.find_one({"alert_id": alert_id})
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        if "status" not in alert:
            alert["status"] = "active"
        
        return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/ueba/alerts/{alert_id}/status", tags=["Security Alerts"])
async def update_alert_status(alert_id: str, status: AlertStatus):
    """Update alert status"""
    try:
        result = await db.security_alerts_history.update_one(
            {"alert_id": alert_id},
            {"$set": {"status": status.value, "updated_at": datetime.now(timezone.utc)}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"message": "Alert status updated", "alert_id": alert_id, "new_status": status.value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update alert status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# AGENT METRICS
# ----------------------------------------------------------------------------

@app.get("/ueba/agents", tags=["Agent Metrics"])
async def get_monitored_agents():
    """Get list of all monitored agents"""
    try:
        agents = await db.agent_status.find(
            {"status": "active"},
            {"agent_id": 1, "agent_type": 1, "last_heartbeat": 1, "messages_processed": 1}
        ).to_list(length=1000)
        
        return {
            "total": len(agents),
            "agents": agents
        }
    except Exception as e:
        logger.error(f"Failed to fetch agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ueba/agents/{agent_id}/metrics", tags=["Agent Metrics"])
async def get_agent_metrics(agent_id: str):
    """Get current metrics for a specific agent"""
    try:
        agent = await db.agent_status.find_one({"agent_id": agent_id})
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return {
            "agent_id": agent_id,
            "status": agent.get("status"),
            "last_heartbeat": agent.get("last_heartbeat"),
            "messages_processed": agent.get("messages_processed", 0),
            "errors_count": agent.get("errors_count", 0),
            "metadata": agent.get("metadata", {})
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch agent metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ueba/agents/{agent_id}/alerts", response_model=List[SecurityAlertResponse], tags=["Agent Metrics"])
async def get_agent_alerts(agent_id: str, limit: int = Query(50, le=500)):
    """Get alerts for a specific agent"""
    try:
        cursor = db.security_alerts_history.find({"agent_id": agent_id}).sort("timestamp", -1).limit(limit)
        alerts = await cursor.to_list(length=limit)
        
        for alert in alerts:
            if "status" not in alert:
                alert["status"] = "active"
        
        return alerts
    except Exception as e:
        logger.error(f"Failed to fetch agent alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# STATISTICS & ANALYTICS
# ----------------------------------------------------------------------------

@app.get("/ueba/stats", response_model=UEBAStatsResponse, tags=["Statistics"])
async def get_ueba_statistics():
    """Get UEBA system statistics"""
    try:
        # Total agents
        total_agents = await db.agent_status.count_documents({"status": "active"})
        
        # Total alerts
        total_alerts = await db.security_alerts_history.count_documents({})
        
        # Alerts by severity
        severity_pipeline = [
            {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
        ]
        severity_results = await db.security_alerts_history.aggregate(severity_pipeline).to_list(length=10)
        alerts_by_severity = {item["_id"]: item["count"] for item in severity_results}
        
        # Today's anomalies
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        anomalies_today = await db.security_alerts_history.count_documents(
            {"timestamp": {"$gte": today_start}}
        )
        
        # Most anomalous agents (last 24h)
        last_24h = datetime.now(timezone.utc) - timedelta(hours=24)
        anomalous_pipeline = [
            {"$match": {"timestamp": {"$gte": last_24h}}},
            {"$group": {"_id": "$agent_id", "count": {"$sum": 1}, "avg_score": {"$avg": "$anomaly_score"}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        anomalous_results = await db.security_alerts_history.aggregate(anomalous_pipeline).to_list(length=10)
        most_anomalous = [
            {"agent_id": item["_id"], "alert_count": item["count"], "avg_anomaly_score": round(item["avg_score"], 3)}
            for item in anomalous_results
        ]
        
        # Alert trend (last 24 hours, hourly buckets)
        trend_pipeline = [
            {"$match": {"timestamp": {"$gte": last_24h}}},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {"format": "%Y-%m-%d %H:00", "date": "$timestamp"}
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        trend_results = await db.security_alerts_history.aggregate(trend_pipeline).to_list(length=24)
        alert_trend = [{"hour": item["_id"], "count": item["count"]} for item in trend_results]
        
        return {
            "total_agents_monitored": total_agents,
            "total_alerts": total_alerts,
            "alerts_by_severity": alerts_by_severity,
            "anomalies_detected_today": anomalies_today,
            "most_anomalous_agents": most_anomalous,
            "alert_trend_24h": alert_trend
        }
    except Exception as e:
        logger.error(f"Failed to fetch statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ueba/trends/severity", tags=["Statistics"])
async def get_severity_trends(days: int = Query(7, ge=1, le=90)):
    """Get alert severity trends over time"""
    try:
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_date}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                        "severity": "$severity"
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id.date": 1}}
        ]
        
        results = await db.security_alerts_history.aggregate(pipeline).to_list(length=1000)
        
        # Organize by date
        trends = {}
        for item in results:
            date = item["_id"]["date"]
            severity = item["_id"]["severity"]
            count = item["count"]
            
            if date not in trends:
                trends[date] = {"date": date, "low": 0, "medium": 0, "high": 0, "critical": 0}
            
            trends[date][severity] = count
        
        return {"trends": list(trends.values())}
    except Exception as e:
        logger.error(f"Failed to fetch severity trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# ELASTICSEARCH QUERIES (if available)
# ----------------------------------------------------------------------------

@app.get("/ueba/elasticsearch/activity/{agent_id}", tags=["ElasticSearch"])
async def query_activity_logs(
    agent_id: str,
    from_time: Optional[datetime] = None,
    to_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000)
):
    """Query activity logs from ElasticSearch"""
    if not es_client:
        raise HTTPException(status_code=503, detail="ElasticSearch not available")
    
    try:
        query = {
            "query": {
                "bool": {
                    "must": [{"term": {"agent_id": agent_id}}]
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": limit
        }
        
        if from_time or to_time:
            time_range = {}
            if from_time:
                time_range["gte"] = from_time.isoformat()
            if to_time:
                time_range["lte"] = to_time.isoformat()
            
            query["query"]["bool"]["must"].append({"range": {"timestamp": time_range}})
        
        result = await es_client.search(
            index="agent_activity_logs",
            body=query
        )
        
        hits = result["hits"]["hits"]
        activities = [hit["_source"] for hit in hits]
        
        return {
            "total": result["hits"]["total"]["value"],
            "activities": activities
        }
    except Exception as e:
        logger.error(f"ElasticSearch query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ueba/elasticsearch/search", tags=["ElasticSearch"])
async def search_alerts(
    query_string: str,
    index: str = Query("security_alerts", regex="^(security_alerts|agent_activity_logs)$"),
    limit: int = Query(50, le=500)
):
    """Full-text search in ElasticSearch"""
    if not es_client:
        raise HTTPException(status_code=503, detail="ElasticSearch not available")
    
    try:
        query = {
            "query": {
                "query_string": {
                    "query": query_string
                }
            },
            "sort": [{"timestamp": {"order": "desc"}}],
            "size": limit
        }
        
        result = await es_client.search(index=index, body=query)
        
        hits = result["hits"]["hits"]
        documents = [hit["_source"] for hit in hits]
        
        return {
            "total": result["hits"]["total"]["value"],
            "results": documents
        }
    except Exception as e:
        logger.error(f"ElasticSearch search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting UEBA Dashboard API on port {API_PORT}")
    uvicorn.run(
        "ueba_dashboard:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=False,
        log_level="info"
    )
