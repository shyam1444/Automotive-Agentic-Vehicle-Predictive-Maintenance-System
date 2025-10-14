"""
Manufacturing Agent - Phase 5 (Enhanced with ClickHouse Integration)
=====================================================================
Long-term failure aggregation, trend analysis, and CAPA recommendations
Integrates real-time Kafka data with historical ClickHouse analytics
"""

import os
import asyncio
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from clickhouse_driver import Client as ClickHouseClient
from loguru import logger
from dotenv import load_dotenv
import pandas as pd
import numpy as np

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPICS = ['diagnostic_results', 'vehicle_alerts']
KAFKA_OUTPUT_TOPIC = 'manufacturing_feedback'
KAFKA_ACTIVITY_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'manufacturing_agent_phase5'

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', 9000))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_pass')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'telemetry_db')

AGENT_ID = 'MANUFACTURING_PHASE5_001'
HEARTBEAT_INTERVAL = 30

# Analysis configuration
REALTIME_WINDOW = timedelta(hours=24)  # Real-time buffer
HISTORICAL_LOOKBACK = timedelta(days=30)  # ClickHouse lookback
MIN_FAILURE_COUNT = 5  # Minimum for pattern detection
TREND_ANALYSIS_INTERVAL = 300  # 5 minutes
CAPA_GENERATION_INTERVAL = 600  # 10 minutes

# Trend thresholds
TREND_INCREASING_THRESHOLD = 0.2  # 20% increase
TREND_DECREASING_THRESHOLD = -0.2  # 20% decrease

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ComponentFailure:
    component_id: str
    vehicle_id: str
    vehicle_model: str
    failure_type: str
    severity: str
    likelihood: float
    timestamp: datetime
    source: str  # 'realtime' or 'historical'

@dataclass
class FailureTrend:
    component_id: str
    vehicle_model: str
    failure_count: int
    trend: str  # 'increasing', 'decreasing', 'stable'
    trend_percentage: float
    severity_distribution: Dict[str, int]
    first_detected: datetime
    last_detected: datetime
    avg_likelihood: float

@dataclass
class CAPARecommendation:
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
    historical_context: Dict
    processed_at: datetime

# ============================================================================
# CLICKHOUSE ANALYTICS ENGINE
# ============================================================================

class ClickHouseAnalytics:
    """Queries historical failure data from ClickHouse"""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self.client = ClickHouseClient(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        self.database = database
    
    def get_historical_failures(self, lookback_days: int = 30) -> List[ComponentFailure]:
        """Extract historical component failures from ClickHouse"""
        
        query = f"""
        SELECT 
            vehicle_id,
            timestamp,
            engine_temp,
            vibration_level,
            rpm,
            battery_voltage,
            fuel_level,
            predicted_failure,
            confidence_score
        FROM {self.database}.vehicle_predictions
        WHERE timestamp >= now() - INTERVAL {lookback_days} DAY
          AND predicted_failure = 1
        ORDER BY timestamp DESC
        LIMIT 10000
        """
        
        try:
            result = self.client.execute(query)
            
            failures = []
            for row in result:
                vehicle_id, timestamp, engine_temp, vibration, rpm, battery, fuel, _, confidence = row
                
                # Infer component failures from telemetry
                component_failures = self._infer_component_from_telemetry(
                    vehicle_id, timestamp, engine_temp, vibration, rpm, battery, fuel, confidence
                )
                failures.extend(component_failures)
            
            logger.info(f"📊 Extracted {len(failures)} historical failures from ClickHouse")
            return failures
        
        except Exception as e:
            logger.error(f"❌ ClickHouse query failed: {e}")
            return []
    
    def _infer_component_from_telemetry(
        self, vehicle_id: str, timestamp: datetime, 
        engine_temp: float, vibration: float, rpm: float, 
        battery: float, fuel: float, confidence: float
    ) -> List[ComponentFailure]:
        """Infer component failures from telemetry thresholds"""
        
        failures = []
        vehicle_model = self._get_vehicle_model(vehicle_id)
        
        # Engine temperature issues
        if engine_temp > 120:
            failures.append(ComponentFailure(
                component_id='COOLING_SYSTEM',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Overheating',
                severity='critical',
                likelihood=min(confidence * 1.2, 1.0),
                timestamp=timestamp,
                source='historical'
            ))
        elif engine_temp > 100:
            failures.append(ComponentFailure(
                component_id='COOLING_SYSTEM',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Temperature Warning',
                severity='warning',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        
        # Vibration issues
        if vibration > 8.0:
            failures.append(ComponentFailure(
                component_id='ENGINE_MOUNT',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Excessive Vibration',
                severity='critical',
                likelihood=min(confidence * 1.1, 1.0),
                timestamp=timestamp,
                source='historical'
            ))
        elif vibration > 3.0:
            failures.append(ComponentFailure(
                component_id='ENGINE_MOUNT',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='High Vibration',
                severity='warning',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        
        # RPM issues
        if rpm > 6000:
            failures.append(ComponentFailure(
                component_id='ENGINE_ECU',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Over-revving',
                severity='warning',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        
        # Battery issues
        if battery < 10.0:
            failures.append(ComponentFailure(
                component_id='BATTERY',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Critical Low Voltage',
                severity='critical',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        elif battery < 11.5:
            failures.append(ComponentFailure(
                component_id='BATTERY',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Low Voltage',
                severity='warning',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        
        # Fuel issues
        if fuel < 5.0:
            failures.append(ComponentFailure(
                component_id='FUEL_SYSTEM',
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type='Critical Low Fuel',
                severity='warning',
                likelihood=confidence,
                timestamp=timestamp,
                source='historical'
            ))
        
        return failures
    
    def _get_vehicle_model(self, vehicle_id: str) -> str:
        """Infer vehicle model from vehicle_id (mock)"""
        # In production, query from vehicle registry
        if 'HERO' in vehicle_id.upper():
            return 'HERO_2025'
        elif 'SPLENDOR' in vehicle_id.upper():
            return 'SPLENDOR_2025'
        elif 'PASSION' in vehicle_id.upper():
            return 'PASSION_2025'
        else:
            return 'UNKNOWN_MODEL'
    
    def get_failure_statistics(self, component_id: str, days: int = 30) -> Dict:
        """Get statistical summary for a component"""
        
        query = f"""
        SELECT 
            COUNT(*) as total_predictions,
            SUM(predicted_failure) as total_failures,
            AVG(confidence_score) as avg_confidence
        FROM {self.database}.vehicle_predictions
        WHERE timestamp >= now() - INTERVAL {days} DAY
        LIMIT 1
        """
        
        try:
            result = self.client.execute(query)
            if result:
                total, failures, confidence = result[0]
                return {
                    'total_predictions': total,
                    'total_failures': failures,
                    'failure_rate': failures / total if total > 0 else 0,
                    'avg_confidence': confidence
                }
        except Exception as e:
            logger.error(f"❌ Statistics query failed: {e}")
        
        return {
            'total_predictions': 0,
            'total_failures': 0,
            'failure_rate': 0,
            'avg_confidence': 0
        }

# ============================================================================
# TREND ANALYSIS ENGINE
# ============================================================================

class TrendAnalysisEngine:
    """Analyzes failure trends over time"""
    
    def analyze_trends(
        self, 
        realtime_failures: List[ComponentFailure],
        historical_failures: List[ComponentFailure]
    ) -> List[FailureTrend]:
        """Analyze trends by comparing recent vs historical data"""
        
        # Group failures by component + model
        realtime_grouped = self._group_failures(realtime_failures)
        historical_grouped = self._group_failures(historical_failures)
        
        trends = []
        
        # Analyze each component
        for key, realtime_data in realtime_grouped.items():
            component_id, vehicle_model = key
            historical_data = historical_grouped.get(key, [])
            
            if len(realtime_data) < MIN_FAILURE_COUNT:
                continue
            
            # Calculate trend
            trend_info = self._calculate_trend(realtime_data, historical_data)
            
            # Extract severity distribution
            severity_counts = Counter([f.severity for f in realtime_data])
            
            # Get timestamps
            timestamps = [f.timestamp for f in realtime_data + historical_data]
            first_detected = min(timestamps)
            last_detected = max(timestamps)
            
            # Calculate average likelihood
            avg_likelihood = np.mean([f.likelihood for f in realtime_data])
            
            trend = FailureTrend(
                component_id=component_id,
                vehicle_model=vehicle_model,
                failure_count=len(realtime_data),
                trend=trend_info['trend'],
                trend_percentage=trend_info['percentage'],
                severity_distribution=dict(severity_counts),
                first_detected=first_detected,
                last_detected=last_detected,
                avg_likelihood=avg_likelihood
            )
            
            trends.append(trend)
        
        return trends
    
    def _group_failures(self, failures: List[ComponentFailure]) -> Dict[Tuple[str, str], List[ComponentFailure]]:
        """Group failures by (component_id, vehicle_model)"""
        grouped = defaultdict(list)
        for failure in failures:
            key = (failure.component_id, failure.vehicle_model)
            grouped[key].append(failure)
        return grouped
    
    def _calculate_trend(
        self, 
        realtime_data: List[ComponentFailure],
        historical_data: List[ComponentFailure]
    ) -> Dict:
        """Calculate trend (increasing/decreasing/stable)"""
        
        if not historical_data:
            return {'trend': 'new', 'percentage': 0.0}
        
        # Calculate failure rate per day
        realtime_days = (max(f.timestamp for f in realtime_data) - 
                         min(f.timestamp for f in realtime_data)).days + 1
        historical_days = (max(f.timestamp for f in historical_data) - 
                           min(f.timestamp for f in historical_data)).days + 1
        
        realtime_rate = len(realtime_data) / max(realtime_days, 1)
        historical_rate = len(historical_data) / max(historical_days, 1)
        
        if historical_rate == 0:
            return {'trend': 'increasing', 'percentage': 100.0}
        
        # Calculate percentage change
        percentage_change = (realtime_rate - historical_rate) / historical_rate
        
        if percentage_change >= TREND_INCREASING_THRESHOLD:
            trend = 'increasing'
        elif percentage_change <= TREND_DECREASING_THRESHOLD:
            trend = 'decreasing'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'percentage': percentage_change * 100
        }

# ============================================================================
# ENHANCED CAPA ENGINE
# ============================================================================

class EnhancedCAPAEngine:
    """Generates CAPA recommendations with historical context"""
    
    CAPA_KNOWLEDGE_BASE = {
        "COOLING_SYSTEM": {
            "Overheating": {
                "corrective": "Replace coolant, inspect radiator for blockages, check water pump operation",
                "preventive": "Implement regular coolant quality checks at assembly. Add thermal stress testing to QC. Review radiator supplier quality.",
                "assembly_step": "Cooling System Assembly (Step 7)",
                "estimated_cost": 500
            },
            "Temperature Warning": {
                "corrective": "Check coolant level, inspect thermostat, verify fan operation",
                "preventive": "Add coolant level sensor to pre-delivery inspection. Improve thermal monitoring.",
                "assembly_step": "Cooling System Assembly (Step 7)",
                "estimated_cost": 300
            }
        },
        "ENGINE_MOUNT": {
            "Excessive Vibration": {
                "corrective": "Replace engine mounts, balance crankshaft, inspect transmission coupling",
                "preventive": "Add vibration testing to engine assembly. Use higher-grade engine mounts. Review engine balancing process.",
                "assembly_step": "Engine Mounting (Step 10)",
                "estimated_cost": 800
            },
            "High Vibration": {
                "corrective": "Inspect engine mounts, check belt tension, verify alignment",
                "preventive": "Add vibration sensors to production testing. Improve mount quality control.",
                "assembly_step": "Engine Mounting (Step 10)",
                "estimated_cost": 400
            }
        },
        "ENGINE_ECU": {
            "Over-revving": {
                "corrective": "ECU recalibration, check throttle position sensor, verify governor settings",
                "preventive": "Update ECU software with improved RPM limiter. Add throttle sensor calibration check.",
                "assembly_step": "Engine Control Module (Step 12)",
                "estimated_cost": 600
            }
        },
        "BATTERY": {
            "Critical Low Voltage": {
                "corrective": "Replace battery, check alternator output, inspect charging circuit",
                "preventive": "Switch to higher-capacity battery supplier. Add load testing to pre-delivery inspection.",
                "assembly_step": "Electrical System (Step 15)",
                "estimated_cost": 250
            },
            "Low Voltage": {
                "corrective": "Test battery, check alternator, inspect connections",
                "preventive": "Improve battery quality control. Add voltage monitoring to telematics.",
                "assembly_step": "Electrical System (Step 15)",
                "estimated_cost": 150
            }
        },
        "FUEL_SYSTEM": {
            "Critical Low Fuel": {
                "corrective": "N/A (operational issue, not manufacturing defect)",
                "preventive": "Add fuel level monitoring to telematics. Send proactive alerts at 15%. Improve gauge accuracy.",
                "assembly_step": "Fuel System Assembly (Step 8)",
                "estimated_cost": 100
            }
        }
    }
    
    def __init__(self, clickhouse_analytics: ClickHouseAnalytics):
        self.clickhouse = clickhouse_analytics
    
    def generate_capa(
        self, 
        trend: FailureTrend,
        historical_context: Dict
    ) -> CAPARecommendation:
        """Generate CAPA recommendation with historical insights"""
        
        component_id = trend.component_id
        failure_type = self._get_primary_failure_type(trend)
        
        # Lookup CAPA actions
        capa_actions = self.CAPA_KNOWLEDGE_BASE.get(component_id, {}).get(failure_type, {
            "corrective": f"Investigate {component_id} - {failure_type}. Perform detailed root cause analysis.",
            "preventive": f"Monitor {component_id} failure rates. Consider design review and supplier evaluation.",
            "assembly_step": "Unknown",
            "estimated_cost": 400
        })
        
        # Determine severity and priority
        severity_dist = trend.severity_distribution
        if severity_dist.get('critical', 0) > 0:
            severity = 'critical'
            priority = 1
        elif severity_dist.get('warning', 0) >= trend.failure_count * 0.5:
            severity = 'warning'
            priority = 2
        else:
            severity = 'info'
            priority = 3
        
        # Adjust priority based on trend
        if trend.trend == 'increasing':
            priority = max(1, priority - 1)
        
        # Calculate estimated impact
        estimated_impact = {
            "failure_count": trend.failure_count,
            "trend": trend.trend,
            "trend_percentage": round(trend.trend_percentage, 2),
            "estimated_cost_per_fix": capa_actions.get('estimated_cost', 400),
            "total_estimated_cost": trend.failure_count * capa_actions.get('estimated_cost', 400),
            "production_line_impact": capa_actions.get('assembly_step', 'Unknown'),
            "failure_rate": historical_context.get('failure_rate', 0),
            "avg_confidence": historical_context.get('avg_confidence', 0)
        }
        
        # Enhanced root cause analysis
        rca = self._generate_root_cause_analysis(trend, historical_context)
        
        return CAPARecommendation(
            recommendation_id=f"CAPA_{uuid.uuid4().hex[:8].upper()}",
            component_id=component_id,
            vehicle_model=trend.vehicle_model,
            failure_count=trend.failure_count,
            trend=trend.trend,
            severity=severity,
            root_cause_analysis=rca,
            corrective_action=capa_actions.get('corrective', 'N/A'),
            preventive_action=capa_actions.get('preventive', 'N/A'),
            priority=priority,
            estimated_impact=estimated_impact,
            historical_context=historical_context,
            processed_at=datetime.now()
        )
    
    def _get_primary_failure_type(self, trend: FailureTrend) -> str:
        """Determine primary failure type (simplified)"""
        # In production, analyze actual failure types from trend data
        component_map = {
            'COOLING_SYSTEM': 'Overheating',
            'ENGINE_MOUNT': 'Excessive Vibration',
            'ENGINE_ECU': 'Over-revving',
            'BATTERY': 'Critical Low Voltage',
            'FUEL_SYSTEM': 'Critical Low Fuel'
        }
        return component_map.get(trend.component_id, 'Unknown Failure')
    
    def _generate_root_cause_analysis(
        self, 
        trend: FailureTrend,
        historical_context: Dict
    ) -> str:
        """Generate comprehensive RCA text"""
        
        rca = f"Component '{trend.component_id}' in vehicle model '{trend.vehicle_model}' "
        rca += f"has experienced {trend.failure_count} failures. "
        
        if trend.trend == 'increasing':
            rca += f"Trend is INCREASING by {trend.trend_percentage:.1f}%, indicating a worsening issue. "
        elif trend.trend == 'decreasing':
            rca += f"Trend is DECREASING by {abs(trend.trend_percentage):.1f}%, showing improvement. "
        else:
            rca += f"Trend is STABLE. "
        
        rca += f"First detected: {trend.first_detected.strftime('%Y-%m-%d')}. "
        rca += f"Average confidence: {trend.avg_likelihood:.2f}. "
        
        failure_rate = historical_context.get('failure_rate', 0)
        if failure_rate > 0:
            rca += f"Historical failure rate: {failure_rate:.2%}. "
        
        if trend.severity_distribution.get('critical', 0) > 0:
            rca += "CRITICAL severity detected - immediate action required."
        
        return rca

# ============================================================================
# PHASE 5 MANUFACTURING AGENT
# ============================================================================

class ManufacturingAgentPhase5:
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.patterns_detected = 0
        self.capa_generated = 0
        self.errors_count = 0
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.activity_producer: Optional[AIOKafkaProducer] = None
        
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        self.clickhouse_analytics: Optional[ClickHouseAnalytics] = None
        self.trend_engine = TrendAnalysisEngine()
        self.capa_engine: Optional[EnhancedCAPAEngine] = None
        
        # Buffers
        self.realtime_failure_buffer = []
        self.historical_failures_cache = []
        self.last_historical_refresh = None
        
        logger.add(
            "logs/manufacturing_agent_phase5_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start Manufacturing Agent Phase 5"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🏭 MANUFACTURING AGENT PHASE 5 STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.connect_clickhouse()
        await self.init_kafka()
        await self.register_agent()
        
        self.capa_engine = EnhancedCAPAEngine(self.clickhouse_analytics)
        
        # Load initial historical data
        await self.refresh_historical_data()
        
        asyncio.create_task(self.send_heartbeat())
        asyncio.create_task(self.periodic_trend_analysis())
        asyncio.create_task(self.periodic_historical_refresh())
        
        logger.info("✅ Manufacturing Agent Phase 5 started")
        logger.info(f"📥 Consuming from: {', '.join(KAFKA_INPUT_TOPICS)}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        logger.info(f"🔍 ClickHouse lookback: {HISTORICAL_LOOKBACK.days} days")
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_diagnostic(message.value)
                self.messages_processed += 1
        
        except Exception as e:
            logger.error(f"❌ Error: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def connect_mongodb(self):
        """Connect to MongoDB"""
        self.mongo_client = AsyncIOMotorClient(MONGODB_URI)
        self.db = self.mongo_client[MONGODB_DATABASE]
        await self.mongo_client.admin.command('ping')
        logger.info("✅ Connected to MongoDB")
    
    async def connect_clickhouse(self):
        """Connect to ClickHouse"""
        try:
            self.clickhouse_analytics = ClickHouseAnalytics(
                host=CLICKHOUSE_HOST,
                port=CLICKHOUSE_PORT,
                user=CLICKHOUSE_USER,
                password=CLICKHOUSE_PASSWORD,
                database=CLICKHOUSE_DATABASE
            )
            # Test connection
            stats = self.clickhouse_analytics.get_failure_statistics('TEST', 1)
            logger.info(f"✅ Connected to ClickHouse: {stats}")
        except Exception as e:
            logger.warning(f"⚠️ ClickHouse connection failed: {e}")
            self.clickhouse_analytics = None
    
    async def init_kafka(self):
        """Initialize Kafka"""
        self.consumer = AIOKafkaConsumer(
            *KAFKA_INPUT_TOPICS,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset='latest',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.activity_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        await self.consumer.start()
        await self.producer.start()
        await self.activity_producer.start()
        
        logger.info("✅ Kafka initialized")
    
    async def register_agent(self):
        """Register agent"""
        await self.db.agent_status.update_one(
            {"agent_id": AGENT_ID},
            {"$set": {
                "agent_id": AGENT_ID,
                "agent_type": "manufacturing_phase5",
                "status": "active",
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {
                    "started_at": datetime.now().isoformat(),
                    "realtime_window_hours": REALTIME_WINDOW.total_seconds() / 3600,
                    "historical_lookback_days": HISTORICAL_LOOKBACK.days,
                    "clickhouse_enabled": self.clickhouse_analytics is not None
                }
            }},
            upsert=True
        )
        logger.info(f"📝 Registered: {AGENT_ID}")
    
    async def process_diagnostic(self, diagnostic: Dict):
        """Process diagnostic result from Kafka"""
        try:
            # Add timestamp if missing
            if 'timestamp' not in diagnostic:
                diagnostic['timestamp'] = datetime.now().isoformat()
            
            # Extract component failures
            failures = self._extract_failures_from_diagnostic(diagnostic)
            self.realtime_failure_buffer.extend(failures)
            
            # Keep buffer size manageable
            if len(self.realtime_failure_buffer) > 1000:
                self.realtime_failure_buffer = self.realtime_failure_buffer[-1000:]
            
        except Exception as e:
            logger.error(f"❌ Failed to process diagnostic: {e}")
            self.errors_count += 1
    
    def _extract_failures_from_diagnostic(self, diagnostic: Dict) -> List[ComponentFailure]:
        """Extract component failures from diagnostic result"""
        failures = []
        
        vehicle_id = diagnostic.get('vehicle_id', 'UNKNOWN')
        vehicle_model = diagnostic.get('vehicle_model', self._infer_vehicle_model(vehicle_id))
        timestamp_str = diagnostic.get('timestamp', datetime.now().isoformat())
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            timestamp = datetime.now()
        
        # Extract root causes if available
        for root_cause in diagnostic.get('root_causes', []):
            failures.append(ComponentFailure(
                component_id=self._normalize_component_id(root_cause.get('component', 'UNKNOWN')),
                vehicle_id=vehicle_id,
                vehicle_model=vehicle_model,
                failure_type=root_cause.get('issue', 'Unknown'),
                severity=diagnostic.get('severity', 'info'),
                likelihood=root_cause.get('likelihood', 0.5),
                timestamp=timestamp,
                source='realtime'
            ))
        
        return failures
    
    def _normalize_component_id(self, component: str) -> str:
        """Normalize component names to standard IDs"""
        mapping = {
            'Cooling System': 'COOLING_SYSTEM',
            'Engine': 'ENGINE_MOUNT',
            'ECU': 'ENGINE_ECU',
            'Battery': 'BATTERY',
            'Fuel System': 'FUEL_SYSTEM'
        }
        return mapping.get(component, component.upper().replace(' ', '_'))
    
    def _infer_vehicle_model(self, vehicle_id: str) -> str:
        """Infer vehicle model from ID"""
        if 'HERO' in vehicle_id.upper():
            return 'HERO_2025'
        elif 'SPLENDOR' in vehicle_id.upper():
            return 'SPLENDOR_2025'
        elif 'PASSION' in vehicle_id.upper():
            return 'PASSION_2025'
        return 'UNKNOWN_MODEL'
    
    async def refresh_historical_data(self):
        """Refresh historical failure data from ClickHouse"""
        if not self.clickhouse_analytics:
            logger.warning("⚠️ ClickHouse not available, skipping historical refresh")
            return
        
        try:
            logger.info("🔄 Refreshing historical data from ClickHouse...")
            
            # Run synchronous ClickHouse query in thread pool
            loop = asyncio.get_event_loop()
            historical_failures = await loop.run_in_executor(
                None,
                self.clickhouse_analytics.get_historical_failures,
                HISTORICAL_LOOKBACK.days
            )
            
            self.historical_failures_cache = historical_failures
            self.last_historical_refresh = datetime.now()
            
            logger.info(f"✅ Loaded {len(historical_failures)} historical failures")
            
        except Exception as e:
            logger.error(f"❌ Historical data refresh failed: {e}")
    
    async def periodic_historical_refresh(self):
        """Periodically refresh historical data"""
        while self.running:
            await asyncio.sleep(3600)  # Every hour
            await self.refresh_historical_data()
    
    async def periodic_trend_analysis(self):
        """Periodically analyze trends and generate CAPA"""
        
        # Initial delay
        await asyncio.sleep(120)
        
        while self.running:
            await asyncio.sleep(CAPA_GENERATION_INTERVAL)
            
            try:
                await self.analyze_and_generate_capa()
            except Exception as e:
                logger.error(f"❌ Trend analysis failed: {e}", exc_info=True)
    
    async def analyze_and_generate_capa(self):
        """Analyze trends and generate CAPA recommendations"""
        
        if len(self.realtime_failure_buffer) < MIN_FAILURE_COUNT:
            logger.debug(f"⏭️ Insufficient realtime data: {len(self.realtime_failure_buffer)} failures")
            return
        
        logger.info(f"🔍 Analyzing trends: {len(self.realtime_failure_buffer)} realtime, "
                   f"{len(self.historical_failures_cache)} historical")
        
        # Analyze trends
        trends = self.trend_engine.analyze_trends(
            self.realtime_failure_buffer,
            self.historical_failures_cache
        )
        
        if not trends:
            logger.debug("⏭️ No significant trends detected")
            return
        
        logger.info(f"✅ Detected {len(trends)} failure trends")
        self.patterns_detected += len(trends)
        
        # Generate CAPA for each trend
        for trend in trends:
            # Get historical context from ClickHouse
            historical_context = {}
            if self.clickhouse_analytics:
                loop = asyncio.get_event_loop()
                historical_context = await loop.run_in_executor(
                    None,
                    self.clickhouse_analytics.get_failure_statistics,
                    trend.component_id,
                    HISTORICAL_LOOKBACK.days
                )
            
            # Generate CAPA
            capa = self.capa_engine.generate_capa(trend, historical_context)
            
            # Store in MongoDB
            capa_doc = {
                "recommendation_id": capa.recommendation_id,
                "component_id": capa.component_id,
                "vehicle_model": capa.vehicle_model,
                "failure_count": capa.failure_count,
                "trend": capa.trend,
                "severity": capa.severity,
                "root_cause_analysis": capa.root_cause_analysis,
                "corrective_action": capa.corrective_action,
                "preventive_action": capa.preventive_action,
                "priority": capa.priority,
                "estimated_impact": capa.estimated_impact,
                "historical_context": capa.historical_context,
                "processed_at": capa.processed_at,
                "status": "pending"
            }
            
            await self.db.manufacturing_reports.insert_one(capa_doc)
            
            # Publish to Kafka
            feedback_message = {
                "recommendation_id": capa.recommendation_id,
                "component_id": capa.component_id,
                "vehicle_model": capa.vehicle_model,
                "failure_count": capa.failure_count,
                "trend": capa.trend,
                "severity": capa.severity,
                "corrective_action": capa.corrective_action,
                "preventive_action": capa.preventive_action,
                "priority": capa.priority,
                "estimated_impact": capa.estimated_impact,
                "timestamp": capa.processed_at.isoformat()
            }
            
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=feedback_message)
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "capa_generated",
                "recommendation_id": capa.recommendation_id,
                "component_id": capa.component_id,
                "vehicle_model": capa.vehicle_model,
                "failure_count": capa.failure_count,
                "trend": capa.trend,
                "timestamp": datetime.now().isoformat()
            })
            
            self.capa_generated += 1
            
            logger.info(
                f"🏭 CAPA Generated: {capa.recommendation_id} | "
                f"Component: {capa.component_id} | "
                f"Model: {capa.vehicle_model} | "
                f"Failures: {capa.failure_count} | "
                f"Trend: {capa.trend} ({capa.estimated_impact['trend_percentage']:.1f}%) | "
                f"Priority: {capa.priority} | "
                f"Cost: ${capa.estimated_impact['total_estimated_cost']:,}"
            )
    
    async def log_activity(self, activity: Dict):
        """Log activity"""
        try:
            await self.activity_producer.send(KAFKA_ACTIVITY_TOPIC, value=activity)
        except Exception as e:
            logger.warning(f"⚠️ Failed to log: {e}")
    
    async def send_heartbeat(self):
        """Send heartbeat"""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            try:
                await self.db.agent_status.update_one(
                    {"agent_id": AGENT_ID},
                    {"$set": {
                        "status": "active",
                        "last_heartbeat": datetime.now(),
                        "messages_processed": self.messages_processed,
                        "errors_count": self.errors_count,
                        "metadata.patterns_detected": self.patterns_detected,
                        "metadata.capa_generated": self.capa_generated,
                        "metadata.realtime_buffer_size": len(self.realtime_failure_buffer),
                        "metadata.historical_cache_size": len(self.historical_failures_cache),
                        "metadata.last_historical_refresh": self.last_historical_refresh.isoformat() if self.last_historical_refresh else None
                    }}
                )
                
                if self.messages_processed % 50 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Patterns: {self.patterns_detected} | "
                        f"CAPA: {self.capa_generated} | "
                        f"Realtime: {len(self.realtime_failure_buffer)} | "
                        f"Historical: {len(self.historical_failures_cache)}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down Manufacturing Agent Phase 5...")
        self.running = False
        
        if self.db:
            await self.db.agent_status.update_one(
                {"agent_id": AGENT_ID},
                {"$set": {"status": "stopped"}}
            )
        
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        if self.activity_producer:
            await self.activity_producer.stop()
        
        if self.mongo_client:
            self.mongo_client.close()
        
        logger.info("✅ Manufacturing Agent Phase 5 shut down")
        logger.info(f"📊 Final: {self.patterns_detected} patterns, {self.capa_generated} CAPA recommendations")

async def main():
    agent = ManufacturingAgentPhase5()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
