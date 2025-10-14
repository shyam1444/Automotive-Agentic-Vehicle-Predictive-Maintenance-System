"""
Customer Agent - Phase 4
=========================
Sends notifications to customers via SMS/Email/WhatsApp
"""

import os
import asyncio
import signal
import json
from datetime import datetime
from typing import Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# Configuration
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPICS = ['diagnostic_results', 'vehicle_alerts']
KAFKA_OUTPUT_TOPIC = 'customer_ack'
KAFKA_ACTIVITY_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'customer_agent'

MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

AGENT_ID = 'CUSTOMER_001'
HEARTBEAT_INTERVAL = 30

# Notification Templates
TEMPLATES = {
    "critical": """
🚨 CRITICAL ALERT - Immediate Action Required

Vehicle: {vehicle_id}
Issue: {primary_issue}
Details: {details}

⚠️ Recommended Action: {action}
⏰ Estimated Repair Time: {repair_time}

Please contact service immediately or visit your nearest service center.
    """,
    "warning": """
⚠️ WARNING - Service Recommended

Vehicle: {vehicle_id}
Issue: {primary_issue}
Details: {details}

📋 Recommended: {action}
⏰ Schedule service within: {repair_time}

Contact us to schedule maintenance.
    """,
    "info": """
ℹ️ MAINTENANCE NOTIFICATION

Vehicle: {vehicle_id}
Status: {details}

📋 Recommendation: {action}

Schedule routine maintenance at your convenience.
    """
}

class NotificationService:
    """Handles multiple notification channels"""
    
    @staticmethod
    async def send_sms(phone: str, message: str) -> bool:
        """Send SMS notification (mock implementation)"""
        logger.info(f"📱 SMS to {phone}: {message[:50]}...")
        # In production: integrate with Twilio, AWS SNS, etc.
        await asyncio.sleep(0.1)  # Simulate API call
        return True
    
    @staticmethod
    async def send_email(email: str, subject: str, message: str) -> bool:
        """Send email notification (mock implementation)"""
        logger.info(f"📧 Email to {email}: {subject}")
        # In production: integrate with SendGrid, AWS SES, etc.
        await asyncio.sleep(0.1)
        return True
    
    @staticmethod
    async def send_whatsapp(phone: str, message: str) -> bool:
        """Send WhatsApp notification (mock implementation)"""
        logger.info(f"💬 WhatsApp to {phone}: {message[:50]}...")
        # In production: integrate with Twilio WhatsApp API
        await asyncio.sleep(0.1)
        return True

class CustomerAgent:
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.notifications_sent = 0
        self.errors_count = 0
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.activity_producer: Optional[AIOKafkaProducer] = None
        
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        self.notification_service = NotificationService()
        
        logger.add(
            "logs/customer_agent_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start Customer Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("👤 CUSTOMER AGENT STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.init_kafka()
        await self.register_agent()
        
        asyncio.create_task(self.send_heartbeat())
        
        logger.info("✅ Customer Agent started")
        logger.info(f"📥 Consuming from: {', '.join(KAFKA_INPUT_TOPICS)}")
        
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
                "agent_type": "customer",
                "status": "active",
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {"started_at": datetime.now().isoformat()}
            }},
            upsert=True
        )
        logger.info(f"📝 Registered: {AGENT_ID}")
    
    async def process_alert(self, topic: str, alert: Dict):
        """Process alert and send notification"""
        try:
            vehicle_id = alert.get('vehicle_id')
            
            # Get customer info
            customer = await self.db.customer_info.find_one({"vehicle_id": vehicle_id})
            
            if not customer:
                logger.warning(f"⚠️ No customer found for {vehicle_id}")
                # Create default customer for testing
                customer = {
                    "customer_id": f"CUST_{vehicle_id}",
                    "vehicle_id": vehicle_id,
                    "customer_name": f"Owner of {vehicle_id}",
                    "contact_info": {
                        "phone": "+1234567890",
                        "email": f"{vehicle_id.lower()}@example.com"
                    },
                    "preferred_contact_method": "email",
                    "notification_enabled": True
                }
                await self.db.customer_info.insert_one(customer)
            
            if not customer.get('notification_enabled', True):
                logger.info(f"ℹ️ Notifications disabled for {vehicle_id}")
                return
            
            # Generate notification message
            severity = alert.get('severity', 'info')
            message = self.generate_message(alert, severity)
            
            # Send notification based on preference
            contact_method = customer.get('preferred_contact_method', 'email')
            contact_info = customer.get('contact_info', {})
            
            success = False
            if contact_method == 'sms' and contact_info.get('phone'):
                success = await self.notification_service.send_sms(
                    contact_info['phone'],
                    message
                )
            elif contact_method == 'whatsapp' and contact_info.get('whatsapp'):
                success = await self.notification_service.send_whatsapp(
                    contact_info['whatsapp'],
                    message
                )
            elif contact_info.get('email'):
                success = await self.notification_service.send_email(
                    contact_info['email'],
                    f"Vehicle Alert: {vehicle_id}",
                    message
                )
            
            if success:
                self.notifications_sent += 1
                
                # Publish acknowledgment
                await self.producer.send(KAFKA_OUTPUT_TOPIC, value={
                    "vehicle_id": vehicle_id,
                    "customer_id": customer.get('customer_id'),
                    "type": "notification_sent",
                    "method": contact_method,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Update alert history
                await self.db.alerts_history.update_one(
                    {"vehicle_id": vehicle_id, "resolution_status": "pending"},
                    {"$set": {"customer_notified": True}},
                    upsert=False
                )
                
                logger.info(f"✅ Notified customer for {vehicle_id} via {contact_method}")
            
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "notification_sent",
                "vehicle_id": vehicle_id,
                "method": contact_method,
                "success": success,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to process alert: {e}")
            self.errors_count += 1
    
    def generate_message(self, alert: Dict, severity: str) -> str:
        """Generate notification message from template"""
        template = TEMPLATES.get(severity, TEMPLATES['info'])
        
        # Extract details based on source
        if 'root_causes' in alert:  # From diagnostics
            primary_issue = alert.get('primary_component', 'Unknown issue')
            details = ', '.join([rc.get('issue', '') for rc in alert.get('root_causes', [])[:2]])
            action = alert.get('recommended_actions', ['Contact service'])[0]
            repair_time = alert.get('estimated_repair_time', '24 hours')
        else:  # From predictions
            primary_issue = alert.get('health_status', 'Status update')
            details = alert.get('reason', 'Sensor anomalies detected')
            action = "Schedule inspection"
            repair_time = "24-48 hours"
        
        message = template.format(
            vehicle_id=alert.get('vehicle_id', 'Unknown'),
            primary_issue=primary_issue,
            details=details,
            action=action,
            repair_time=repair_time
        )
        
        return message.strip()
    
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
                        "errors_count": self.errors_count
                    }}
                )
                
                if self.messages_processed % 10 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Sent: {self.notifications_sent} | Errors: {self.errors_count}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down Customer Agent...")
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
        
        logger.info("✅ Customer Agent shut down")
        logger.info(f"📊 Final: Sent {self.notifications_sent} notifications")

async def main():
    agent = CustomerAgent()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
