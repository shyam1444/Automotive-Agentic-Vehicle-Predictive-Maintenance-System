"""
UEBA Agent - Phase 6
====================
Enhanced User and Entity Behavior Analytics with ElasticSearch Integration
Monitors agent behavior, detects anomalies using PyOD, generates security alerts,
and provides comprehensive logging to ElasticSearch for visualization
"""

import os
import sys
import asyncio
import signal
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import numpy as np

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient
from elasticsearch import AsyncElasticsearch
from loguru import logger
from dotenv import load_dotenv

# Anomaly detection
from pyod.models.iforest import IForest
from pyod.models.lof import LOF
from sklearn.preprocessing import StandardScaler

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Kafka
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_INPUT_TOPIC = os.getenv('KAFKA_ACTIVITY_LOG_TOPIC', 'agent_activity_log')
KAFKA_OUTPUT_TOPIC = os.getenv('KAFKA_SECURITY_ALERTS_TOPIC', 'security_alerts')
KAFKA_GROUP_ID = os.getenv('UEBA_CONSUMER_GROUP', 'ueba_agent_group')

# MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

# ElasticSearch (NEW in Phase 6)
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost:9200')
ELASTICSEARCH_INDEX_ACTIVITY = 'agent_activity_logs'
ELASTICSEARCH_INDEX_ALERTS = 'security_alerts'

AGENT_ID = 'UEBA_001'
HEARTBEAT_INTERVAL = 30

# Behavioral analysis configuration
OBSERVATION_WINDOW = timedelta(minutes=5)   # Window for feature extraction (shortened for real-time)
TRAINING_WINDOW = timedelta(hours=2)        # Window for baseline training
MIN_SAMPLES_FOR_TRAINING = 50               # Minimum samples before training
ANOMALY_THRESHOLD = 0.7                     # Anomaly score threshold (0-1)
CONTAMINATION = 0.1                         # Expected anomaly rate (10%)

# Feature extraction intervals
FEATURE_EXTRACTION_INTERVAL = 60  # seconds

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class AgentBehavior:
    agent_id: str
    window_start: datetime
    window_end: datetime
    features: Dict[str, float]

@dataclass
class SecurityAnomaly:
    anomaly_id: str
    agent_id: str
    anomaly_score: float
    deviation_metrics: Dict[str, any]
    severity: str
    recommended_action: str
    timestamp: datetime

@dataclass
class SecurityAlert:
    """Enhanced security alert for Phase 6"""
    alert_id: str
    agent_id: str
    anomaly_score: float
    metric: str
    current_value: float
    expected_range: Dict[str, float]
    deviation_sigma: float
    severity: str  # "low", "medium", "high", "critical"
    description: str
    timestamp: datetime
    model_type: str  # "isolation_forest", "lof"
    additional_context: Dict[str, any]

# ============================================================================
# BEHAVIORAL FEATURE EXTRACTOR
# ============================================================================

class BehavioralFeatureExtractor:
    """Extracts behavioral features from agent activity logs"""
    
    FEATURE_NAMES = [
        'messages_per_sec',
        'error_rate',
        'avg_processing_latency',
        'action_diversity',
        'heartbeat_regularity',
        'activity_burst_score',
        'idle_time_ratio'
    ]
    
    def __init__(self):
        self.agent_activities = defaultdict(lambda: deque(maxlen=1000))
    
    def add_activity(self, activity: Dict):
        """Add activity log"""
        agent_id = activity.get('agent_id')
        if agent_id:
            self.agent_activities[agent_id].append(activity)
    
    def extract_features(self, agent_id: str, window_start: datetime, window_end: datetime) -> Optional[Dict[str, float]]:
        """Extract behavioral features for an agent"""
        
        activities = self.agent_activities.get(agent_id, [])
        if not activities:
            return None
        
        # Filter activities in window
        window_activities = [
            a for a in activities
            if window_start <= datetime.fromisoformat(a.get('timestamp', '1970-01-01')) <= window_end
        ]
        
        if len(window_activities) < 5:  # Need minimum data
            return None
        
        # Extract features
        window_duration = (window_end - window_start).total_seconds()
        
        features = {
            'messages_per_sec': len(window_activities) / max(window_duration, 1),
            'error_rate': self._calculate_error_rate(window_activities),
            'avg_processing_latency': self._calculate_avg_latency(window_activities),
            'action_diversity': self._calculate_action_diversity(window_activities),
            'heartbeat_regularity': self._calculate_heartbeat_regularity(window_activities),
            'activity_burst_score': self._calculate_burst_score(window_activities, window_duration),
            'idle_time_ratio': self._calculate_idle_ratio(window_activities, window_duration)
        }
        
        return features
    
    def _calculate_error_rate(self, activities: List[Dict]) -> float:
        """Calculate error rate"""
        error_actions = ['error', 'failed', 'exception']
        error_count = sum(
            1 for a in activities
            if any(err in a.get('action', '').lower() for err in error_actions)
        )
        return error_count / len(activities) if activities else 0.0
    
    def _calculate_avg_latency(self, activities: List[Dict]) -> float:
        """Calculate average processing latency"""
        latencies = [a.get('latency_ms', 100) for a in activities if 'latency_ms' in a]
        return np.mean(latencies) if latencies else 100.0
    
    def _calculate_action_diversity(self, activities: List[Dict]) -> float:
        """Calculate diversity of actions (Shannon entropy)"""
        actions = [a.get('action', 'unknown') for a in activities]
        unique_actions = set(actions)
        
        if len(unique_actions) <= 1:
            return 0.0
        
        # Calculate entropy
        action_counts = np.array([actions.count(a) for a in unique_actions])
        probabilities = action_counts / len(actions)
        entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
        
        # Normalize to 0-1
        max_entropy = np.log2(len(unique_actions))
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def _calculate_heartbeat_regularity(self, activities: List[Dict]) -> float:
        """Calculate heartbeat regularity (lower is more regular)"""
        heartbeats = [
            datetime.fromisoformat(a['timestamp'])
            for a in activities
            if 'heartbeat' in a.get('action', '').lower()
        ]
        
        if len(heartbeats) < 2:
            return 1.0  # Assume irregular if insufficient data
        
        # Calculate intervals
        heartbeats.sort()
        intervals = [(heartbeats[i+1] - heartbeats[i]).total_seconds() for i in range(len(heartbeats) - 1)]
        
        # Coefficient of variation (std / mean)
        if len(intervals) > 0 and np.mean(intervals) > 0:
            cv = np.std(intervals) / np.mean(intervals)
            return min(cv, 2.0) / 2.0  # Normalize to 0-1
        
        return 1.0
    
    def _calculate_burst_score(self, activities: List[Dict], window_duration: float) -> float:
        """Calculate activity burst score"""
        if window_duration < 60:
            return 0.0
        
        # Divide window into 1-minute buckets
        bucket_count = int(window_duration / 60)
        buckets = [0] * bucket_count
        
        window_start = datetime.fromisoformat(activities[0]['timestamp'])
        
        for activity in activities:
            ts = datetime.fromisoformat(activity['timestamp'])
            bucket_idx = int((ts - window_start).total_seconds() / 60)
            if 0 <= bucket_idx < bucket_count:
                buckets[bucket_idx] += 1
        
        # Calculate burst score (coefficient of variation)
        if len(buckets) > 0 and np.mean(buckets) > 0:
            cv = np.std(buckets) / np.mean(buckets)
            return min(cv, 2.0) / 2.0  # Normalize to 0-1
        
        return 0.0
    
    def _calculate_idle_ratio(self, activities: List[Dict], window_duration: float) -> float:
        """Calculate idle time ratio"""
        if len(activities) < 2:
            return 1.0
        
        # Sort by timestamp
        sorted_activities = sorted(activities, key=lambda x: x.get('timestamp', ''))
        
        # Calculate gaps between activities
        gaps = []
        for i in range(len(sorted_activities) - 1):
            t1 = datetime.fromisoformat(sorted_activities[i]['timestamp'])
            t2 = datetime.fromisoformat(sorted_activities[i+1]['timestamp'])
            gap = (t2 - t1).total_seconds()
            gaps.append(gap)
        
        # Idle time is gaps > 60 seconds
        idle_time = sum(gap for gap in gaps if gap > 60)
        
        return min(idle_time / window_duration, 1.0)

# ============================================================================
# ANOMALY DETECTOR
# ============================================================================

class AnomalyDetector:
    """Dual-model anomaly detector: Isolation Forest + LOF"""
    
    def __init__(self):
        self.if_models = {}  # Per-agent Isolation Forest models
        self.lof_models = {}  # Per-agent LOF models (NEW in Phase 6)
        self.scalers = {}  # Per-agent scalers
        self.training_data = defaultdict(list)
        self.baseline_stats = {}
    
    def add_training_sample(self, agent_id: str, features: Dict[str, float]):
        """Add sample for training"""
        feature_vector = self._dict_to_vector(features)
        self.training_data[agent_id].append(feature_vector)
    
    def train(self, agent_id: str):
        """Train both Isolation Forest and LOF models for agent"""
        
        if agent_id not in self.training_data or len(self.training_data[agent_id]) < MIN_SAMPLES_FOR_TRAINING:
            logger.debug(f"Insufficient training data for {agent_id}: {len(self.training_data.get(agent_id, []))} samples")
            return False
        
        X = np.array(self.training_data[agent_id])
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # Train Isolation Forest
        if_model = IForest(
            contamination=CONTAMINATION,
            random_state=42,
            n_estimators=100
        )
        if_model.fit(X_scaled)
        
        # Train LOF (NEW in Phase 6)
        lof_model = LOF(
            contamination=CONTAMINATION,
            n_neighbors=min(20, len(X) - 1)
        )
        lof_model.fit(X_scaled)
        
        self.if_models[agent_id] = if_model
        self.lof_models[agent_id] = lof_model
        self.scalers[agent_id] = scaler
        
        # Calculate baseline statistics
        self.baseline_stats[agent_id] = {
            'mean': np.mean(X, axis=0).tolist(),
            'std': np.std(X, axis=0).tolist(),
            'samples': len(X)
        }
        
        logger.info(f"✅ Trained IF+LOF models for {agent_id}: {len(X)} samples")
        return True
    
    def detect_anomaly(self, agent_id: str, features: Dict[str, float]) -> Optional[Dict[str, float]]:
        """Detect anomaly using both models, returns scores from both"""
        
        if agent_id not in self.if_models:
            return None
        
        feature_vector = self._dict_to_vector(features)
        X = np.array([feature_vector])
        
        # Scale
        X_scaled = self.scalers[agent_id].transform(X)
        
        # Get Isolation Forest score
        if_score = self.if_models[agent_id].decision_function(X_scaled)[0]
        if_normalized = max(0, min(1, 1 - (if_score + 0.5)))
        
        # Get LOF score (NEW in Phase 6)
        lof_score = self.lof_models[agent_id].decision_function(X_scaled)[0]
        lof_normalized = max(0, min(1, 1 - (lof_score + 0.5)))
        
        # Return both scores
        return {
            'isolation_forest': if_normalized,
            'lof': lof_normalized,
            'combined': (if_normalized + lof_normalized) / 2
        }
    
    def calculate_deviations(self, agent_id: str, features: Dict[str, float]) -> Dict[str, float]:
        """Calculate feature deviations from baseline"""
        
        if agent_id not in self.baseline_stats:
            return {}
        
        baseline = self.baseline_stats[agent_id]
        feature_names = BehavioralFeatureExtractor.FEATURE_NAMES
        
        deviations = {}
        for i, feature_name in enumerate(feature_names):
            feature_value = features.get(feature_name, 0)
            baseline_mean = baseline['mean'][i]
            baseline_std = baseline['std'][i]
            
            if baseline_std > 0:
                # Z-score
                deviation = abs(feature_value - baseline_mean) / baseline_std
            else:
                deviation = 0.0
            
            deviations[feature_name] = deviation
        
        return deviations
    
    def _dict_to_vector(self, features: Dict[str, float]) -> List[float]:
        """Convert feature dict to vector"""
        return [features.get(name, 0.0) for name in BehavioralFeatureExtractor.FEATURE_NAMES]

# ============================================================================
# UEBA AGENT
# ============================================================================

class UEBAAgent:
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.anomalies_detected = 0
        self.errors_count = 0
        self.alerts_generated = 0  # NEW in Phase 6
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        # NEW in Phase 6: ElasticSearch client
        self.es_client: Optional[AsyncElasticsearch] = None
        
        self.feature_extractor = BehavioralFeatureExtractor()
        self.anomaly_detector = AnomalyDetector()
        
        # Enhanced logging
        logger.remove()
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>UEBA</cyan> - <level>{message}</level>",
            level="INFO"
        )
        logger.add(
            "logs/ueba_agent_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="DEBUG"
        )
        logger.add(
            "logs/security_alerts_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="90 days",
            level="WARNING",
            filter=lambda record: "SECURITY ALERT" in record["message"] or "ANOMALY" in record["message"]
        )
    
    async def start(self):
        """Start UEBA Agent"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🔒 UEBA AGENT STARTING")
        logger.info("=" * 80)
        
        await self.connect_mongodb()
        await self.init_kafka()
        await self.register_agent()
        
        asyncio.create_task(self.send_heartbeat())
        asyncio.create_task(self.periodic_analysis())
        
        logger.info("✅ UEBA Agent started")
        logger.info(f"📥 Consuming from: {KAFKA_INPUT_TOPIC}")
        logger.info(f"📤 Publishing to: {KAFKA_OUTPUT_TOPIC}")
        logger.info(f"🔍 Observation window: {OBSERVATION_WINDOW.total_seconds() / 60:.0f} minutes")
        
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_activity(message.value)
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
            KAFKA_INPUT_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset='latest',
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
        """Register agent"""
        await self.db.agent_status.update_one(
            {"agent_id": AGENT_ID},
            {"$set": {
                "agent_id": AGENT_ID,
                "agent_type": "ueba",
                "status": "active",
                "last_heartbeat": datetime.now(),
                "messages_processed": 0,
                "errors_count": 0,
                "metadata": {
                    "started_at": datetime.now().isoformat(),
                    "observation_window_minutes": OBSERVATION_WINDOW.total_seconds() / 60
                }
            }},
            upsert=True
        )
        logger.info(f"📝 Registered: {AGENT_ID}")
    
    async def process_activity(self, activity: Dict):
        """Process activity log"""
        try:
            # Add timestamp if missing
            if 'timestamp' not in activity:
                activity['timestamp'] = datetime.now().isoformat()
            
            self.feature_extractor.add_activity(activity)
            
        except Exception as e:
            logger.error(f"❌ Failed to process activity: {e}")
            self.errors_count += 1
    
    async def periodic_analysis(self):
        """Periodically analyze agent behavior"""
        
        # Wait for initial data collection
        await asyncio.sleep(120)
        
        while self.running:
            await asyncio.sleep(FEATURE_EXTRACTION_INTERVAL)
            
            try:
                await self.analyze_agents()
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}", exc_info=True)
    
    async def analyze_agents(self):
        """Analyze all agents for anomalies"""
        
        now = datetime.now()
        observation_start = now - OBSERVATION_WINDOW
        training_start = now - TRAINING_WINDOW
        
        # Get active agents
        active_agents = await self.db.agent_status.find(
            {"status": "active"},
            {"agent_id": 1}
        ).to_list(length=100)
        
        for agent_doc in active_agents:
            agent_id = agent_doc['agent_id']
            
            if agent_id == AGENT_ID:  # Don't monitor self
                continue
            
            # Extract features for observation window
            features = self.feature_extractor.extract_features(agent_id, observation_start, now)
            
            if not features:
                continue
            
            # Add to training data if in training window
            self.anomaly_detector.add_training_sample(agent_id, features)
            
            # Train model if needed
            if agent_id not in self.anomaly_detector.models:
                trained = self.anomaly_detector.train(agent_id)
                if not trained:
                    continue
            
            # Detect anomaly
            anomaly_score = self.anomaly_detector.detect_anomaly(agent_id, features)
            
            if anomaly_score is None:
                continue
            
            # Check threshold
            if anomaly_score >= ANOMALY_THRESHOLD:
                await self.handle_anomaly(agent_id, anomaly_score, features)
    
    async def handle_anomaly(self, agent_id: str, anomaly_score: float, features: Dict[str, float]):
        """Handle detected anomaly"""
        
        # Calculate deviations
        deviations = self.anomaly_detector.calculate_deviations(agent_id, features)
        
        # Find most deviated metric
        max_deviation_metric = max(deviations, key=deviations.get) if deviations else 'unknown'
        max_deviation_value = deviations.get(max_deviation_metric, 0)
        
        # Determine severity
        if anomaly_score >= 0.9 or max_deviation_value >= 5:
            severity = 'critical'
            action = f"Immediately disable {agent_id} and investigate"
        elif anomaly_score >= 0.8:
            severity = 'warning'
            action = f"Flag {agent_id} for review, increase monitoring"
        else:
            severity = 'info'
            action = f"Monitor {agent_id} closely for continued anomalies"
        
        # Create anomaly object
        anomaly = SecurityAnomaly(
            anomaly_id=f"ANOM_{datetime.now().strftime('%Y%m%d%H%M%S')}_{agent_id}",
            agent_id=agent_id,
            anomaly_score=anomaly_score,
            deviation_metrics={
                'features': features,
                'deviations': deviations,
                'max_deviation_metric': max_deviation_metric,
                'max_deviation_value': max_deviation_value
            },
            severity=severity,
            recommended_action=action,
            timestamp=datetime.now()
        )
        
        # Store in MongoDB
        anomaly_doc = {
            "anomaly_id": anomaly.anomaly_id,
            "agent_id": anomaly.agent_id,
            "anomaly_score": anomaly.anomaly_score,
            "deviation_metrics": anomaly.deviation_metrics,
            "severity": anomaly.severity,
            "recommended_action": anomaly.recommended_action,
            "timestamp": anomaly.timestamp,
            "status": "active"
        }
        
        # Check if recent anomaly exists
        recent = await self.db.alerts_history.find_one({
            "type": "security_anomaly",
            "agent_id": agent_id,
            "timestamp": {"$gte": datetime.now() - timedelta(minutes=5)}
        })
        
        if recent:
            logger.debug(f"⏭️ Recent anomaly exists for {agent_id}")
            return
        
        await self.db.alerts_history.insert_one({
            "type": "security_anomaly",
            **anomaly_doc
        })
        
        # Publish security alert
        alert_message = {
            "anomaly_id": anomaly.anomaly_id,
            "agent_id": anomaly.agent_id,
            "anomaly_score": round(anomaly.anomaly_score, 3),
            "severity": anomaly.severity,
            "metric": max_deviation_metric,
            "deviation": round(max_deviation_value, 2),
            "recommended_action": anomaly.recommended_action,
            "timestamp": anomaly.timestamp.isoformat()
        }
        
        await self.producer.send(KAFKA_OUTPUT_TOPIC, value=alert_message)
        
        self.anomalies_detected += 1
        
        logger.warning(
            f"🚨 ANOMALY DETECTED: {agent_id} | "
            f"Score: {anomaly_score:.3f} | "
            f"Metric: {max_deviation_metric} (σ={max_deviation_value:.2f}) | "
            f"Severity: {severity}"
        )
    
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
                        "metadata.anomalies_detected": self.anomalies_detected,
                        "metadata.models_trained": len(self.anomaly_detector.models)
                    }}
                )
                
                if self.messages_processed % 100 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed} | "
                        f"Anomalies: {self.anomalies_detected} | "
                        f"Models: {len(self.anomaly_detector.models)}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down UEBA Agent...")
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
        
        if self.mongo_client:
            self.mongo_client.close()
        
        logger.info("✅ UEBA Agent shut down")
        logger.info(f"📊 Final: {self.anomalies_detected} anomalies detected")

async def main():
    agent = UEBAAgent()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.start()

if __name__ == "__main__":
    asyncio.run(main())
