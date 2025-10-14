"""
Master Agent - Phase 4 Multi-Agent Orchestration
=================================================
Orchestrates autonomous worker agents, monitors health, routes alerts
"""

import os
import asyncio
import signal
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from dotenv import load_dotenv

# Load environment
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Kafka
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPICS = ['vehicle_alerts', 'diagnostic_results', 'customer_ack']
KAFKA_OUTPUT_TOPIC = 'agent_activity_log'
KAFKA_GROUP_ID = 'master_agent'

# MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

# Agent configuration
HEARTBEAT_INTERVAL = 30  # seconds
AGENT_TIMEOUT = 120  # seconds - consider agent dead if no heartbeat
ROUTING_PRIORITIES = {
    'critical': ['diagnostics', 'customer', 'scheduling'],
    'warning': ['diagnostics', 'customer'],
    'info': ['manufacturing']
}

AGENT_ID = 'MASTER_001'

# ============================================================================
# DATA MODELS
# ============================================================================

class AgentType(str, Enum):
    MASTER = "master"
    DIAGNOSTICS = "diagnostics"
    CUSTOMER = "customer"
    SCHEDULING = "scheduling"
    MANUFACTURING = "manufacturing"
    UEBA = "ueba"

class AgentStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    STOPPED = "stopped"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class AgentHeartbeat:
    agent_id: str
    agent_type: AgentType
    timestamp: datetime
    status: AgentStatus
    messages_processed: int
    errors_count: int
    metadata: Dict[str, Any]

@dataclass
class TaskAssignment:
    task_id: str
    assigned_to: str
    agent_type: AgentType
    priority: TaskPriority
    payload: Dict[str, Any]
    assigned_at: datetime
    deadline: Optional[datetime] = None

@dataclass
class MasterStats:
    agents_monitored: int = 0
    active_agents: int = 0
    tasks_routed: int = 0
    alerts_processed: int = 0
    errors_detected: int = 0

# ============================================================================
# MASTER AGENT
# ============================================================================

class MasterAgent:
    def __init__(self):
        self.running = False
        self.stats = MasterStats()
        self.agent_registry: Dict[str, AgentHeartbeat] = {}
        self.pending_tasks: List[TaskAssignment] = []
        
        # Kafka
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        
        # MongoDB
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        # Configure logger
        logger.add(
            "logs/master_agent_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    async def start(self):
        """Start the Master Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🤖 MASTER AGENT STARTING")
        logger.info("=" * 80)
        
        # Connect to MongoDB
        await self.connect_mongodb()
        
        # Initialize Kafka
        await self.init_kafka()
        
        # Register self
        await self.register_agent()
        
        # Start background tasks
        asyncio.create_task(self.heartbeat_monitor())
        asyncio.create_task(self.send_heartbeat())
        asyncio.create_task(self.print_stats())
        
        logger.info("✅ Master Agent started successfully")
        logger.info(f"📥 Monitoring topics: {', '.join(KAFKA_INPUT_TOPICS)}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        
        # Main consumption loop
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_message(message.topic, message.value)
        
        except Exception as e:
            logger.error(f"❌ Error in consumption loop: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def connect_mongodb(self):
        """Connect to MongoDB"""
        try:
            self.mongo_client = AsyncIOMotorClient(MONGODB_URI)
            self.db = self.mongo_client[MONGODB_DATABASE]
            
            # Test connection
            await self.mongo_client.admin.command('ping')
            
            logger.info(f"✅ Connected to MongoDB: {MONGODB_DATABASE}")
            
            # Initialize collections if needed
            from db.mongodb_schemas import initialize_mongodb
            await initialize_mongodb(self.db)
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise
    
    async def init_kafka(self):
        """Initialize Kafka consumer and producer"""
        self.consumer = AIOKafkaConsumer(
            *KAFKA_INPUT_TOPICS,
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
        
        await self.consumer.start()
        await self.producer.start()
        
        logger.info("✅ Kafka initialized")
    
    async def register_agent(self):
        """Register Master Agent in MongoDB"""
        try:
            agent_doc = {
                "agent_id": AGENT_ID,
                "agent_type": AgentType.MASTER.value,
                "status": AgentStatus.ACTIVE.value,
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {
                    "topics_monitored": KAFKA_INPUT_TOPICS,
                    "started_at": datetime.now().isoformat()
                }
            }
            
            await self.db.agent_status.update_one(
                {"agent_id": AGENT_ID},
                {"$set": agent_doc},
                upsert=True
            )
            
            logger.info(f"📝 Registered Master Agent: {AGENT_ID}")
            
        except Exception as e:
            logger.error(f"❌ Failed to register agent: {e}")
    
    async def process_message(self, topic: str, message: Dict):
        """Process incoming messages based on topic"""
        try:
            if topic == 'vehicle_alerts':
                await self.handle_vehicle_alert(message)
            elif topic == 'diagnostic_results':
                await self.handle_diagnostic_result(message)
            elif topic == 'customer_ack':
                await self.handle_customer_ack(message)
            
            self.stats.alerts_processed += 1
            
        except Exception as e:
            logger.error(f"❌ Error processing message from {topic}: {e}")
            self.stats.errors_detected += 1
    
    async def handle_vehicle_alert(self, alert: Dict):
        """Handle incoming vehicle alert - route to appropriate agents"""
        try:
            vehicle_id = alert.get('vehicle_id')
            severity = alert.get('severity', 'WARNING').lower()
            failure_prob = alert.get('failure_probability', 0)
            
            logger.info(f"🚨 Alert received: {vehicle_id} | Severity: {severity} | Prob: {failure_prob:.2f}")
            
            # Determine routing priority
            priority = TaskPriority.CRITICAL if severity == 'critical' else TaskPriority.HIGH
            agents_to_notify = ROUTING_PRIORITIES.get(severity, ['diagnostics'])
            
            # Create task assignments
            for agent_type in agents_to_notify:
                task = TaskAssignment(
                    task_id=f"TASK_{vehicle_id}_{datetime.now().timestamp()}",
                    assigned_to=f"{agent_type}_agent",
                    agent_type=AgentType(agent_type),
                    priority=priority,
                    payload=alert,
                    assigned_at=datetime.now(),
                    deadline=datetime.now() + timedelta(hours=1 if severity == 'critical' else 24)
                )
                
                await self.route_task(task)
                self.stats.tasks_routed += 1
            
            # Store in alerts history
            await self.store_alert_history(alert)
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "alert_routed",
                "vehicle_id": vehicle_id,
                "severity": severity,
                "agents_notified": agents_to_notify,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to handle vehicle alert: {e}")
            self.stats.errors_detected += 1
    
    async def handle_diagnostic_result(self, result: Dict):
        """Handle diagnostic results - route to customer and scheduling"""
        try:
            vehicle_id = result.get('vehicle_id')
            root_cause = result.get('root_cause', 'Unknown')
            
            logger.info(f"🔍 Diagnostic result: {vehicle_id} | RCA: {root_cause}")
            
            # Route to customer agent for notification
            customer_task = TaskAssignment(
                task_id=f"CUST_{vehicle_id}_{datetime.now().timestamp()}",
                assigned_to="customer_agent",
                agent_type=AgentType.CUSTOMER,
                priority=TaskPriority.HIGH,
                payload=result,
                assigned_at=datetime.now()
            )
            
            await self.route_task(customer_task)
            
            # If critical, route to scheduling agent
            if result.get('severity') == 'critical':
                scheduling_task = TaskAssignment(
                    task_id=f"SCHED_{vehicle_id}_{datetime.now().timestamp()}",
                    assigned_to="scheduling_agent",
                    agent_type=AgentType.SCHEDULING,
                    priority=TaskPriority.CRITICAL,
                    payload=result,
                    assigned_at=datetime.now(),
                    deadline=datetime.now() + timedelta(hours=4)
                )
                
                await self.route_task(scheduling_task)
            
            self.stats.tasks_routed += 2
            
        except Exception as e:
            logger.error(f"❌ Failed to handle diagnostic result: {e}")
    
    async def handle_customer_ack(self, ack: Dict):
        """Handle customer acknowledgment"""
        try:
            vehicle_id = ack.get('vehicle_id')
            ack_type = ack.get('type', 'unknown')
            
            logger.info(f"✅ Customer ACK: {vehicle_id} | Type: {ack_type}")
            
            # Update alerts history
            await self.db.alerts_history.update_one(
                {"vehicle_id": vehicle_id, "resolution_status": "pending"},
                {"$set": {
                    "resolution_status": "acknowledged",
                    "acknowledged_at": datetime.now()
                }}
            )
            
            # Log activity
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "customer_acknowledged",
                "vehicle_id": vehicle_id,
                "ack_type": ack_type,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to handle customer ack: {e}")
    
    async def route_task(self, task: TaskAssignment):
        """Route task to appropriate agent via Kafka"""
        try:
            # Determine target topic based on agent type
            topic_map = {
                AgentType.DIAGNOSTICS: 'diagnostic_results',
                AgentType.CUSTOMER: 'customer_ack',
                AgentType.SCHEDULING: 'service_requests',
                AgentType.MANUFACTURING: 'manufacturing_feedback'
            }
            
            # For now, just log the routing (agents will consume from their respective topics)
            logger.debug(f"📤 Routing task {task.task_id} to {task.assigned_to}")
            
            # Log the task assignment
            await self.log_activity({
                "agent_id": AGENT_ID,
                "action": "task_routed",
                "task_id": task.task_id,
                "assigned_to": task.assigned_to,
                "priority": task.priority.value,
                "timestamp": datetime.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"❌ Failed to route task: {e}")
    
    async def store_alert_history(self, alert: Dict):
        """Store alert in MongoDB for historical tracking"""
        try:
            alert_doc = {
                "alert_id": alert.get('alert_id', f"ALT_{datetime.now().timestamp()}"),
                "vehicle_id": alert.get('vehicle_id'),
                "timestamp": datetime.fromisoformat(alert.get('timestamp', datetime.now().isoformat()).replace('Z', '+00:00')),
                "severity": alert.get('severity', 'warning').lower(),
                "failure_probability": alert.get('failure_probability', 0),
                "customer_notified": False,
                "service_scheduled": False,
                "resolution_status": "pending",
                "agents_processed": [AGENT_ID],
                "created_at": datetime.now()
            }
            
            await self.db.alerts_history.insert_one(alert_doc)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to store alert history: {e}")
    
    async def log_activity(self, activity: Dict):
        """Log agent activity to Kafka"""
        try:
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=activity)
        except Exception as e:
            logger.warning(f"⚠️ Failed to log activity: {e}")
    
    async def heartbeat_monitor(self):
        """Monitor other agents' heartbeats"""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            try:
                # Query MongoDB for agent statuses
                agents = await self.db.agent_status.find(
                    {"agent_type": {"$ne": AgentType.MASTER.value}}
                ).to_list(length=100)
                
                now = datetime.now()
                active_count = 0
                
                for agent in agents:
                    agent_id = agent['agent_id']
                    last_heartbeat = agent.get('last_heartbeat')
                    
                    if last_heartbeat and (now - last_heartbeat).total_seconds() < AGENT_TIMEOUT:
                        active_count += 1
                    else:
                        # Agent might be down
                        logger.warning(f"⚠️ Agent {agent_id} hasn't sent heartbeat in {AGENT_TIMEOUT}s")
                        
                        # Update status
                        await self.db.agent_status.update_one(
                            {"agent_id": agent_id},
                            {"$set": {"status": AgentStatus.ERROR.value}}
                        )
                
                self.stats.agents_monitored = len(agents)
                self.stats.active_agents = active_count
                
            except Exception as e:
                logger.error(f"❌ Heartbeat monitor error: {e}")
    
    async def send_heartbeat(self):
        """Send own heartbeat to MongoDB"""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            try:
                await self.db.agent_status.update_one(
                    {"agent_id": AGENT_ID},
                    {"$set": {
                        "status": AgentStatus.ACTIVE.value,
                        "last_heartbeat": datetime.now(),
                        "messages_processed": self.stats.alerts_processed
                    }}
                )
                
                # Log heartbeat
                await self.log_activity({
                    "agent_id": AGENT_ID,
                    "action": "heartbeat",
                    "stats": asdict(self.stats),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"❌ Failed to send heartbeat: {e}")
    
    async def print_stats(self):
        """Print statistics periodically"""
        while self.running:
            await asyncio.sleep(30)
            
            logger.info(
                f"📊 Master Stats - "
                f"Agents: {self.stats.active_agents}/{self.stats.agents_monitored} | "
                f"Tasks Routed: {self.stats.tasks_routed} | "
                f"Alerts: {self.stats.alerts_processed} | "
                f"Errors: {self.stats.errors_detected}"
            )
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Master Agent...")
        self.running = False
        
        # Update status in MongoDB
        if self.db:
            await self.db.agent_status.update_one(
                {"agent_id": AGENT_ID},
                {"$set": {"status": AgentStatus.STOPPED.value}}
            )
        
        # Close Kafka connections
        if self.consumer:
            await self.consumer.stop()
        if self.producer:
            await self.producer.stop()
        
        # Close MongoDB
        if self.mongo_client:
            self.mongo_client.close()
        
        logger.info("✅ Master Agent shut down complete")
        logger.info(
            f"📊 Final Stats - "
            f"Tasks: {self.stats.tasks_routed} | "
            f"Alerts: {self.stats.alerts_processed}"
        )

# ============================================================================
# MAIN
# ============================================================================

async def main():
    agent = MasterAgent()
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("⚠️ Received shutdown signal")
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
