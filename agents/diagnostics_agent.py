"""
Diagnostics Agent - Phase 4
============================
Performs root cause analysis on vehicle predictions and enriches alerts
"""

import os
import asyncio
import signal
import json
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPIC = 'vehicle_predictions'
KAFKA_OUTPUT_TOPIC = 'diagnostic_results'
KAFKA_ACTIVITY_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'diagnostics_agent'

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

AGENT_ID = 'DIAGNOSTICS_001'
HEARTBEAT_INTERVAL = 30

# ============================================================================
# RCA RULES ENGINE
# ============================================================================

class RCAEngine:
    """Root Cause Analysis Engine"""
    
    @staticmethod
    def analyze(prediction: Dict) -> Dict:
        """Perform root cause analysis based on sensor data"""
        vehicle_id = prediction.get('vehicle_id')
        failure_prob = prediction.get('failure_probability', 0)
        metrics = prediction.get('metrics', {})
        
        # Extract metrics
        engine_temp = metrics.get('engine_temp', 0)
        vibration = metrics.get('vibration', 0)
        engine_rpm = metrics.get('engine_rpm', 0)
        battery_voltage = metrics.get('battery_voltage', 0)
        fuel_level = metrics.get('fuel_level', 0)
        speed = metrics.get('speed', 0)
        
        root_causes = []
        severity = "info"
        recommended_actions = []
        estimated_time = "72 hours"
        
        # Engine Temperature Analysis
        if engine_temp > 120:
            root_causes.append({
                "component": "Cooling System",
                "issue": "Critical Overheating",
                "detail": f"Engine temperature at {engine_temp:.1f}°C (normal: 80-95°C)",
                "likelihood": 0.95
            })
            recommended_actions.append("Immediate coolant system inspection")
            recommended_actions.append("Check radiator and water pump")
            severity = "critical"
            estimated_time = "4 hours"
            
        elif engine_temp > 100:
            root_causes.append({
                "component": "Cooling System",
                "issue": "Elevated Temperature",
                "detail": f"Engine temperature at {engine_temp:.1f}°C (warning threshold)",
                "likelihood": 0.75
            })
            recommended_actions.append("Schedule coolant system check")
            severity = "warning" if severity != "critical" else severity
            estimated_time = "24 hours"
        
        # Vibration Analysis
        if vibration > 8.0:
            root_causes.append({
                "component": "Engine Mounts / Balance",
                "issue": "Severe Vibration",
                "detail": f"Vibration level at {vibration:.1f} (normal: <2.5)",
                "likelihood": 0.90
            })
            recommended_actions.append("Inspect engine mounts and suspension")
            recommended_actions.append("Check wheel balance and alignment")
            severity = "critical"
            estimated_time = "4 hours"
            
        elif vibration > 3.0:
            root_causes.append({
                "component": "Engine Mounts",
                "issue": "Excessive Vibration",
                "detail": f"Vibration at {vibration:.1f} (elevated)",
                "likelihood": 0.65
            })
            recommended_actions.append("Check engine mounts")
            severity = "warning" if severity == "info" else severity
        
        # RPM Analysis
        if engine_rpm > 6000:
            root_causes.append({
                "component": "Engine / Transmission",
                "issue": "Over-revving",
                "detail": f"Engine RPM at {engine_rpm} (red line exceeded)",
                "likelihood": 0.85
            })
            recommended_actions.append("Inspect engine for damage")
            recommended_actions.append("Check transmission")
            severity = "critical"
            
        elif engine_rpm < 500 and speed > 10:
            root_causes.append({
                "component": "Engine / Fuel System",
                "issue": "Engine Stalling",
                "detail": f"Low RPM ({engine_rpm}) while vehicle moving",
                "likelihood": 0.80
            })
            recommended_actions.append("Check fuel system and filters")
            recommended_actions.append("Inspect ignition system")
            severity = "critical"
        
        # Battery Analysis
        if battery_voltage < 10.0:
            root_causes.append({
                "component": "Electrical System",
                "issue": "Critical Battery Voltage",
                "detail": f"Battery at {battery_voltage:.1f}V (normal: 12.6-14.4V)",
                "likelihood": 0.90
            })
            recommended_actions.append("Replace battery immediately")
            recommended_actions.append("Check alternator output")
            severity = "critical"
            estimated_time = "2 hours"
            
        elif battery_voltage < 11.5:
            root_causes.append({
                "component": "Electrical System",
                "issue": "Low Battery Voltage",
                "detail": f"Battery at {battery_voltage:.1f}V (warning)",
                "likelihood": 0.70
            })
            recommended_actions.append("Test battery and charging system")
            severity = "warning" if severity == "info" else severity
        
        # Fuel Level Analysis
        if fuel_level < 5:
            root_causes.append({
                "component": "Fuel System",
                "issue": "Critical Fuel Level",
                "detail": f"Fuel at {fuel_level:.1f}% (immediate refuel needed)",
                "likelihood": 1.0
            })
            recommended_actions.append("Refuel immediately")
            if severity == "info":
                severity = "warning"
        
        # Multi-factor Analysis
        if len(root_causes) >= 3:
            root_causes.append({
                "component": "Multiple Systems",
                "issue": "Multiple Failure Points",
                "detail": f"{len(root_causes)} simultaneous issues detected",
                "likelihood": 0.95
            })
            recommended_actions.append("Comprehensive multi-point inspection required")
            severity = "critical"
            estimated_time = "8 hours"
        
        # Default if no specific issues found
        if not root_causes:
            root_causes.append({
                "component": "Predictive Model",
                "issue": "Elevated Risk Score",
                "detail": f"ML model detected anomalous patterns (probability: {failure_prob:.2f})",
                "likelihood": failure_prob
            })
            recommended_actions.append("Routine inspection recommended")
            severity = "info"
        
        # Generate diagnostic result
        result = {
            "vehicle_id": vehicle_id,
            "diagnostic_id": f"DIAG_{vehicle_id}_{datetime.now().timestamp()}",
            "timestamp": datetime.now().isoformat(),
            "failure_probability": failure_prob,
            "severity": severity,
            "root_causes": root_causes,
            "primary_component": root_causes[0]["component"] if root_causes else "Unknown",
            "recommended_actions": recommended_actions,
            "estimated_repair_time": estimated_time,
            "requires_immediate_attention": severity == "critical",
            "analyzed_by": AGENT_ID,
            "confidence_score": sum(rc["likelihood"] for rc in root_causes) / len(root_causes) if root_causes else 0
        }
        
        return result

# ============================================================================
# DIAGNOSTICS AGENT
# ============================================================================

class DiagnosticsAgent:
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.errors_count = 0
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.activity_producer: Optional[AIOKafkaProducer] = None
        
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        self.rca_engine = RCAEngine()
        
        logger.add(
            "logs/diagnostics_agent_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start Diagnostics Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🔍 DIAGNOSTICS AGENT STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.init_kafka()
        await self.register_agent()
        
        asyncio.create_task(self.send_heartbeat())
        
        logger.info("✅ Diagnostics Agent started")
        logger.info(f"📥 Consuming from: {KAFKA_INPUT_TOPIC}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_prediction(message.value)
                self.messages_processed += 1
        
        except Exception as e:
            logger.error(f"❌ Error in consumption loop: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def connect_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = AsyncIOMotorClient(MONGODB_URI)
            self.db = self.mongo_client[MONGODB_DATABASE]
            await self.mongo_client.admin.command('ping')
            logger.info("✅ Connected to MongoDB")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    async def init_kafka(self):
        """Initialize Kafka connections"""
        self.consumer = AIOKafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset='latest',
            enable_auto_commit=True,
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
        """Register agent in MongoDB"""
        try:
            await self.db.agent_status.update_one(
                {"agent_id": AGENT_ID},
                {"$set": {
                    "agent_id": AGENT_ID,
                    "agent_type": "diagnostics",
                    "status": "active",
                    "last_heartbeat": datetime.now(),
                    "messages_processed": 0,
                    "errors_count": 0,
                    "metadata": {
                        "started_at": datetime.now().isoformat(),
                        "input_topic": KAFKA_INPUT_TOPIC,
                        "output_topic": KAFKA_OUTPUT_TOPIC
                    }
                }},
                upsert=True
            )
            logger.info(f"📝 Registered agent: {AGENT_ID}")
        except Exception as e:
            logger.error(f"❌ Failed to register agent: {e}")
    
    async def process_prediction(self, prediction: Dict):
        """Process prediction and perform RCA"""
        try:
            vehicle_id = prediction.get('vehicle_id')
            failure_prob = prediction.get('failure_probability', 0)
            
            logger.info(f"🔍 Analyzing: {vehicle_id} | Failure Prob: {failure_prob:.2f}")
            
            # Perform RCA
            diagnostic_result = self.rca_engine.analyze(prediction)
            
            # Publish result
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=diagnostic_result)
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "diagnosis_completed",
                "vehicle_id": vehicle_id,
                "severity": diagnostic_result["severity"],
                "root_causes_count": len(diagnostic_result["root_causes"]),
                "confidence": diagnostic_result["confidence_score"],
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(
                f"✅ Diagnosis: {vehicle_id} | "
                f"Severity: {diagnostic_result['severity']} | "
                f"Primary: {diagnostic_result['primary_component']}"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to process prediction: {e}")
            self.errors_count += 1
    
    async def log_activity(self, activity: Dict):
        """Log activity to Kafka"""
        try:
            await self.activity_producer.send(KAFKA_ACTIVITY_TOPIC, value=activity)
        except Exception as e:
            logger.warning(f"⚠️ Failed to log activity: {e}")
    
    async def send_heartbeat(self):
        """Send periodic heartbeat"""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            try:
                await self.db.agent_status.update_one(
                    {"agent_id": AGENT_ID},
                    {"$set": {
                        "status": "active",
                        "last_heartbeat": datetime.now(),
                        "messages_processed": self.messages_processed,
                        "errors_count": self.errors_count
                    }}
                )
                
                await self.log_activity({
                    "agent_id": AGENT_ID,
                    "action": "heartbeat",
                    "messages_processed": self.messages_processed,
                    "errors_count": self.errors_count,
                    "timestamp": datetime.now().isoformat()
                })
                
                if self.messages_processed % 10 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Errors: {self.errors_count}"
                    )
                
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Diagnostics Agent...")
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
        
        logger.info("✅ Diagnostics Agent shut down")
        logger.info(f"📊 Final: Processed {self.messages_processed} predictions")

async def main():
    agent = DiagnosticsAgent()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("⚠️ Received shutdown signal")
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
