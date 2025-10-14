"""
Manufacturing Agent - Phase 4
==============================
Aggregates failures, detects patterns, and provides CAPA insights
"""

import os
import asyncio
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass
import uuid

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPICS = ['diagnostic_results', 'vehicle_alerts']
KAFKA_OUTPUT_TOPIC = 'manufacturing_feedback'
KAFKA_ACTIVITY_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'manufacturing_agent'

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

AGENT_ID = 'MANUFACTURING_001'
HEARTBEAT_INTERVAL = 30

# Analysis window (aggregate data over this period)
ANALYSIS_WINDOW = timedelta(hours=24)

# Thresholds for pattern detection
MIN_FAILURE_COUNT = 5  # Minimum failures to trigger CAPA
PATTERN_SIMILARITY_THRESHOLD = 0.7  # 70% similarity to group patterns

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class FailurePattern:
    pattern_id: str
    component: str
    failure_type: str
    occurrences: int
    affected_vehicles: List[str]
    severity_distribution: Dict[str, int]
    first_seen: datetime
    last_seen: datetime
    avg_confidence: float

@dataclass
class CAPARecommendation:
    recommendation_id: str
    pattern_id: str
    component: str
    failure_count: int
    severity: str
    root_cause_analysis: str
    corrective_action: str
    preventive_action: str
    priority: int
    estimated_impact: Dict[str, any]
    created_at: datetime

# ============================================================================
# PATTERN DETECTION ENGINE
# ============================================================================

class PatternDetectionEngine:
    """Detects recurring failure patterns across fleet"""
    
    def __init__(self):
        self.patterns = defaultdict(list)
    
    def analyze_failures(self, failures: List[Dict]) -> List[FailurePattern]:
        """Analyze failures and detect patterns"""
        
        # Group by component
        component_failures = defaultdict(list)
        for failure in failures:
            for root_cause in failure.get('root_causes', []):
                component = root_cause.get('component', 'Unknown')
                component_failures[component].append({
                    'vehicle_id': failure.get('vehicle_id'),
                    'issue': root_cause.get('issue'),
                    'likelihood': root_cause.get('likelihood', 0.5),
                    'severity': failure.get('severity', 'info'),
                    'timestamp': failure.get('timestamp')
                })
        
        patterns = []
        
        # Detect patterns for each component
        for component, comp_failures in component_failures.items():
            if len(comp_failures) < MIN_FAILURE_COUNT:
                continue
            
            # Group by issue type
            issue_groups = defaultdict(list)
            for failure in comp_failures:
                issue_groups[failure['issue']].append(failure)
            
            # Create pattern for each issue type with sufficient occurrences
            for issue_type, issue_failures in issue_groups.items():
                if len(issue_failures) >= MIN_FAILURE_COUNT:
                    pattern = self._create_pattern(component, issue_type, issue_failures)
                    patterns.append(pattern)
        
        return patterns
    
    def _create_pattern(self, component: str, issue_type: str, failures: List[Dict]) -> FailurePattern:
        """Create failure pattern"""
        
        # Sort by timestamp
        sorted_failures = sorted(failures, key=lambda x: x.get('timestamp', ''))
        
        # Count severity distribution
        severity_counts = Counter([f.get('severity', 'info') for f in failures])
        
        # Calculate average confidence
        avg_confidence = sum(f.get('likelihood', 0.5) for f in failures) / len(failures)
        
        return FailurePattern(
            pattern_id=f"PATTERN_{uuid.uuid4().hex[:8].upper()}",
            component=component,
            failure_type=issue_type,
            occurrences=len(failures),
            affected_vehicles=[f['vehicle_id'] for f in failures],
            severity_distribution=dict(severity_counts),
            first_seen=datetime.fromisoformat(sorted_failures[0]['timestamp']) if sorted_failures[0].get('timestamp') else datetime.now(),
            last_seen=datetime.fromisoformat(sorted_failures[-1]['timestamp']) if sorted_failures[-1].get('timestamp') else datetime.now(),
            avg_confidence=avg_confidence
        )

# ============================================================================
# CAPA RECOMMENDATION ENGINE
# ============================================================================

class CAPAEngine:
    """Generates Corrective and Preventive Action recommendations"""
    
    # CAPA knowledge base (maps component + failure type to actions)
    CAPA_KNOWLEDGE_BASE = {
        "Cooling System": {
            "Overheating": {
                "corrective": "Replace coolant, inspect radiator for blockages, check water pump",
                "preventive": "Implement regular coolant quality checks at assembly. Add thermal stress testing to QC.",
                "assembly_step": "Cooling System Assembly (Step 7)"
            },
            "Coolant Leak": {
                "corrective": "Replace hoses and seals, check radiator integrity",
                "preventive": "Switch to higher-grade seals. Add pressure testing to production line.",
                "assembly_step": "Seal Installation (Step 6)"
            }
        },
        "Engine": {
            "Over-revving": {
                "corrective": "ECU recalibration, check throttle position sensor",
                "preventive": "Update ECU software with RPM limiter. Add throttle sensor calibration check.",
                "assembly_step": "Engine Control Module (Step 12)"
            },
            "Vibration": {
                "corrective": "Engine mount replacement, balance crankshaft",
                "preventive": "Add vibration testing to engine assembly. Use higher-grade engine mounts.",
                "assembly_step": "Engine Mounting (Step 10)"
            }
        },
        "Battery": {
            "Low Voltage": {
                "corrective": "Replace battery, check alternator output",
                "preventive": "Switch battery supplier. Add load testing to pre-delivery inspection.",
                "assembly_step": "Electrical System (Step 15)"
            }
        },
        "Fuel System": {
            "Low Fuel": {
                "corrective": "N/A (operational issue)",
                "preventive": "Add fuel level monitoring to telematics. Send proactive alerts at 15%.",
                "assembly_step": "N/A"
            }
        }
    }
    
    def generate_capa(self, pattern: FailurePattern) -> CAPARecommendation:
        """Generate CAPA recommendation"""
        
        component = pattern.component
        failure_type = pattern.failure_type
        
        # Lookup CAPA actions
        capa_actions = self.CAPA_KNOWLEDGE_BASE.get(component, {}).get(failure_type, {
            "corrective": f"Investigate {component} - {failure_type}. Perform root cause analysis.",
            "preventive": f"Monitor {component} failure rates. Consider design review.",
            "assembly_step": "Unknown"
        })
        
        # Determine severity and priority
        severity_dist = pattern.severity_distribution
        if severity_dist.get('critical', 0) > 0:
            severity = 'critical'
            priority = 1
        elif severity_dist.get('warning', 0) >= pattern.occurrences * 0.5:
            severity = 'warning'
            priority = 2
        else:
            severity = 'info'
            priority = 3
        
        # Estimate impact
        estimated_impact = {
            "affected_vehicles_count": len(pattern.affected_vehicles),
            "potential_recalls": len(pattern.affected_vehicles) if severity == 'critical' else 0,
            "estimated_cost_per_fix": self._estimate_cost(component, severity),
            "total_estimated_cost": len(pattern.affected_vehicles) * self._estimate_cost(component, severity),
            "production_line_impact": capa_actions.get('assembly_step', 'Unknown')
        }
        
        return CAPARecommendation(
            recommendation_id=f"CAPA_{uuid.uuid4().hex[:8].upper()}",
            pattern_id=pattern.pattern_id,
            component=component,
            failure_count=pattern.occurrences,
            severity=severity,
            root_cause_analysis=f"{failure_type} detected in {component} across {len(pattern.affected_vehicles)} vehicles. "
                                f"Average confidence: {pattern.avg_confidence:.2f}. "
                                f"First detected: {pattern.first_seen.strftime('%Y-%m-%d')}.",
            corrective_action=capa_actions.get('corrective', 'N/A'),
            preventive_action=capa_actions.get('preventive', 'N/A'),
            priority=priority,
            estimated_impact=estimated_impact,
            created_at=datetime.now()
        )
    
    def _estimate_cost(self, component: str, severity: str) -> int:
        """Estimate repair cost (USD)"""
        base_costs = {
            "Cooling System": 500,
            "Engine": 2000,
            "Battery": 200,
            "Fuel System": 300
        }
        
        severity_multipliers = {
            "critical": 2.0,
            "warning": 1.5,
            "info": 1.0
        }
        
        base_cost = base_costs.get(component, 400)
        multiplier = severity_multipliers.get(severity, 1.0)
        
        return int(base_cost * multiplier)

# ============================================================================
# MANUFACTURING AGENT
# ============================================================================

class ManufacturingAgent:
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
        
        self.pattern_engine = PatternDetectionEngine()
        self.capa_engine = CAPAEngine()
        
        # Buffer for recent failures
        self.failure_buffer = []
        
        logger.add(
            "logs/manufacturing_agent_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start Manufacturing Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🏭 MANUFACTURING AGENT STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.init_kafka()
        await self.register_agent()
        
        asyncio.create_task(self.send_heartbeat())
        asyncio.create_task(self.periodic_analysis())
        
        logger.info("✅ Manufacturing Agent started")
        logger.info(f"📥 Consuming from: {', '.join(KAFKA_INPUT_TOPICS)}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        logger.info(f"🔍 Analysis window: {ANALYSIS_WINDOW.total_seconds() / 3600:.0f} hours")
        
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
                "agent_type": "manufacturing",
                "status": "active",
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {
                    "started_at": datetime.now().isoformat(),
                    "analysis_window_hours": ANALYSIS_WINDOW.total_seconds() / 3600
                }
            }},
            upsert=True
        )
        logger.info(f"📝 Registered: {AGENT_ID}")
    
    async def process_diagnostic(self, diagnostic: Dict):
        """Add diagnostic to buffer"""
        try:
            # Add timestamp if missing
            if 'timestamp' not in diagnostic:
                diagnostic['timestamp'] = datetime.now().isoformat()
            
            self.failure_buffer.append(diagnostic)
            
            # Keep buffer size manageable
            if len(self.failure_buffer) > 1000:
                self.failure_buffer = self.failure_buffer[-1000:]
            
        except Exception as e:
            logger.error(f"❌ Failed to process diagnostic: {e}")
            self.errors_count += 1
    
    async def periodic_analysis(self):
        """Periodically analyze patterns and generate CAPA"""
        while self.running:
            await asyncio.sleep(300)  # Every 5 minutes
            
            try:
                await self.analyze_and_generate_capa()
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}", exc_info=True)
    
    async def analyze_and_generate_capa(self):
        """Analyze patterns and generate CAPA recommendations"""
        
        if len(self.failure_buffer) < MIN_FAILURE_COUNT:
            logger.debug(f"⏭️ Insufficient data: {len(self.failure_buffer)} failures")
            return
        
        logger.info(f"🔍 Analyzing {len(self.failure_buffer)} failures...")
        
        # Filter recent failures within analysis window
        cutoff_time = datetime.now() - ANALYSIS_WINDOW
        recent_failures = [
            f for f in self.failure_buffer
            if datetime.fromisoformat(f.get('timestamp', '1970-01-01')) >= cutoff_time
        ]
        
        if len(recent_failures) < MIN_FAILURE_COUNT:
            logger.debug(f"⏭️ Insufficient recent data: {len(recent_failures)} failures")
            return
        
        # Detect patterns
        patterns = self.pattern_engine.analyze_failures(recent_failures)
        
        if not patterns:
            logger.debug("⏭️ No significant patterns detected")
            return
        
        logger.info(f"✅ Detected {len(patterns)} failure patterns")
        self.patterns_detected += len(patterns)
        
        # Generate CAPA for each pattern
        for pattern in patterns:
            capa = self.capa_engine.generate_capa(pattern)
            
            # Store in MongoDB
            capa_doc = {
                "recommendation_id": capa.recommendation_id,
                "pattern_id": capa.pattern_id,
                "component": capa.component,
                "failure_count": capa.failure_count,
                "severity": capa.severity,
                "root_cause_analysis": capa.root_cause_analysis,
                "corrective_action": capa.corrective_action,
                "preventive_action": capa.preventive_action,
                "priority": capa.priority,
                "estimated_impact": capa.estimated_impact,
                "affected_vehicles": pattern.affected_vehicles,
                "created_at": capa.created_at,
                "status": "pending"
            }
            
            await self.db.manufacturing_reports.insert_one(capa_doc)
            
            # Publish to Kafka
            feedback_message = {
                "recommendation_id": capa.recommendation_id,
                "component": capa.component,
                "failure_count": capa.failure_count,
                "severity": capa.severity,
                "corrective_action": capa.corrective_action,
                "preventive_action": capa.preventive_action,
                "priority": capa.priority,
                "estimated_impact": capa.estimated_impact,
                "timestamp": capa.created_at.isoformat()
            }
            
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=feedback_message)
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "capa_generated",
                "recommendation_id": capa.recommendation_id,
                "component": capa.component,
                "failure_count": capa.failure_count,
                "affected_vehicles": len(pattern.affected_vehicles),
                "timestamp": datetime.now().isoformat()
            })
            
            self.capa_generated += 1
            
            logger.info(
                f"🏭 CAPA Generated: {capa.recommendation_id} | "
                f"Component: {capa.component} | "
                f"Failures: {capa.failure_count} | "
                f"Vehicles: {len(pattern.affected_vehicles)} | "
                f"Priority: {capa.priority} | "
                f"Est. Cost: ${capa.estimated_impact['total_estimated_cost']:,}"
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
                        "metadata.buffer_size": len(self.failure_buffer)
                    }}
                )
                
                if self.messages_processed % 50 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Patterns: {self.patterns_detected} | "
                        f"CAPA: {self.capa_generated} | "
                        f"Buffer: {len(self.failure_buffer)}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down Manufacturing Agent...")
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
        
        logger.info("✅ Manufacturing Agent shut down")
        logger.info(f"📊 Final: {self.patterns_detected} patterns, {self.capa_generated} CAPA recommendations")

async def main():
    agent = ManufacturingAgent()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
