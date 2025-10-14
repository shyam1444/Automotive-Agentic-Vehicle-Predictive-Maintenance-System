"""
Manufacturing Feedback Dashboard API - Phase 5
===============================================
FastAPI endpoints for monitoring manufacturing insights and CAPA recommendations
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

API_PORT = int(os.getenv('MANUFACTURING_DASHBOARD_PORT', 8003))
API_HOST = os.getenv('MANUFACTURING_DASHBOARD_HOST', '0.0.0.0')

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class CAPAReport(BaseModel):
    recommendation_id: str
    component_id: str
    vehicle_model: str
    failure_count: int
    trend: str
    severity: str
    root_cause_analysis: str
    corrective_action: str
    preventive_action: str
    priority: int
    estimated_impact: Dict
    historical_context: Optional[Dict] = Field(default_factory=dict)
    processed_at: datetime
    status: str = "pending"

class ComponentTrend(BaseModel):
    component_id: str
    vehicle_model: str
    total_failures: int
    recommendations_count: int
    avg_priority: float
    total_cost: float
    trend: str
    latest_recommendation: datetime

class VehicleModelStats(BaseModel):
    vehicle_model: str
    total_failures: int
    components_affected: int
    critical_issues: int
    total_estimated_cost: float
    top_components: List[Dict]

class ManufacturingStats(BaseModel):
    total_reports: int
    pending_reports: int
    resolved_reports: int
    total_failures: int
    total_estimated_cost: float
    components_with_issues: int
    critical_recommendations: int
    trending_up_count: int
    trending_down_count: int

class TrendAnalysis(BaseModel):
    time_period: str
    data_points: List[Dict]
    overall_trend: str
    failure_rate_change: float

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
    logger.info("🚀 Starting Manufacturing Dashboard API...")
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
    logger.info("🛑 Shutting down Manufacturing Dashboard API...")
    if mongo_client:
        mongo_client.close()
    logger.info("✅ Shutdown complete")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Manufacturing Feedback Dashboard API",
    description="Real-time monitoring of manufacturing insights and CAPA recommendations",
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
        "service": "Manufacturing Feedback Dashboard API",
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
# CAPA REPORTS ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/manufacturing/reports", response_model=List[CAPAReport])
async def get_all_reports(
    status: Optional[str] = Query(None, description="Filter by status (pending/resolved)"),
    priority: Optional[int] = Query(None, description="Filter by priority (1-3)"),
    component_id: Optional[str] = Query(None, description="Filter by component"),
    vehicle_model: Optional[str] = Query(None, description="Filter by vehicle model"),
    limit: int = Query(100, le=500, description="Maximum reports to return")
):
    """Get all CAPA reports with optional filters"""
    try:
        query = {}
        
        if status:
            query['status'] = status
        if priority:
            query['priority'] = priority
        if component_id:
            query['component_id'] = component_id
        if vehicle_model:
            query['vehicle_model'] = vehicle_model
        
        reports = await db.manufacturing_reports.find(query).sort("processed_at", -1).limit(limit).to_list(length=limit)
        
        return reports
    
    except Exception as e:
        logger.error(f"Failed to get reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/manufacturing/reports/{recommendation_id}", response_model=CAPAReport)
async def get_report_by_id(recommendation_id: str):
    """Get specific CAPA report by ID"""
    try:
        report = await db.manufacturing_reports.find_one({"recommendation_id": recommendation_id})
        
        if not report:
            raise HTTPException(status_code=404, detail=f"Report {recommendation_id} not found")
        
        return report
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/manufacturing/reports/{recommendation_id}/status")
async def update_report_status(
    recommendation_id: str,
    status: str = Query(..., regex="^(pending|in_progress|resolved|rejected)$")
):
    """Update CAPA report status"""
    try:
        result = await db.manufacturing_reports.update_one(
            {"recommendation_id": recommendation_id},
            {
                "$set": {
                    "status": status,
                    "status_updated_at": datetime.now()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"Report {recommendation_id} not found")
        
        return {
            "message": f"Report {recommendation_id} status updated to {status}",
            "timestamp": datetime.now().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# COMPONENT TRENDS ENDPOINTS
# ----------------------------------------------------------------------------

@app.get("/manufacturing/trends/components", response_model=List[ComponentTrend])
async def get_component_trends(
    days: int = Query(30, description="Days to look back"),
    limit: int = Query(20, description="Max components to return")
):
    """Get failure trends grouped by component"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "processed_at": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": {
                        "component_id": "$component_id",
                        "vehicle_model": "$vehicle_model"
                    },
                    "total_failures": {"$sum": "$failure_count"},
                    "recommendations_count": {"$sum": 1},
                    "avg_priority": {"$avg": "$priority"},
                    "total_cost": {"$sum": "$estimated_impact.total_estimated_cost"},
                    "latest_recommendation": {"$max": "$processed_at"},
                    "trends": {"$push": "$trend"}
                }
            },
            {
                "$sort": {"total_failures": -1}
            },
            {
                "$limit": limit
            }
        ]
        
        results = await db.manufacturing_reports.aggregate(pipeline).to_list(length=limit)
        
        # Determine overall trend
        trends = []
        for result in results:
            trend_list = result['trends']
            increasing = sum(1 for t in trend_list if t == 'increasing')
            decreasing = sum(1 for t in trend_list if t == 'decreasing')
            
            if increasing > decreasing:
                overall_trend = 'increasing'
            elif decreasing > increasing:
                overall_trend = 'decreasing'
            else:
                overall_trend = 'stable'
            
            trends.append(ComponentTrend(
                component_id=result['_id']['component_id'],
                vehicle_model=result['_id']['vehicle_model'],
                total_failures=result['total_failures'],
                recommendations_count=result['recommendations_count'],
                avg_priority=round(result['avg_priority'], 2),
                total_cost=result['total_cost'],
                trend=overall_trend,
                latest_recommendation=result['latest_recommendation']
            ))
        
        return trends
    
    except Exception as e:
        logger.error(f"Failed to get component trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/manufacturing/trends/component/{component_id}")
async def get_component_trend_details(
    component_id: str,
    days: int = Query(30, description="Days to look back")
):
    """Get detailed trend for specific component"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        reports = await db.manufacturing_reports.find({
            "component_id": component_id,
            "processed_at": {"$gte": cutoff_date}
        }).sort("processed_at", 1).to_list(length=1000)
        
        if not reports:
            raise HTTPException(status_code=404, detail=f"No data found for component {component_id}")
        
        # Build time series
        data_points = []
        for report in reports:
            data_points.append({
                "timestamp": report['processed_at'].isoformat(),
                "failure_count": report['failure_count'],
                "trend": report['trend'],
                "severity": report['severity'],
                "estimated_cost": report['estimated_impact']['total_estimated_cost']
            })
        
        # Calculate overall trend
        recent_reports = reports[-5:] if len(reports) >= 5 else reports
        historical_reports = reports[:5] if len(reports) >= 5 else reports
        recent_count = sum(r['failure_count'] for r in recent_reports)
        historical_count = sum(r['failure_count'] for r in historical_reports)
        
        if historical_count > 0:
            failure_rate_change = ((recent_count - historical_count) / historical_count) * 100
        else:
            failure_rate_change = 0
        
        if failure_rate_change > 20:
            overall_trend = 'increasing'
        elif failure_rate_change < -20:
            overall_trend = 'decreasing'
        else:
            overall_trend = 'stable'
        
        return TrendAnalysis(
            time_period=f"Last {days} days",
            data_points=data_points,
            overall_trend=overall_trend,
            failure_rate_change=round(failure_rate_change, 2)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get component trend details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# VEHICLE MODEL INSIGHTS
# ----------------------------------------------------------------------------

@app.get("/manufacturing/insights/models", response_model=List[VehicleModelStats])
async def get_vehicle_model_insights(
    days: int = Query(30, description="Days to look back")
):
    """Get aggregated insights per vehicle model"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "processed_at": {"$gte": cutoff_date}
                }
            },
            {
                "$group": {
                    "_id": "$vehicle_model",
                    "total_failures": {"$sum": "$failure_count"},
                    "components": {"$addToSet": "$component_id"},
                    "critical_issues": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}
                    },
                    "total_cost": {"$sum": "$estimated_impact.total_estimated_cost"},
                    "component_failures": {
                        "$push": {
                            "component": "$component_id",
                            "failures": "$failure_count"
                        }
                    }
                }
            },
            {
                "$sort": {"total_failures": -1}
            }
        ]
        
        results = await db.manufacturing_reports.aggregate(pipeline).to_list(length=100)
        
        models = []
        for result in results:
            # Get top 5 components
            component_map = {}
            for comp in result['component_failures']:
                component_id = comp['component']
                if component_id not in component_map:
                    component_map[component_id] = 0
                component_map[component_id] += comp['failures']
            
            top_components = [
                {"component": k, "failures": v}
                for k, v in sorted(component_map.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            
            models.append(VehicleModelStats(
                vehicle_model=result['_id'],
                total_failures=result['total_failures'],
                components_affected=len(result['components']),
                critical_issues=result['critical_issues'],
                total_estimated_cost=result['total_cost'],
                top_components=top_components
            ))
        
        return models
    
    except Exception as e:
        logger.error(f"Failed to get model insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# STATISTICS ENDPOINT
# ----------------------------------------------------------------------------

@app.get("/manufacturing/stats", response_model=ManufacturingStats)
async def get_manufacturing_stats():
    """Get aggregated manufacturing statistics"""
    try:
        total_reports = await db.manufacturing_reports.count_documents({})
        pending_reports = await db.manufacturing_reports.count_documents({"status": "pending"})
        resolved_reports = await db.manufacturing_reports.count_documents({"status": "resolved"})
        
        # Aggregate failures and costs
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_failures": {"$sum": "$failure_count"},
                    "total_cost": {"$sum": "$estimated_impact.total_estimated_cost"},
                    "components": {"$addToSet": "$component_id"},
                    "critical_count": {
                        "$sum": {"$cond": [{"$eq": ["$severity", "critical"]}, 1, 0]}
                    },
                    "increasing_count": {
                        "$sum": {"$cond": [{"$eq": ["$trend", "increasing"]}, 1, 0]}
                    },
                    "decreasing_count": {
                        "$sum": {"$cond": [{"$eq": ["$trend", "decreasing"]}, 1, 0]}
                    }
                }
            }
        ]
        
        results = await db.manufacturing_reports.aggregate(pipeline).to_list(length=1)
        
        if results:
            result = results[0]
            return ManufacturingStats(
                total_reports=total_reports,
                pending_reports=pending_reports,
                resolved_reports=resolved_reports,
                total_failures=result['total_failures'],
                total_estimated_cost=result['total_cost'],
                components_with_issues=len(result['components']),
                critical_recommendations=result['critical_count'],
                trending_up_count=result['increasing_count'],
                trending_down_count=result['decreasing_count']
            )
        else:
            return ManufacturingStats(
                total_reports=total_reports,
                pending_reports=pending_reports,
                resolved_reports=resolved_reports,
                total_failures=0,
                total_estimated_cost=0,
                components_with_issues=0,
                critical_recommendations=0,
                trending_up_count=0,
                trending_down_count=0
            )
    
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# SEARCH ENDPOINT
# ----------------------------------------------------------------------------

@app.get("/manufacturing/search")
async def search_reports(
    query: str = Query(..., description="Search query (component or vehicle model)"),
    limit: int = Query(50, description="Max results")
):
    """Search CAPA reports by component or vehicle model"""
    try:
        search_query = {
            "$or": [
                {"component_id": {"$regex": query, "$options": "i"}},
                {"vehicle_model": {"$regex": query, "$options": "i"}},
                {"root_cause_analysis": {"$regex": query, "$options": "i"}}
            ]
        }
        
        reports = await db.manufacturing_reports.find(search_query).sort("processed_at", -1).limit(limit).to_list(length=limit)
        
        return {
            "query": query,
            "results_count": len(reports),
            "reports": reports
        }
    
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.add(
        "logs/manufacturing_dashboard_{time}.log",
        rotation="100 MB",
        retention="7 days",
        level="INFO"
    )
    
    logger.info("=" * 80)
    logger.info("🏭 MANUFACTURING FEEDBACK DASHBOARD API")
    logger.info("=" * 80)
    logger.info(f"🌐 Starting on {API_HOST}:{API_PORT}")
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info"
    )
