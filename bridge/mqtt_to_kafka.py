#!/usr/bin/env python3
"""
MQTT to Kafka Bridge
Subscribes to MQTT vehicle telemetry and publishes to Kafka for distributed processing.
Handles retries, connection failures, and graceful shutdown.
"""

import asyncio
import json
import signal
import sys
import os
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "/vehicle/+/telemetry")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_RAW = os.getenv("KAFKA_TOPIC_RAW", "vehicle_telemetry_raw")

# Retry configuration
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))


class MQTTKafkaBridge:
    """
    Bridges MQTT vehicle telemetry messages to Kafka.
    Handles connection management, message transformation, and error recovery.
    """
    
    def __init__(self):
        self.mqtt_client: Optional[mqtt.Client] = None
        self.kafka_producer: Optional[AIOKafkaProducer] = None
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Statistics
        self.mqtt_received_count = 0
        self.kafka_published_count = 0
        self.error_count = 0
        self.last_message_time = None
        
        # Message queue for async processing
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure structured logging"""
        logger.remove()  # Remove default handler
        
        # Console output with colors
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        # File output with JSON structure
        logger.add(
            "logs/mqtt_kafka_bridge_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} - {message}",
            level="DEBUG"
        )
        
        # Separate file for errors
        logger.add(
            "logs/mqtt_kafka_bridge_errors_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} - {message}"
        )
    
    def setup_mqtt(self):
        """Initialize MQTT client with callbacks"""
        client_id = f"mqtt_kafka_bridge_{os.getpid()}"
        self.mqtt_client = mqtt.Client(client_id=client_id, clean_session=True)
        
        def on_connect(client, userdata, flags, rc):
            """Callback for when MQTT client connects"""
            if rc == 0:
                logger.success(f"✅ Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
                # Subscribe to vehicle telemetry topic
                client.subscribe(MQTT_TOPIC, qos=1)
                logger.info(f"📡 Subscribed to MQTT topic: {MQTT_TOPIC}")
            else:
                logger.error(f"❌ Failed to connect to MQTT broker. Return code: {rc}")
                self._handle_mqtt_error(rc)
        
        def on_disconnect(client, userdata, rc):
            """Callback for when MQTT client disconnects"""
            if rc != 0:
                logger.warning(f"⚠️  Unexpected disconnect from MQTT broker. RC: {rc}")
                # Attempt reconnection
                if self.running:
                    self._reconnect_mqtt()
        
        def on_message(client, userdata, msg):
            """Callback for when a message is received from MQTT"""
            try:
                self.mqtt_received_count += 1
                self.last_message_time = datetime.now(timezone.utc)
                
                # Parse message
                topic = msg.topic
                payload = msg.payload.decode('utf-8')
                
                # Queue message for async Kafka publishing
                if self.loop and self.running:
                    asyncio.run_coroutine_threadsafe(
                        self.message_queue.put((topic, payload)),
                        self.loop
                    )
                    
                    logger.debug(f"📥 MQTT message received from {topic}")
                    
            except Exception as e:
                logger.error(f"❌ Error processing MQTT message: {e}")
                self.error_count += 1
        
        def on_subscribe(client, userdata, mid, granted_qos):
            """Callback for successful subscription"""
            logger.success(f"✅ Subscription confirmed with QoS: {granted_qos}")
        
        # Assign callbacks
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_message = on_message
        self.mqtt_client.on_subscribe = on_subscribe
        
        # Connect to broker
        try:
            logger.info(f"🔌 Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT broker: {e}")
            raise
    
    def _handle_mqtt_error(self, rc: int):
        """Handle MQTT connection errors"""
        error_messages = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }
        msg = error_messages.get(rc, f"Unknown error code: {rc}")
        logger.error(f"MQTT Error: {msg}")
    
    def _reconnect_mqtt(self):
        """Attempt to reconnect to MQTT broker"""
        logger.info("🔄 Attempting to reconnect to MQTT broker...")
        try:
            self.mqtt_client.reconnect()
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
    
    async def setup_kafka(self):
        """Initialize Kafka producer"""
        logger.info(f"🔌 Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
        
        try:
            self.kafka_producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: v.encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                compression_type='gzip',
                acks='all'  # Wait for all replicas
            )
            
            await self.kafka_producer.start()
            logger.success(f"✅ Connected to Kafka cluster")
            logger.info(f"📤 Publishing to topic: {KAFKA_TOPIC_RAW}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            raise
    
    async def publish_to_kafka(self, topic: str, payload: str) -> bool:
        """
        Publish a message to Kafka with retry logic.
        
        Args:
            topic: MQTT topic (used for logging)
            payload: JSON message payload
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Parse message to extract vehicle_id for partitioning
            message_data = json.loads(payload)
            vehicle_id = message_data.get("vehicle_id", "unknown")
            
            # Add bridge metadata
            message_data["bridge_timestamp"] = datetime.now(timezone.utc).isoformat()
            message_data["mqtt_topic"] = topic
            
            enriched_payload = json.dumps(message_data)
            
            # Publish to Kafka (key by vehicle_id for consistent partitioning)
            for attempt in range(MAX_RETRIES):
                try:
                    result = await asyncio.wait_for(
                        self.kafka_producer.send_and_wait(
                            KAFKA_TOPIC_RAW,
                            value=enriched_payload,
                            key=vehicle_id
                        ),
                        timeout=10.0
                    )
                    
                    self.kafka_published_count += 1
                    logger.debug(
                        f"📤 Published to Kafka - Vehicle: {vehicle_id}, "
                        f"Partition: {result.partition}, Offset: {result.offset}"
                    )
                    return True
                    
                except (KafkaTimeoutError, KafkaError) as e:
                    logger.warning(
                        f"⚠️  Kafka publish attempt {attempt + 1}/{MAX_RETRIES} failed: {e}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_BACKOFF ** attempt)
                    else:
                        raise
                        
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON payload from {topic}: {e}")
            self.error_count += 1
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to publish to Kafka after retries: {e}")
            self.error_count += 1
            return False
    
    async def process_messages(self):
        """Process messages from queue and publish to Kafka"""
        logger.info("🔄 Starting message processing worker...")
        
        while self.running:
            try:
                # Get message from queue with timeout
                topic, payload = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Publish to Kafka
                await self.publish_to_kafka(topic, payload)
                
                # Mark task as done
                self.message_queue.task_done()
                
            except asyncio.TimeoutError:
                # No message in queue, continue
                continue
                
            except Exception as e:
                logger.error(f"❌ Error in message processing worker: {e}")
                await asyncio.sleep(1)
    
    async def monitor_stats(self):
        """Periodically log statistics"""
        last_mqtt_count = 0
        last_kafka_count = 0
        
        while self.running:
            await asyncio.sleep(10)  # Report every 10 seconds
            
            mqtt_rate = (self.mqtt_received_count - last_mqtt_count) / 10.0
            kafka_rate = (self.kafka_published_count - last_kafka_count) / 10.0
            
            last_mqtt_count = self.mqtt_received_count
            last_kafka_count = self.kafka_published_count
            
            queue_size = self.message_queue.qsize()
            
            logger.info(
                f"📊 Stats - MQTT Received: {self.mqtt_received_count:,} ({mqtt_rate:.2f}/s) | "
                f"Kafka Published: {self.kafka_published_count:,} ({kafka_rate:.2f}/s) | "
                f"Queue: {queue_size} | Errors: {self.error_count}"
            )
            
            # Alert if queue is growing
            if queue_size > 5000:
                logger.warning(f"⚠️  Message queue is large: {queue_size} messages pending")
    
    async def run(self):
        """Main bridge loop"""
        self.running = True
        self.loop = asyncio.get_event_loop()
        
        logger.info("🌉 Starting MQTT to Kafka Bridge...")
        
        # Setup connections
        self.setup_mqtt()
        await self.setup_kafka()
        await asyncio.sleep(2)  # Give connections time to establish
        
        logger.success("✅ Bridge is operational")
        logger.info(f"MQTT: {MQTT_BROKER}:{MQTT_PORT} -> Kafka: {KAFKA_BOOTSTRAP_SERVERS}")
        logger.info("Press Ctrl+C to stop...")
        
        # Start worker tasks
        tasks = [
            asyncio.create_task(self.process_messages()),
            asyncio.create_task(self.monitor_stats())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Bridge tasks cancelled")
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down bridge...")
        self.running = False
        
        # Stop MQTT
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("MQTT client disconnected")
        
        # Flush remaining messages
        if not self.message_queue.empty():
            logger.info(f"📤 Flushing {self.message_queue.qsize()} remaining messages...")
            await self.message_queue.join()
        
        # Stop Kafka
        if self.kafka_producer:
            await self.kafka_producer.stop()
            logger.info("Kafka producer stopped")
        
        logger.info(
            f"Final stats - MQTT: {self.mqtt_received_count}, "
            f"Kafka: {self.kafka_published_count}, Errors: {self.error_count}"
        )
        logger.success("Bridge stopped successfully")


# Global bridge instance for signal handling
bridge: Optional[MQTTKafkaBridge] = None


def signal_handler(signum, frame):
    """Handle interrupt signals for graceful shutdown"""
    logger.info(f"\nReceived signal {signum}")
    if bridge and bridge.loop:
        asyncio.run_coroutine_threadsafe(bridge.shutdown(), bridge.loop)


async def main():
    """Main entry point"""
    global bridge
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run bridge
    bridge = MQTTKafkaBridge()
    
    try:
        await bridge.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await bridge.shutdown()


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Run the bridge
    asyncio.run(main())
