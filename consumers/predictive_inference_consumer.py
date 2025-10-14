"""
Predictive Inference Consumer - Phase 3
========================================
Real-time ML inference pipeline: Kafka → Model → ClickHouse + Kafka

Consumes cleaned telemetry, runs failure prediction, publishes alerts.
"""

import os
import asyncio
import signal
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

import joblib
import numpy as np
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from clickhouse_driver import Client
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Kafka
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_INPUT_TOPIC = os.getenv('KAFKA_INPUT_TOPIC', 'vehicle_telemetry_clean')
KAFKA_PREDICTIONS_TOPIC = os.getenv('KAFKA_PREDICTIONS_TOPIC', 'vehicle_predictions')
KAFKA_ALERTS_TOPIC = os.getenv('KAFKA_ALERTS_TOPIC', 'vehicle_alerts')
KAFKA_GROUP_ID = 'predictive_inference_consumer'

# ClickHouse
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '9000'))
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', 'clickhouse_pass')
CLICKHOUSE_DATABASE = os.getenv('CLICKHOUSE_DATABASE', 'telemetry_db')

# ML Model
MODEL_PATH = os.getenv('MODEL_PATH', 'models/vehicle_failure_model.pkl')

# Inference settings
BATCH_SIZE = int(os.getenv('INFERENCE_BATCH_SIZE', '10'))
BATCH_TIMEOUT = float(os.getenv('INFERENCE_BATCH_TIMEOUT', '2.0'))
ALERT_THRESHOLD = float(os.getenv('ALERT_THRESHOLD', '0.7'))

# Feature columns (must match training)
FEATURE_COLUMNS = [
    'engine_rpm', 'engine_temp', 'vibration', 'speed',
    'fuel_level', 'battery_voltage',
    'rolling_avg_rpm', 'rolling_avg_temp',
    'rolling_avg_vibration', 'rolling_avg_speed'
]

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class PredictionResult:
    """ML prediction result"""
    vehicle_id: str
    timestamp: datetime
    failure_probability: float
    health_status: str
    engine_temp: float
    vibration: float
    engine_rpm: float
    speed: float
    fuel_level: float
    battery_voltage: float
    reason: str
    model_version: str = "1.0.0"

@dataclass
class AlertRecord:
    """Alert record for critical predictions"""
    vehicle_id: str
    timestamp: datetime
    failure_probability: float
    health_status: str
    reason: str
    severity: str

@dataclass
class InferenceStats:
    """Statistics tracker"""
    messages_consumed: int = 0
    predictions_made: int = 0
    alerts_generated: int = 0
    db_inserts: int = 0
    kafka_publishes: int = 0
    errors: int = 0

# ============================================================================
# PREDICTIVE INFERENCE ENGINE
# ============================================================================

class PredictiveInferenceConsumer:
    def __init__(self):
        self.running = False
        self.stats = InferenceStats()
        self.batch: List[Dict] = []
        self.last_batch_time = asyncio.get_event_loop().time()
        
        # ML Model
        self.model = None
        self.model_metadata = None
        
        # Kafka
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.predictions_producer: Optional[AIOKafkaProducer] = None
        self.alerts_producer: Optional[AIOKafkaProducer] = None
        
        # ClickHouse
        self.clickhouse_client = None
        
        # Configure logger
        logger.add(
            "logs/predictive_inference_{time}.log",
            rotation="100 MB",
            retention="7 days",
            level="INFO"
        )
    
    def load_model(self):
        """Load trained ML model"""
        try:
            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
            
            logger.info(f"📦 Loading model from: {MODEL_PATH}")
            model_data = joblib.load(MODEL_PATH)
            
            self.model = model_data['model']
            self.model_metadata = {
                'version': model_data.get('version', '1.0.0'),
                'trained_at': model_data.get('trained_at', 'unknown'),
                'model_type': model_data.get('model_type', 'unknown')
            }
            
            logger.info(f"✅ Model loaded successfully!")
            logger.info(f"   Version: {self.model_metadata['version']}")
            logger.info(f"   Type: {self.model_metadata['model_type']}")
            logger.info(f"   Trained: {self.model_metadata['trained_at']}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise
    
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
        except Exception as e:
            logger.error(f"❌ Failed to connect to ClickHouse: {e}")
            raise
    
    async def start(self):
        """Start the predictive inference pipeline"""
        self.running = True
        
        # Load ML model
        self.load_model()
        
        # Connect to ClickHouse
        self.connect_clickhouse()
        
        # Initialize Kafka consumer
        self.consumer = AIOKafkaConsumer(
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        # Initialize Kafka producers
        self.predictions_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        self.alerts_producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        await self.consumer.start()
        await self.predictions_producer.start()
        await self.alerts_producer.start()
        
        logger.info("🚀 Predictive Inference Consumer started")
        logger.info(f"📥 Consuming from: {KAFKA_INPUT_TOPIC}")
        logger.info(f"📤 Publishing predictions to: {KAFKA_PREDICTIONS_TOPIC}")
        logger.info(f"🚨 Publishing alerts to: {KAFKA_ALERTS_TOPIC}")
        logger.info(f"⚡ Batch size: {BATCH_SIZE}, Timeout: {BATCH_TIMEOUT}s")
        logger.info(f"🎯 Alert threshold: {ALERT_THRESHOLD}")
        
        # Start background tasks
        asyncio.create_task(self.batch_timeout_monitor())
        asyncio.create_task(self.print_stats())
        
        # Main consumption loop
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_message(message.value)
                self.stats.messages_consumed += 1
                
                # Batch inference
                if len(self.batch) >= BATCH_SIZE:
                    await self.run_batch_inference()
        
        except Exception as e:
            logger.error(f"❌ Error in consumption loop: {e}", exc_info=True)
        finally:
            await self.shutdown()
    
    async def process_message(self, telemetry: Dict):
        """Process incoming telemetry message"""
        try:
            # Extract features needed for prediction
            features = {
                'vehicle_id': telemetry['vehicle_id'],
                'timestamp': telemetry['timestamp'],
                'engine_rpm': telemetry.get('engine_rpm', 0),
                'engine_temp': telemetry.get('engine_temp', 0),
                'vibration': telemetry.get('vibration', 0),
                'speed': telemetry.get('speed', 0),
                'fuel_level': telemetry.get('fuel_level', 0),
                'battery_voltage': telemetry.get('battery_voltage', 0)
            }
            
            # Extract rolling averages (from Phase 1 enrichment)
            rolling_avgs = telemetry.get('rolling_averages', {})
            features['rolling_avg_rpm'] = rolling_avgs.get('engine_rpm_avg', features['engine_rpm'])
            features['rolling_avg_temp'] = rolling_avgs.get('engine_temp_avg', features['engine_temp'])
            features['rolling_avg_vibration'] = rolling_avgs.get('vibration_avg', features['vibration'])
            features['rolling_avg_speed'] = rolling_avgs.get('speed_avg', features['speed'])
            
            # Add to batch
            self.batch.append(features)
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to process message: {e}")
            self.stats.errors += 1
    
    async def run_batch_inference(self):
        """Run ML inference on batch of telemetry"""
        if not self.batch:
            return
        
        try:
            batch_size = len(self.batch)
            
            # Prepare feature matrix
            X = np.array([[
                record[col] for col in FEATURE_COLUMNS
            ] for record in self.batch])
            
            # Run inference
            probabilities = self.model.predict_proba(X)[:, 1]
            predictions = self.model.predict(X)
            
            # Process each prediction
            results = []
            alerts = []
            
            for i, record in enumerate(self.batch):
                probability = float(probabilities[i])
                prediction = int(predictions[i])
                
                # Determine health status
                if probability >= 0.8:
                    health_status = "Critical"
                    reason = self.generate_failure_reason(record, "critical")
                elif probability >= 0.5:
                    health_status = "Warning"
                    reason = self.generate_failure_reason(record, "warning")
                else:
                    health_status = "Healthy"
                    reason = "All systems normal"
                
                # Parse timestamp
                try:
                    ts = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))
                except:
                    ts = datetime.now()
                
                # Create prediction result
                result = PredictionResult(
                    vehicle_id=record['vehicle_id'],
                    timestamp=ts,
                    failure_probability=probability,
                    health_status=health_status,
                    engine_temp=record['engine_temp'],
                    vibration=record['vibration'],
                    engine_rpm=record['engine_rpm'],
                    speed=record['speed'],
                    fuel_level=record['fuel_level'],
                    battery_voltage=record['battery_voltage'],
                    reason=reason,
                    model_version=self.model_metadata['version']
                )
                
                results.append(result)
                
                # Generate alert if needed
                if probability >= ALERT_THRESHOLD:
                    severity = "CRITICAL" if probability >= 0.8 else "WARNING"
                    alert = AlertRecord(
                        vehicle_id=record['vehicle_id'],
                        timestamp=ts,
                        failure_probability=probability,
                        health_status=health_status,
                        reason=reason,
                        severity=severity
                    )
                    alerts.append(alert)
            
            # Publish results
            await self.publish_predictions(results)
            
            # Publish alerts
            if alerts:
                await self.publish_alerts(alerts)
            
            # Insert into ClickHouse
            await self.insert_to_clickhouse(results, alerts)
            
            # Update stats
            self.stats.predictions_made += batch_size
            self.stats.alerts_generated += len(alerts)
            
            # Clear batch
            self.batch.clear()
            self.last_batch_time = asyncio.get_event_loop().time()
            
            logger.debug(f"✅ Processed batch of {batch_size} records, generated {len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"❌ Batch inference failed: {e}", exc_info=True)
            self.stats.errors += 1
            self.batch.clear()
    
    def generate_failure_reason(self, record: Dict, severity: str) -> str:
        """Generate human-readable failure reason"""
        reasons = []
        
        if record['engine_temp'] > 100:
            reasons.append(f"High engine temp ({record['engine_temp']:.1f}°C)")
        if record['vibration'] > 3.0:
            reasons.append(f"Excessive vibration ({record['vibration']:.1f})")
        if record['engine_rpm'] > 5000:
            reasons.append(f"High RPM ({record['engine_rpm']})")
        if record['engine_rpm'] < 500 and record['speed'] > 10:
            reasons.append(f"Engine stalling (RPM: {record['engine_rpm']})")
        if record['battery_voltage'] < 11.0:
            reasons.append(f"Low battery ({record['battery_voltage']:.1f}V)")
        if record['fuel_level'] < 10:
            reasons.append(f"Low fuel ({record['fuel_level']:.1f}%)")
        
        if not reasons:
            if severity == "critical":
                reasons.append("Multiple sensor anomalies detected")
            else:
                reasons.append("Elevated sensor readings")
        
        return " | ".join(reasons)
    
    async def publish_predictions(self, predictions: List[PredictionResult]):
        """Publish predictions to Kafka"""
        try:
            for pred in predictions:
                message = {
                    'vehicle_id': pred.vehicle_id,
                    'timestamp': pred.timestamp.isoformat(),
                    'failure_probability': pred.failure_probability,
                    'health_status': pred.health_status,
                    'reason': pred.reason,
                    'model_version': pred.model_version,
                    'predicted_at': datetime.now().isoformat()
                }
                
                await self.predictions_producer.send(
                    KAFKA_PREDICTIONS_TOPIC,
                    value=message
                )
            
            self.stats.kafka_publishes += len(predictions)
            
        except Exception as e:
            logger.error(f"❌ Failed to publish predictions: {e}")
            self.stats.errors += 1
    
    async def publish_alerts(self, alerts: List[AlertRecord]):
        """Publish alerts to Kafka"""
        try:
            for alert in alerts:
                message = {
                    'vehicle_id': alert.vehicle_id,
                    'timestamp': alert.timestamp.isoformat(),
                    'failure_probability': alert.failure_probability,
                    'health_status': alert.health_status,
                    'reason': alert.reason,
                    'severity': alert.severity,
                    'created_at': datetime.now().isoformat()
                }
                
                await self.alerts_producer.send(
                    KAFKA_ALERTS_TOPIC,
                    value=message
                )
            
            logger.info(f"🚨 Published {len(alerts)} alerts")
            
        except Exception as e:
            logger.error(f"❌ Failed to publish alerts: {e}")
            self.stats.errors += 1
    
    async def insert_to_clickhouse(self, predictions: List[PredictionResult], alerts: List[AlertRecord]):
        """Insert predictions and alerts into ClickHouse"""
        try:
            # Insert predictions
            if predictions:
                pred_data = [
                    (
                        pred.vehicle_id,
                        pred.timestamp,
                        pred.failure_probability,
                        pred.health_status,
                        pred.engine_temp,
                        pred.vibration,
                        pred.engine_rpm,
                        pred.speed,
                        pred.fuel_level,
                        pred.battery_voltage,
                        pred.reason,
                        pred.model_version,
                        datetime.now()
                    )
                    for pred in predictions
                ]
                
                self.clickhouse_client.execute(
                    """
                    INSERT INTO vehicle_predictions
                    (vehicle_id, timestamp, failure_probability, health_status,
                     engine_temp, vibration, engine_rpm, speed, fuel_level,
                     battery_voltage, reason, model_version, predicted_at)
                    VALUES
                    """,
                    pred_data
                )
                
                self.stats.db_inserts += len(predictions)
            
            # Insert alerts
            if alerts:
                alert_data = [
                    (
                        alert.vehicle_id,
                        alert.timestamp,
                        alert.failure_probability,
                        alert.health_status,
                        alert.reason,
                        alert.severity,
                        datetime.now()
                    )
                    for alert in alerts
                ]
                
                self.clickhouse_client.execute(
                    """
                    INSERT INTO vehicle_alerts
                    (vehicle_id, timestamp, failure_probability, health_status,
                     reason, severity, created_at)
                    VALUES
                    """,
                    alert_data
                )
            
        except Exception as e:
            logger.error(f"❌ Failed to insert into ClickHouse: {e}")
            self.stats.errors += 1
    
    async def batch_timeout_monitor(self):
        """Monitor batch timeout and flush if exceeded"""
        while self.running:
            await asyncio.sleep(1)
            
            current_time = asyncio.get_event_loop().time()
            time_since_last_batch = current_time - self.last_batch_time
            
            if self.batch and time_since_last_batch >= BATCH_TIMEOUT:
                logger.debug(f"⏱️ Batch timeout reached, flushing {len(self.batch)} records")
                await self.run_batch_inference()
    
    async def print_stats(self):
        """Print statistics periodically"""
        while self.running:
            await asyncio.sleep(10)
            
            logger.info(
                f"📊 Stats - Consumed: {self.stats.messages_consumed} | "
                f"Predictions: {self.stats.predictions_made} | "
                f"Alerts: {self.stats.alerts_generated} | "
                f"DB Inserts: {self.stats.db_inserts} | "
                f"Kafka Publishes: {self.stats.kafka_publishes} | "
                f"Errors: {self.stats.errors} | "
                f"Pending: {len(self.batch)}"
            )
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Predictive Inference Consumer...")
        self.running = False
        
        # Flush remaining batch
        if self.batch:
            logger.info(f"💾 Flushing final batch of {len(self.batch)} records...")
            await self.run_batch_inference()
        
        # Close Kafka connections
        if self.consumer:
            await self.consumer.stop()
        if self.predictions_producer:
            await self.predictions_producer.stop()
        if self.alerts_producer:
            await self.alerts_producer.stop()
        
        # Close ClickHouse connection
        if self.clickhouse_client:
            self.clickhouse_client.disconnect()
        
        logger.info("✅ Shutdown complete")
        logger.info(
            f"📊 Final Stats - Consumed: {self.stats.messages_consumed} | "
            f"Predictions: {self.stats.predictions_made} | "
            f"Alerts: {self.stats.alerts_generated}"
        )

# ============================================================================
# MAIN
# ============================================================================

async def main():
    consumer = PredictiveInferenceConsumer()
    
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
