"""
ClickHouse Ingestion Consumer - Phase 2
Automotive Predictive Maintenance System

Consumes cleaned telemetry from Kafka topic 'vehicle_telemetry_clean' 
and ingests into ClickHouse for persistent storage and analytics.

Features:
- Async consumption from Kafka with batch processing
- Direct insertion into ClickHouse MergeTree table
- Anomaly detection and separate anomaly stream
- Data validation and enrichment
- Graceful shutdown with offset commit
- Structured logging and metrics
"""

import asyncio
import json
import signal
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from clickhouse_driver import Client
from pydantic import BaseModel, ValidationError, Field
from loguru import logger
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_CLEAN = os.getenv("KAFKA_TOPIC_CLEAN", "vehicle_telemetry_clean")
KAFKA_TOPIC_ANOMALIES = os.getenv("KAFKA_TOPIC_ANOMALIES", "vehicle_anomalies")
KAFKA_GROUP_ID = "clickhouse_ingest_consumer"

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")

BATCH_SIZE = int(os.getenv("CLICKHOUSE_BATCH_SIZE", "100"))
BATCH_TIMEOUT_SECONDS = float(os.getenv("CLICKHOUSE_BATCH_TIMEOUT", "5.0"))

# Anomaly detection thresholds
ANOMALY_THRESHOLDS = {
    "engine_temp": {"warning": 100.0, "critical": 110.0},
    "vibration": {"warning": 6.0, "critical": 8.0},
    "battery_voltage": {"warning_low": 11.5, "critical_low": 11.0},
    "engine_rpm": {"warning": 6500, "critical": 7500},
    "fuel_level": {"warning_low": 15.0, "critical_low": 5.0}
}

# ============================================================================
# DATA MODELS
# ============================================================================

class GPSLocation(BaseModel):
    """GPS coordinates from Phase 1 cleaner"""
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

class TelemetryRecord(BaseModel):
    """Validated telemetry record from Kafka (matches Phase 1 cleaner output)"""
    vehicle_id: str
    timestamp: str  # ISO string from Phase 1
    engine_rpm: int = Field(ge=0, le=8000)
    engine_temp: float = Field(ge=-50, le=150)
    vibration: float = Field(ge=0, le=20)
    speed: float = Field(ge=0, le=300)
    gps: GPSLocation  # Nested GPS structure from Phase 1
    fuel_level: float = Field(ge=0, le=100)
    battery_voltage: float = Field(ge=0, le=20)
    
    # Rolling averages from Phase 1 enrichment (nested)
    rolling_averages: Optional[Dict[str, float]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S")
        }

@dataclass
class AnomalyDetection:
    """Detected anomaly record"""
    vehicle_id: str
    timestamp: datetime
    anomaly_type: str
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'
    metric_name: str
    metric_value: float
    threshold: float
    message: str
    detected_at: datetime = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now()

@dataclass
class IngestionStats:
    """Statistics for monitoring"""
    consumed: int = 0
    inserted: int = 0
    failed: int = 0
    anomalies_detected: int = 0
    validation_errors: int = 0
    last_inserted_batch: int = 0

# ============================================================================
# CLICKHOUSE INGEST CONSUMER
# ============================================================================

class ClickHouseIngestConsumer:
    def __init__(self):
        self.running = False
        self.stats = IngestionStats()
        self.batch: List[Dict] = []
        self.last_batch_time = asyncio.get_event_loop().time()
        
        # Initialize ClickHouse client
        self.clickhouse_client = None
        
        # Kafka consumer and producer
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.anomaly_producer: Optional[AIOKafkaProducer] = None

        # Configure logger
        logger.add(
            "logs/clickhouse_ingest_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )

    def connect_clickhouse(self):
        """Initialize ClickHouse connection"""
        try:
            self.clickhouse_client = Client(
                host=CLICKHOUSE_HOST,
                port=CLICKHOUSE_PORT,
                user=CLICKHOUSE_USER,
                password=CLICKHOUSE_PASSWORD,
                database=CLICKHOUSE_DATABASE,
                settings={'use_numpy': False}
            )
            # Test connection
            result = self.clickhouse_client.execute('SELECT 1')
            logger.info(f"✅ Connected to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to ClickHouse: {e}")
            return False

    async def start(self):
        """Start the consumer"""
        self.running = True
        
        # Connect to ClickHouse
        if not self.connect_clickhouse():
            logger.error("Cannot start without ClickHouse connection")
            return

        # Initialize Kafka consumer
        self.consumer = AIOKafkaConsumer(
            KAFKA_TOPIC_CLEAN,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )

        # Initialize Kafka producer for anomalies
        self.anomaly_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            compression_type='gzip',
            acks='all'
        )

        await self.consumer.start()
        await self.anomaly_producer.start()
        
        logger.info(f"🚀 ClickHouse Ingest Consumer started")
        logger.info(f"📥 Consuming from: {KAFKA_TOPIC_CLEAN}")
        logger.info(f"💾 Inserting into ClickHouse: {CLICKHOUSE_DATABASE}.telemetry")
        logger.info(f"⚡ Batch size: {BATCH_SIZE}, Timeout: {BATCH_TIMEOUT_SECONDS}s")

        # Start background tasks
        stats_task = asyncio.create_task(self.print_stats())
        batch_timeout_task = asyncio.create_task(self.batch_timeout_monitor())

        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_message(message.value)
                
                # Check if batch is ready to insert
                if len(self.batch) >= BATCH_SIZE:
                    await self.flush_batch()

        except Exception as e:
            logger.error(f"❌ Consumer error: {e}")
        finally:
            stats_task.cancel()
            batch_timeout_task.cancel()
            await self.shutdown()

    async def process_message(self, message: Dict):
        """Process and validate a single message"""
        self.stats.consumed += 1
        
        try:
            # Validate with Pydantic
            telemetry = TelemetryRecord(**message)
            
            # Parse timestamp
            ts = datetime.fromisoformat(telemetry.timestamp.replace('Z', '+00:00'))
            
            # Extract rolling averages from nested structure
            rolling_avgs = telemetry.rolling_averages or {}
            
            # Convert to dict for ClickHouse
            record = {
                'vehicle_id': telemetry.vehicle_id,
                'timestamp': ts,
                'engine_rpm': telemetry.engine_rpm,
                'engine_temp': telemetry.engine_temp,
                'vibration': telemetry.vibration,
                'speed': telemetry.speed,
                'gps_lat': telemetry.gps.lat,
                'gps_lon': telemetry.gps.lon,
                'fuel_level': telemetry.fuel_level,
                'battery_voltage': telemetry.battery_voltage,
                'rolling_avg_rpm': rolling_avgs.get('engine_rpm_avg', 0.0),
                'rolling_avg_temp': rolling_avgs.get('engine_temp_avg', 0.0),
                'rolling_avg_vibration': rolling_avgs.get('vibration_avg', 0.0),
                'rolling_avg_speed': rolling_avgs.get('speed_avg', 0.0),
            }
            
            # Add to batch
            self.batch.append(record)
            
            # Detect anomalies
            anomalies = self.detect_anomalies(telemetry)
            if anomalies:
                await self.publish_anomalies(anomalies)
            
        except ValidationError as e:
            self.stats.validation_errors += 1
            logger.warning(f"⚠️ Validation error: {e}")
        except Exception as e:
            self.stats.failed += 1
            logger.error(f"❌ Processing error: {e}")

    def detect_anomalies(self, telemetry: TelemetryRecord) -> List[AnomalyDetection]:
        """Detect anomalies in telemetry data"""
        anomalies = []
        
        # Parse timestamp
        ts = datetime.fromisoformat(telemetry.timestamp.replace('Z', '+00:00'))
        
        # High engine temperature
        if telemetry.engine_temp >= ANOMALY_THRESHOLDS["engine_temp"]["critical"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=ts,
                anomaly_type="HIGH_TEMP",
                severity="CRITICAL",
                metric_name="engine_temp",
                metric_value=telemetry.engine_temp,
                threshold=ANOMALY_THRESHOLDS["engine_temp"]["critical"],
                message=f"Critical high engine temperature: {telemetry.engine_temp:.2f}°C"
            ))
        elif telemetry.engine_temp >= ANOMALY_THRESHOLDS["engine_temp"]["warning"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=ts,
                anomaly_type="HIGH_TEMP",
                severity="WARNING",
                metric_name="engine_temp",
                metric_value=telemetry.engine_temp,
                threshold=ANOMALY_THRESHOLDS["engine_temp"]["warning"],
                message=f"High engine temperature: {telemetry.engine_temp:.2f}°C"
            ))
        
        # Low battery voltage
        if telemetry.battery_voltage <= ANOMALY_THRESHOLDS["battery_voltage"]["critical_low"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=ts,
                anomaly_type="LOW_BATTERY",
                severity="CRITICAL",
                metric_name="battery_voltage",
                metric_value=telemetry.battery_voltage,
                threshold=ANOMALY_THRESHOLDS["battery_voltage"]["critical_low"],
                message=f"Critical low battery: {telemetry.battery_voltage:.2f}V"
            ))
        elif telemetry.battery_voltage <= ANOMALY_THRESHOLDS["battery_voltage"]["warning_low"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=ts,
                anomaly_type="LOW_BATTERY",
                severity="WARNING",
                metric_name="battery_voltage",
                metric_value=telemetry.battery_voltage,
                threshold=ANOMALY_THRESHOLDS["battery_voltage"]["warning_low"],
                message=f"Low battery: {telemetry.battery_voltage:.2f}V"
            ))
        
        # High vibration
        if telemetry.vibration >= ANOMALY_THRESHOLDS["vibration"]["critical"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="HIGH_VIBRATION",
                severity="CRITICAL",
                metric_name="vibration",
                metric_value=telemetry.vibration,
                threshold=ANOMALY_THRESHOLDS["vibration"]["critical"],
                message=f"Critical high vibration: {telemetry.vibration:.2f}"
            ))
        elif telemetry.vibration >= ANOMALY_THRESHOLDS["vibration"]["warning"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="HIGH_VIBRATION",
                severity="WARNING",
                metric_name="vibration",
                metric_value=telemetry.vibration,
                threshold=ANOMALY_THRESHOLDS["vibration"]["warning"],
                message=f"High vibration: {telemetry.vibration:.2f}"
            ))
        
        # Low fuel
        if telemetry.fuel_level <= ANOMALY_THRESHOLDS["fuel_level"]["critical_low"]:
            anomalies.append(AnomalyDetection(
                vehicle_id=telemetry.vehicle_id,
                timestamp=telemetry.timestamp,
                anomaly_type="LOW_FUEL",
                severity="CRITICAL",
                metric_name="fuel_level",
                metric_value=telemetry.fuel_level,
                threshold=ANOMALY_THRESHOLDS["fuel_level"]["critical_low"],
                message=f"Critical low fuel: {telemetry.fuel_level:.1f}%"
            ))
        
        if anomalies:
            self.stats.anomalies_detected += len(anomalies)
        
        return anomalies

    async def publish_anomalies(self, anomalies: List[AnomalyDetection]):
        """Publish detected anomalies to Kafka and ClickHouse"""
        try:
            for anomaly in anomalies:
                # Convert to dict with string timestamps
                # Handle both datetime objects and datetime objects
                timestamp_str = anomaly.timestamp.strftime("%Y-%m-%d %H:%M:%S") if isinstance(anomaly.timestamp, datetime) else str(anomaly.timestamp)
                detected_at_str = anomaly.detected_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(anomaly.detected_at, datetime) else str(anomaly.detected_at)
                
                anomaly_dict = {
                    'vehicle_id': anomaly.vehicle_id,
                    'timestamp': timestamp_str,
                    'anomaly_type': anomaly.anomaly_type,
                    'severity': anomaly.severity,
                    'metric_name': anomaly.metric_name,
                    'metric_value': anomaly.metric_value,
                    'threshold': anomaly.threshold,
                    'message': anomaly.message,
                    'detected_at': detected_at_str
                }
                
                # Publish to Kafka anomalies topic
                await self.anomaly_producer.send(
                    KAFKA_TOPIC_ANOMALIES,
                    value=anomaly_dict
                )
                
                # Insert directly into ClickHouse anomalies table
                self.clickhouse_client.execute(
                    """
                    INSERT INTO anomalies 
                    (vehicle_id, timestamp, anomaly_type, severity, metric_name, 
                     metric_value, threshold, message, detected_at)
                    VALUES
                    """,
                    [(
                        anomaly.vehicle_id,
                        anomaly.timestamp,
                        anomaly.anomaly_type,
                        anomaly.severity,
                        anomaly.metric_name,
                        anomaly.metric_value,
                        anomaly.threshold,
                        anomaly.message,
                        anomaly.detected_at
                    )]
                )
                
        except Exception as e:
            logger.error(f"❌ Failed to publish anomalies: {e}")

    async def flush_batch(self):
        """Insert batch into ClickHouse"""
        if not self.batch:
            return
        
        batch_size = len(self.batch)
        
        try:
            # Prepare data for batch insert
            data_tuples = [
                (
                    record['vehicle_id'],
                    record['timestamp'],
                    record['engine_rpm'],
                    record['engine_temp'],
                    record['vibration'],
                    record['speed'],
                    record['gps_lat'],
                    record['gps_lon'],
                    record['fuel_level'],
                    record['battery_voltage'],
                    record['rolling_avg_rpm'],
                    record['rolling_avg_temp'],
                    record['rolling_avg_vibration'],
                    record['rolling_avg_speed']
                )
                for record in self.batch
            ]
            
            # Batch insert into ClickHouse
            self.clickhouse_client.execute(
                """
                INSERT INTO telemetry 
                (vehicle_id, timestamp, engine_rpm, engine_temp, vibration, speed,
                 gps_lat, gps_lon, fuel_level, battery_voltage,
                 rolling_avg_rpm, rolling_avg_temp, rolling_avg_vibration, rolling_avg_speed)
                VALUES
                """,
                data_tuples
            )
            
            self.stats.inserted += batch_size
            self.stats.last_inserted_batch = batch_size
            
            # Commit Kafka offsets after successful insert
            await self.consumer.commit()
            
            # Clear batch
            self.batch.clear()
            self.last_batch_time = asyncio.get_event_loop().time()
            
            logger.debug(f"✅ Inserted batch of {batch_size} records into ClickHouse")
            
        except Exception as e:
            self.stats.failed += batch_size
            logger.error(f"❌ Failed to insert batch: {e}")
            # Keep batch for retry or move to DLQ in production
            self.batch.clear()

    async def batch_timeout_monitor(self):
        """Monitor batch timeout and flush if exceeded"""
        while self.running:
            await asyncio.sleep(1)
            
            current_time = asyncio.get_event_loop().time()
            time_since_last_batch = current_time - self.last_batch_time
            
            if self.batch and time_since_last_batch >= BATCH_TIMEOUT_SECONDS:
                logger.debug(f"⏱️ Batch timeout reached ({BATCH_TIMEOUT_SECONDS}s), flushing {len(self.batch)} records")
                await self.flush_batch()

    async def print_stats(self):
        """Print statistics periodically"""
        while self.running:
            await asyncio.sleep(10)
            
            logger.info(
                f"📊 Stats - Consumed: {self.stats.consumed} | "
                f"Inserted: {self.stats.inserted} | "
                f"Failed: {self.stats.failed} | "
                f"Anomalies: {self.stats.anomalies_detected} | "
                f"Validation Errors: {self.stats.validation_errors} | "
                f"Last Batch: {self.stats.last_inserted_batch} | "
                f"Pending: {len(self.batch)}"
            )

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down ClickHouse Ingest Consumer...")
        self.running = False
        
        # Flush remaining batch
        if self.batch:
            logger.info(f"💾 Flushing final batch of {len(self.batch)} records...")
            await self.flush_batch()
        
        # Close Kafka connections
        if self.consumer:
            await self.consumer.stop()
        if self.anomaly_producer:
            await self.anomaly_producer.stop()
        
        # Close ClickHouse connection
        if self.clickhouse_client:
            self.clickhouse_client.disconnect()
        
        logger.info("✅ Shutdown complete")
        logger.info(f"📊 Final Stats - Consumed: {self.stats.consumed} | Inserted: {self.stats.inserted} | Failed: {self.stats.failed}")

# ============================================================================
# MAIN
# ============================================================================

async def main():
    consumer = ClickHouseIngestConsumer()
    
    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("⚠️ Received shutdown signal")
        asyncio.create_task(consumer.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await consumer.start()

if __name__ == "__main__":
    asyncio.run(main())
