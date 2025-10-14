#!/usr/bin/env python3
"""
Data Cleaning and Enrichment Consumer
Consumes raw vehicle telemetry from Kafka, validates, cleans, enriches,
and publishes to clean stream for ML/analytics.
"""

import asyncio
import json
import signal
import sys
import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError
from pydantic import BaseModel, ValidationError, Field, validator
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_RAW = os.getenv("KAFKA_TOPIC_RAW", "vehicle_telemetry_raw")
KAFKA_TOPIC_CLEAN = os.getenv("KAFKA_TOPIC_CLEAN", "vehicle_telemetry_clean")
KAFKA_TOPIC_ANOMALIES = os.getenv("KAFKA_TOPIC_ANOMALIES", "vehicle_anomalies")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "telemetry_cleaner_group")

# Rolling average window size
ROLLING_WINDOW_SIZE = int(os.getenv("ROLLING_WINDOW_SIZE", "10"))


class GPSLocation(BaseModel):
    """GPS coordinates validation"""
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")


class VehicleTelemetrySchema(BaseModel):
    """
    Pydantic schema for vehicle telemetry validation.
    Ensures all fields meet expected types and ranges.
    """
    vehicle_id: str = Field(..., min_length=1, max_length=50)
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    engine_rpm: int = Field(..., ge=0, le=8000, description="Engine RPM")
    engine_temp: float = Field(..., ge=0, le=150, description="Engine temperature in °C")
    vibration: float = Field(..., ge=0, le=10, description="Vibration RMS")
    speed: float = Field(..., ge=0, le=250, description="Speed in km/h")
    gps: GPSLocation
    fuel_level: float = Field(..., ge=0, le=100, description="Fuel level %")
    battery_voltage: float = Field(..., ge=0, le=20, description="Battery voltage")
    
    # Optional bridge metadata
    bridge_timestamp: Optional[str] = None
    mqtt_topic: Optional[str] = None
    
    @validator('timestamp', 'bridge_timestamp')
    def validate_timestamp(cls, v):
        """Validate ISO 8601 timestamp format"""
        if v:
            try:
                datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError(f"Invalid timestamp format: {v}")
        return v
    
    class Config:
        extra = 'allow'  # Allow additional fields


@dataclass
class AnomalyReport:
    """Anomaly detection report"""
    vehicle_id: str
    timestamp: str
    anomaly_type: str
    field: str
    value: float
    threshold: Dict[str, float]
    severity: str  # "low", "medium", "high", "critical"
    message: str


class RollingStats:
    """Maintains rolling statistics for anomaly detection"""
    
    def __init__(self, window_size: int = ROLLING_WINDOW_SIZE):
        self.window_size = window_size
        self.windows: Dict[str, Dict[str, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=window_size)))
    
    def add_value(self, vehicle_id: str, field: str, value: float):
        """Add a value to the rolling window"""
        self.windows[vehicle_id][field].append(value)
    
    def get_average(self, vehicle_id: str, field: str) -> Optional[float]:
        """Get rolling average for a field"""
        values = self.windows[vehicle_id][field]
        if len(values) == 0:
            return None
        return sum(values) / len(values)
    
    def get_stats(self, vehicle_id: str, field: str) -> Dict[str, float]:
        """Get statistics (min, max, avg) for a field"""
        values = list(self.windows[vehicle_id][field])
        if not values:
            return {}
        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values)
        }


class DataCleanerConsumer:
    """
    Kafka consumer that validates, cleanses, and enriches vehicle telemetry.
    Detects anomalies and publishes to separate streams.
    """
    
    def __init__(self):
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        self.running = False
        
        # Statistics
        self.messages_consumed = 0
        self.messages_cleaned = 0
        self.messages_rejected = 0
        self.anomalies_detected = 0
        self.validation_errors = 0
        
        # Rolling statistics for anomaly detection
        self.rolling_stats = RollingStats()
        
        # Anomaly thresholds
        self.thresholds = {
            "engine_temp": {"warning": 100, "critical": 110},
            "vibration": {"warning": 6, "critical": 8},
            "battery_voltage": {"low_warning": 11.5, "low_critical": 11.0, "high_warning": 14.8},
            "engine_rpm": {"warning": 6500, "critical": 7500},
            "fuel_level": {"low_warning": 15, "low_critical": 5}
        }
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure structured logging"""
        logger.remove()
        
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        logger.add(
            "logs/cleaner_consumer_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} - {message}",
            level="DEBUG"
        )
        
        logger.add(
            "logs/anomalies_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="WARNING",
            filter=lambda record: "ANOMALY" in record["message"],
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )
    
    async def setup_kafka(self):
        """Initialize Kafka consumer and producer"""
        logger.info(f"🔌 Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
        
        try:
            # Setup consumer
            self.consumer = AIOKafkaConsumer(
                KAFKA_TOPIC_RAW,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=CONSUMER_GROUP,
                auto_offset_reset='latest',  # Start from latest for new consumer group
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                value_deserializer=lambda m: m.decode('utf-8'),
                max_poll_records=500,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            await self.consumer.start()
            logger.success(f"✅ Consumer connected - Group: {CONSUMER_GROUP}")
            logger.info(f"📥 Consuming from topic: {KAFKA_TOPIC_RAW}")
            
            # Setup producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                compression_type='gzip',
                acks='all'
            )
            
            await self.producer.start()
            logger.success(f"✅ Producer connected")
            logger.info(f"📤 Publishing clean data to: {KAFKA_TOPIC_CLEAN}")
            logger.info(f"📤 Publishing anomalies to: {KAFKA_TOPIC_ANOMALIES}")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            raise
    
    def validate_message(self, raw_data: str) -> Optional[VehicleTelemetrySchema]:
        """
        Validate raw message against schema.
        
        Args:
            raw_data: Raw JSON string
            
        Returns:
            Validated telemetry object or None if invalid
        """
        try:
            data = json.loads(raw_data)
            validated = VehicleTelemetrySchema(**data)
            return validated
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON: {e}")
            self.validation_errors += 1
            return None
        except ValidationError as e:
            logger.warning(f"⚠️  Validation failed: {e}")
            self.validation_errors += 1
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected validation error: {e}")
            self.validation_errors += 1
            return None
    
    def detect_anomalies(self, telemetry: VehicleTelemetrySchema) -> List[AnomalyReport]:
        """
        Detect anomalies in telemetry data.
        
        Args:
            telemetry: Validated telemetry data
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        vehicle_id = telemetry.vehicle_id
        
        # Check engine temperature
        if telemetry.engine_temp >= self.thresholds["engine_temp"]["critical"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_temperature",
                field="engine_temp",
                value=telemetry.engine_temp,
                threshold=self.thresholds["engine_temp"],
                severity="critical",
                message=f"Critical engine temperature: {telemetry.engine_temp}°C"
            ))
        elif telemetry.engine_temp >= self.thresholds["engine_temp"]["warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_temperature",
                field="engine_temp",
                value=telemetry.engine_temp,
                threshold=self.thresholds["engine_temp"],
                severity="medium",
                message=f"High engine temperature: {telemetry.engine_temp}°C"
            ))
        
        # Check vibration
        if telemetry.vibration >= self.thresholds["vibration"]["critical"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_vibration",
                field="vibration",
                value=telemetry.vibration,
                threshold=self.thresholds["vibration"],
                severity="critical",
                message=f"Critical vibration level: {telemetry.vibration}"
            ))
        elif telemetry.vibration >= self.thresholds["vibration"]["warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_vibration",
                field="vibration",
                value=telemetry.vibration,
                threshold=self.thresholds["vibration"],
                severity="medium",
                message=f"High vibration level: {telemetry.vibration}"
            ))
        
        # Check battery voltage
        if telemetry.battery_voltage <= self.thresholds["battery_voltage"]["low_critical"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="low_battery",
                field="battery_voltage",
                value=telemetry.battery_voltage,
                threshold=self.thresholds["battery_voltage"],
                severity="critical",
                message=f"Critical low battery: {telemetry.battery_voltage}V"
            ))
        elif telemetry.battery_voltage <= self.thresholds["battery_voltage"]["low_warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="low_battery",
                field="battery_voltage",
                value=telemetry.battery_voltage,
                threshold=self.thresholds["battery_voltage"],
                severity="low",
                message=f"Low battery: {telemetry.battery_voltage}V"
            ))
        elif telemetry.battery_voltage >= self.thresholds["battery_voltage"]["high_warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_voltage",
                field="battery_voltage",
                value=telemetry.battery_voltage,
                threshold=self.thresholds["battery_voltage"],
                severity="low",
                message=f"High battery voltage: {telemetry.battery_voltage}V"
            ))
        
        # Check engine RPM
        if telemetry.engine_rpm >= self.thresholds["engine_rpm"]["critical"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_rpm",
                field="engine_rpm",
                value=telemetry.engine_rpm,
                threshold=self.thresholds["engine_rpm"],
                severity="critical",
                message=f"Critical RPM: {telemetry.engine_rpm}"
            ))
        elif telemetry.engine_rpm >= self.thresholds["engine_rpm"]["warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="high_rpm",
                field="engine_rpm",
                value=telemetry.engine_rpm,
                threshold=self.thresholds["engine_rpm"],
                severity="medium",
                message=f"High RPM: {telemetry.engine_rpm}"
            ))
        
        # Check fuel level
        if telemetry.fuel_level <= self.thresholds["fuel_level"]["low_critical"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="low_fuel",
                field="fuel_level",
                value=telemetry.fuel_level,
                threshold=self.thresholds["fuel_level"],
                severity="high",
                message=f"Critical low fuel: {telemetry.fuel_level}%"
            ))
        elif telemetry.fuel_level <= self.thresholds["fuel_level"]["low_warning"]:
            anomalies.append(AnomalyReport(
                vehicle_id=vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="low_fuel",
                field="fuel_level",
                value=telemetry.fuel_level,
                threshold=self.thresholds["fuel_level"],
                severity="low",
                message=f"Low fuel: {telemetry.fuel_level}%"
            ))
        
        return anomalies
    
    def enrich_message(self, telemetry: VehicleTelemetrySchema) -> Dict[str, Any]:
        """
        Enrich telemetry with rolling statistics and metadata.
        
        Args:
            telemetry: Validated telemetry
            
        Returns:
            Enriched message dictionary
        """
        vehicle_id = telemetry.vehicle_id
        
        # Add rolling statistics
        fields_to_track = ["engine_temp", "vibration", "speed", "engine_rpm", "battery_voltage"]
        
        for field in fields_to_track:
            value = getattr(telemetry, field)
            self.rolling_stats.add_value(vehicle_id, field, float(value))
        
        # Build enriched message
        enriched = telemetry.dict()
        
        # Add processing timestamp
        enriched["processed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Add rolling averages
        enriched["rolling_averages"] = {}
        for field in fields_to_track:
            avg = self.rolling_stats.get_average(vehicle_id, field)
            if avg is not None:
                enriched["rolling_averages"][f"{field}_avg"] = round(avg, 2)
        
        # Add stats summary
        enriched["stats_window_size"] = ROLLING_WINDOW_SIZE
        
        return enriched
    
    async def publish_clean_data(self, enriched_data: Dict[str, Any]):
        """Publish cleaned and enriched data to Kafka"""
        try:
            vehicle_id = enriched_data["vehicle_id"]
            await self.producer.send_and_wait(
                KAFKA_TOPIC_CLEAN,
                value=enriched_data,
                key=vehicle_id
            )
            self.messages_cleaned += 1
            logger.debug(f"📤 Published clean data for {vehicle_id}")
        except Exception as e:
            logger.error(f"❌ Failed to publish clean data: {e}")
    
    async def publish_anomalies(self, anomalies: List[AnomalyReport]):
        """Publish detected anomalies to Kafka"""
        for anomaly in anomalies:
            try:
                await self.producer.send_and_wait(
                    KAFKA_TOPIC_ANOMALIES,
                    value=asdict(anomaly),
                    key=anomaly.vehicle_id
                )
                self.anomalies_detected += 1
                logger.warning(
                    f"⚠️  ANOMALY - {anomaly.vehicle_id}: {anomaly.message} "
                    f"(Severity: {anomaly.severity})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to publish anomaly: {e}")
    
    async def process_message(self, raw_message: str):
        """
        Process a single raw message: validate, detect anomalies, enrich, publish.
        
        Args:
            raw_message: Raw JSON message from Kafka
        """
        self.messages_consumed += 1
        
        # Validate
        telemetry = self.validate_message(raw_message)
        if not telemetry:
            self.messages_rejected += 1
            return
        
        # Detect anomalies
        anomalies = self.detect_anomalies(telemetry)
        
        # Enrich
        enriched_data = self.enrich_message(telemetry)
        
        # Publish clean data
        await self.publish_clean_data(enriched_data)
        
        # Publish anomalies if any
        if anomalies:
            await self.publish_anomalies(anomalies)
    
    async def consume_messages(self):
        """Main consumer loop"""
        logger.info("🔄 Starting message consumption...")
        
        try:
            async for msg in self.consumer:
                if not self.running:
                    break
                
                try:
                    await self.process_message(msg.value)
                except Exception as e:
                    logger.error(f"❌ Error processing message: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Consumer error: {e}")
    
    async def monitor_stats(self):
        """Periodically log statistics"""
        last_consumed = 0
        last_cleaned = 0
        
        while self.running:
            await asyncio.sleep(10)
            
            consumed_rate = (self.messages_consumed - last_consumed) / 10.0
            cleaned_rate = (self.messages_cleaned - last_cleaned) / 10.0
            
            last_consumed = self.messages_consumed
            last_cleaned = self.messages_cleaned
            
            logger.info(
                f"📊 Stats - Consumed: {self.messages_consumed:,} ({consumed_rate:.2f}/s) | "
                f"Cleaned: {self.messages_cleaned:,} ({cleaned_rate:.2f}/s) | "
                f"Rejected: {self.messages_rejected} | "
                f"Anomalies: {self.anomalies_detected} | "
                f"Validation Errors: {self.validation_errors}"
            )
    
    async def run(self):
        """Main run loop"""
        self.running = True
        
        logger.info("🧹 Starting Data Cleaner Consumer...")
        
        await self.setup_kafka()
        await asyncio.sleep(2)
        
        logger.success("✅ Consumer is operational")
        logger.info("Press Ctrl+C to stop...")
        
        tasks = [
            asyncio.create_task(self.consume_messages()),
            asyncio.create_task(self.monitor_stats())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Consumer tasks cancelled")
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down consumer...")
        self.running = False
        
        if self.consumer:
            await self.consumer.stop()
            logger.info("Consumer stopped")
        
        if self.producer:
            await self.producer.stop()
            logger.info("Producer stopped")
        
        logger.info(
            f"Final stats - Consumed: {self.messages_consumed}, "
            f"Cleaned: {self.messages_cleaned}, "
            f"Rejected: {self.messages_rejected}, "
            f"Anomalies: {self.anomalies_detected}"
        )
        logger.success("Consumer stopped successfully")


# Global consumer instance
consumer: Optional[DataCleanerConsumer] = None


def signal_handler(signum, frame):
    """Handle interrupt signals"""
    logger.info(f"\nReceived signal {signum}")
    if consumer:
        asyncio.create_task(consumer.shutdown())


async def main():
    """Main entry point"""
    global consumer
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    consumer = DataCleanerConsumer()
    
    try:
        await consumer.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await consumer.shutdown()


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
