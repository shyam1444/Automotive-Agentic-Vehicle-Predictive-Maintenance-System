"""
Scheduling Agent - Phase 4
===========================
Auto-books maintenance slots based on alert severity with priority queue
"""

import os
import asyncio
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
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
KAFKA_OUTPUT_TOPIC = 'customer_ack'
KAFKA_ACTIVITY_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'scheduling_agent'

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

AGENT_ID = 'SCHEDULING_001'
HEARTBEAT_INTERVAL = 30

# Service Centers (mock data)
SERVICE_CENTERS = [
    {"id": "CENTER_A", "name": "Downtown Service", "capacity_per_day": 20},
    {"id": "CENTER_B", "name": "North Branch", "capacity_per_day": 15},
    {"id": "CENTER_C", "name": "South Station", "capacity_per_day": 25}
]

# Scheduling priorities
PRIORITY_MAP = {
    "critical": 1,  # Immediate (4 hours)
    "warning": 2,   # 24 hours
    "info": 3       # 72 hours
}

# ============================================================================
# DATA MODELS
# ============================================================================

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

@dataclass
class MaintenanceSlot:
    booking_id: str
    vehicle_id: str
    customer_id: str
    scheduled_date: datetime
    service_center: str
    severity: str
    status: BookingStatus
    service_type: str
    diagnostic_result_id: Optional[str]
    estimated_duration: int  # minutes
    notes: str

# ============================================================================
# SCHEDULING ENGINE
# ============================================================================

class SchedulingEngine:
    """Intelligent scheduling engine with priority queue"""
    
    def __init__(self, db):
        self.db = db
    
    async def find_available_slot(self, severity: str, vehicle_id: str) -> Dict:
        """Find next available slot based on severity"""
        
        # Calculate target date based on severity
        now = datetime.now()
        if severity == "critical":
            target_date = now + timedelta(hours=4)
            search_window = timedelta(hours=12)
        elif severity == "warning":
            target_date = now + timedelta(hours=24)
            search_window = timedelta(days=3)
        else:
            target_date = now + timedelta(days=3)
            search_window = timedelta(days=7)
        
        # Search for available slots
        end_date = target_date + search_window
        current_date = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        
        while current_date < end_date:
            # Skip weekends (for simulation)
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Check capacity for each service center
            for center in SERVICE_CENTERS:
                # Count existing bookings for this center/date
                bookings_count = await self.db.service_schedule.count_documents({
                    "service_center": center["id"],
                    "scheduled_date": {
                        "$gte": current_date,
                        "$lt": current_date + timedelta(days=1)
                    },
                    "status": {"$in": ["pending", "confirmed"]}
                })
                
                if bookings_count < center["capacity_per_day"]:
                    # Found available slot
                    return {
                        "scheduled_date": current_date + timedelta(hours=bookings_count % 8),
                        "service_center": center["id"],
                        "service_center_name": center["name"]
                    }
            
            # Try next day
            current_date += timedelta(days=1)
        
        # Fallback: force schedule at earliest possible time
        logger.warning(f"No slots available in window, forcing schedule for {vehicle_id}")
        return {
            "scheduled_date": target_date,
            "service_center": SERVICE_CENTERS[0]["id"],
            "service_center_name": SERVICE_CENTERS[0]["name"]
        }
    
    async def book_slot(self, alert: Dict, diagnostic_result: Optional[Dict] = None) -> MaintenanceSlot:
        """Book maintenance slot"""
        
        vehicle_id = alert.get('vehicle_id')
        severity = alert.get('severity', 'info').lower()
        
        # Find customer
        customer = await self.db.customer_info.find_one({"vehicle_id": vehicle_id})
        if not customer:
            customer = {
                "customer_id": f"CUST_{vehicle_id}",
                "vehicle_id": vehicle_id
            }
        
        # Find available slot
        slot_info = await self.find_available_slot(severity, vehicle_id)
        
        # Determine service type and duration
        if diagnostic_result:
            service_type = diagnostic_result.get('primary_component', 'General Inspection')
            estimated_duration = self._estimate_duration(diagnostic_result)
            notes = diagnostic_result.get('reason', '')
        else:
            service_type = "Predictive Maintenance"
            estimated_duration = 120
            notes = alert.get('reason', 'Routine inspection')
        
        # Create booking
        booking = MaintenanceSlot(
            booking_id=f"BOOK_{uuid.uuid4().hex[:8].upper()}",
            vehicle_id=vehicle_id,
            customer_id=customer.get('customer_id'),
            scheduled_date=slot_info['scheduled_date'],
            service_center=slot_info['service_center'],
            severity=severity,
            status=BookingStatus.CONFIRMED,
            service_type=service_type,
            diagnostic_result_id=diagnostic_result.get('diagnostic_id') if diagnostic_result else None,
            estimated_duration=estimated_duration,
            notes=notes
        )
        
        return booking
    
    def _estimate_duration(self, diagnostic_result: Dict) -> int:
        """Estimate repair duration based on diagnostic results"""
        severity = diagnostic_result.get('severity', 'info')
        root_causes_count = len(diagnostic_result.get('root_causes', []))
        
        # Base duration by severity
        base_duration = {
            'critical': 240,  # 4 hours
            'warning': 120,   # 2 hours
            'info': 60        # 1 hour
        }.get(severity, 120)
        
        # Add time for multiple issues
        additional_time = (root_causes_count - 1) * 30 if root_causes_count > 1 else 0
        
        return min(base_duration + additional_time, 480)  # Max 8 hours

# ============================================================================
# SCHEDULING AGENT
# ============================================================================

class SchedulingAgent:
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.bookings_made = 0
        self.errors_count = 0
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.activity_producer: Optional[AIOKafkaProducer] = None
        
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        self.scheduling_engine = None
        
        logger.add(
            "logs/scheduling_agent_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start Scheduling Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("📅 SCHEDULING AGENT STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.init_kafka()
        await self.register_agent()
        
        self.scheduling_engine = SchedulingEngine(self.db)
        
        asyncio.create_task(self.send_heartbeat())
        
        logger.info("✅ Scheduling Agent started")
        logger.info(f"📥 Consuming from: {', '.join(KAFKA_INPUT_TOPICS)}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_alert(message.topic, message.value)
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
                "agent_type": "scheduling",
                "status": "active",
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {
                    "started_at": datetime.now().isoformat(),
                    "service_centers": len(SERVICE_CENTERS)
                }
            }},
            upsert=True
        )
        logger.info(f"📝 Registered: {AGENT_ID}")
    
    async def process_alert(self, topic: str, alert: Dict):
        """Process alert and schedule maintenance"""
        try:
            vehicle_id = alert.get('vehicle_id')
            severity = alert.get('severity', 'info').lower()
            
            # Check if already scheduled
            existing = await self.db.service_schedule.find_one({
                "vehicle_id": vehicle_id,
                "status": {"$in": ["pending", "confirmed"]},
                "scheduled_date": {"$gte": datetime.now()}
            })
            
            if existing:
                logger.info(f"ℹ️ {vehicle_id} already has pending booking: {existing['booking_id']}")
                return
            
            # Only schedule for warning/critical
            if severity not in ['warning', 'critical']:
                logger.debug(f"⏭️ Skipping {vehicle_id} - severity: {severity}")
                return
            
            logger.info(f"📅 Scheduling: {vehicle_id} | Severity: {severity}")
            
            # Get diagnostic result if from that topic
            diagnostic_result = alert if topic == 'diagnostic_results' else None
            
            # Book slot
            booking = await self.scheduling_engine.book_slot(alert, diagnostic_result)
            
            # Store in MongoDB
            booking_doc = {
                "booking_id": booking.booking_id,
                "vehicle_id": booking.vehicle_id,
                "customer_id": booking.customer_id,
                "scheduled_date": booking.scheduled_date,
                "service_center": booking.service_center,
                "severity": booking.severity,
                "status": booking.status.value,
                "service_type": booking.service_type,
                "diagnostic_result_id": booking.diagnostic_result_id,
                "estimated_duration": booking.estimated_duration,
                "notes": booking.notes,
                "created_at": datetime.now()
            }
            
            await self.db.service_schedule.insert_one(booking_doc)
            
            # Update alerts history
            await self.db.alerts_history.update_one(
                {"vehicle_id": vehicle_id, "resolution_status": {"$in": ["pending", "acknowledged"]}},
                {"$set": {"service_scheduled": True, "resolution_status": "scheduled"}},
                upsert=False
            )
            
            # Publish acknowledgment
            ack_message = {
                "vehicle_id": vehicle_id,
                "booking_id": booking.booking_id,
                "type": "service_scheduled",
                "scheduled_date": booking.scheduled_date.isoformat(),
                "service_center": booking.service_center,
                "severity": severity,
                "acknowledged": True,
                "timestamp": datetime.now().isoformat()
            }
            
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=ack_message)
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "maintenance_scheduled",
                "vehicle_id": vehicle_id,
                "booking_id": booking.booking_id,
                "scheduled_date": booking.scheduled_date.isoformat(),
                "service_center": booking.service_center,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            })
            
            self.bookings_made += 1
            
            logger.info(
                f"✅ Scheduled: {vehicle_id} | "
                f"Date: {booking.scheduled_date.strftime('%Y-%m-%d %H:%M')} | "
                f"Center: {booking.service_center} | "
                f"Duration: {booking.estimated_duration}min"
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to schedule: {e}")
            self.errors_count += 1
    
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
                        "metadata.bookings_made": self.bookings_made
                    }}
                )
                
                if self.messages_processed % 10 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Booked: {self.bookings_made} | Errors: {self.errors_count}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down Scheduling Agent...")
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
        
        logger.info("✅ Scheduling Agent shut down")
        logger.info(f"📊 Final: Scheduled {self.bookings_made} appointments")

async def main():
    agent = SchedulingAgent()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
