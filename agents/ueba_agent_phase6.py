#!/usr/bin/env python3
"""
UEBA Agent - Phase 6 Enhanced Version
======================================
User and Entity Behavior Analytics with ElasticSearch Integration

Features:
- Dual anomaly detection: Isolation Forest + LOF
- ElasticSearch integration for long-term log storage
- Enhanced security alert generation
- Real-time agent behavior monitoring
- Kibana/Grafana visualization support
"""

import os
import sys
import asyncio
import signal
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import numpy as np
import pandas as pd

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
KAFKA_GROUP_ID = os.getenv('UEBA_CONSUMER_GROUP', 'ueba_phase6_group')

# MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://admin:mongodb_pass@localhost:27017/')
MONGODB_DATABASE = os.getenv('MONGODB_DATABASE', 'agents_db')

# ElasticSearch
ELASTICSEARCH_HOST = os.getenv('ELASTICSEARCH_HOST', 'localhost:9200')
ELASTICSEARCH_INDEX_ACTIVITY = 'agent_activity_logs'
ELASTICSEARCH_INDEX_ALERTS = 'security_alerts'

AGENT_ID = 'UEBA_PHASE6_001'
HEARTBEAT_INTERVAL = 30

# Behavioral analysis
OBSERVATION_WINDOW = timedelta(minutes=5)
TRAINING_WINDOW = timedelta(hours=2)
MIN_SAMPLES_FOR_TRAINING = 50
ANOMALY_THRESHOLD = 0.7
CONTAMINATION = 0.1

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
class SecurityAlert:
    """Enhanced security alert"""
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
    model_type: str  # "isolation_forest", "lof", "combined"
    additional_context: Dict[str, Any]

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
            if window_start <= self._parse_timestamp(a.get('timestamp')) <= window_end
        ]
        
        if len(window_activities) < 5:
            return None
        
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
    
    def _parse_timestamp(self, ts_str) -> datetime:
        """Parse timestamp string"""
        if isinstance(ts_str, datetime):
            return ts_str
        try:
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        except:
            return datetime.now(timezone.utc)
    
    def _calculate_error_rate(self, activities: List[Dict]) -> float:
        """Calculate error rate"""
        error_keywords = ['error', 'failed', 'exception', 'critical']
        error_count = sum(
            1 for a in activities
            if any(kw in str(a.get('action', '')).lower() for kw in error_keywords)
        )
        return error_count / len(activities) if activities else 0.0
    
    def _calculate_avg_latency(self, activities: List[Dict]) -> float:
        """Calculate average processing latency"""
        latencies = [a.get('latency_ms', 100) for a in activities if 'latency_ms' in a]
        return float(np.mean(latencies)) if latencies else 100.0
    
    def _calculate_action_diversity(self, activities: List[Dict]) -> float:
        """Calculate Shannon entropy of actions"""
        actions = [a.get('action', 'unknown') for a in activities]
        unique_actions = set(actions)
        
        if len(unique_actions) <= 1:
            return 0.0
        
        action_counts = np.array([actions.count(a) for a in unique_actions])
        probabilities = action_counts / len(actions)
        entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
        
        max_entropy = np.log2(len(unique_actions))
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def _calculate_heartbeat_regularity(self, activities: List[Dict]) -> float:
        """Calculate heartbeat regularity (CV of intervals)"""
        heartbeats = [
            self._parse_timestamp(a['timestamp'])
            for a in activities
            if 'heartbeat' in str(a.get('action', '')).lower()
        ]
        
        if len(heartbeats) < 2:
            return 1.0
        
        heartbeats.sort()
        intervals = [(heartbeats[i+1] - heartbeats[i]).total_seconds() for i in range(len(heartbeats) - 1)]
        
        if len(intervals) > 0 and np.mean(intervals) > 0:
            cv = np.std(intervals) / np.mean(intervals)
            return min(float(cv), 2.0) / 2.0
        
        return 1.0
    
    def _calculate_burst_score(self, activities: List[Dict], window_duration: float) -> float:
        """Calculate activity burst score"""
        if window_duration < 60:
            return 0.0
        
        bucket_count = int(window_duration / 60)
        buckets = [0] * max(bucket_count, 1)
        
        window_start = self._parse_timestamp(activities[0]['timestamp'])
        
        for activity in activities:
            ts = self._parse_timestamp(activity['timestamp'])
            bucket_idx = int((ts - window_start).total_seconds() / 60)
            if 0 <= bucket_idx < bucket_count:
                buckets[bucket_idx] += 1
        
        if len(buckets) > 0 and np.mean(buckets) > 0:
            cv = np.std(buckets) / np.mean(buckets)
            return min(float(cv), 2.0) / 2.0
        
        return 0.0
    
    def _calculate_idle_ratio(self, activities: List[Dict], window_duration: float) -> float:
        """Calculate idle time ratio"""
        if len(activities) < 2:
            return 1.0
        
        sorted_activities = sorted(activities, key=lambda x: self._parse_timestamp(x.get('timestamp')))
        
        gaps = []
        for i in range(len(sorted_activities) - 1):
            t1 = self._parse_timestamp(sorted_activities[i]['timestamp'])
            t2 = self._parse_timestamp(sorted_activities[i+1]['timestamp'])
            gap = (t2 - t1).total_seconds()
            gaps.append(gap)
        
        idle_time = sum(gap for gap in gaps if gap > 60)
        
        return min(float(idle_time / window_duration), 1.0)

# ============================================================================
# DUAL-MODEL ANOMALY DETECTOR
# ============================================================================

class DualAnomalyDetector:
    """Dual-model anomaly detector: Isolation Forest + LOF"""
    
    def __init__(self):
        self.if_models = {}  # Isolation Forest models
        self.lof_models = {}  # Local Outlier Factor models
        self.scalers = {}
        self.training_data = defaultdict(list)
        self.baseline_stats = {}
    
    def add_training_sample(self, agent_id: str, features: Dict[str, float]):
        """Add sample for training"""
        feature_vector = self._dict_to_vector(features)
        self.training_data[agent_id].append(feature_vector)
    
    def train(self, agent_id: str) -> bool:
        """Train both models for agent"""
        
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
        
        # Train LOF
        lof_model = LOF(
            contamination=CONTAMINATION,
            n_neighbors=min(20, len(X) - 1)
        )
        lof_model.fit(X_scaled)
        
        self.if_models[agent_id] = if_model
        self.lof_models[agent_id] = lof_model
        self.scalers[agent_id] = scaler
        
        # Baseline statistics
        self.baseline_stats[agent_id] = {
            'mean': np.mean(X, axis=0).tolist(),
            'std': np.std(X, axis=0).tolist(),
            'samples': len(X)
        }
        
        logger.info(f"✅ Trained IF+LOF models for {agent_id}: {len(X)} samples")
        return True
    
    def detect_anomaly(self, agent_id: str, features: Dict[str, float]) -> Optional[Dict[str, float]]:
        """Detect anomaly using both models"""
        
        if agent_id not in self.if_models:
            return None
        
        feature_vector = self._dict_to_vector(features)
        X = np.array([feature_vector])
        
        X_scaled = self.scalers[agent_id].transform(X)
        
        # Isolation Forest score
        if_score = self.if_models[agent_id].decision_function(X_scaled)[0]
        if_normalized = max(0, min(1, 1 - (if_score + 0.5)))
        
        # LOF score
        lof_score = self.lof_models[agent_id].decision_function(X_scaled)[0]
        lof_normalized = max(0, min(1, 1 - (lof_score + 0.5)))
        
        return {
            'isolation_forest': float(if_normalized),
            'lof': float(lof_normalized),
            'combined': float((if_normalized + lof_normalized) / 2)
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
                deviation = abs(feature_value - baseline_mean) / baseline_std
            else:
                deviation = 0.0
            
            deviations[feature_name] = float(deviation)
        
        return deviations
    
    def _dict_to_vector(self, features: Dict[str, float]) -> List[float]:
        """Convert feature dict to vector"""
        return [features.get(name, 0.0) for name in BehavioralFeatureExtractor.FEATURE_NAMES]

# ============================================================================
# UEBA AGENT - PHASE 6
# ============================================================================

class UEBAAgentPhase6:
    """Enhanced UEBA Agent with ElasticSearch integration"""
    
    def __init__(self):
        self.running = False
        self.messages_processed = 0
        self.anomalies_detected = 0
        self.alerts_generated = 0
        self.errors_count = 0
        
        # Kafka
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.producer: Optional[AIOKafkaProducer] = None
        
        # MongoDB
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.db = None
        
        # ElasticSearch (NEW in Phase 6)
        self.es_client: Optional[AsyncElasticsearch] = None
        
        # Components
        self.feature_extractor = BehavioralFeatureExtractor()
        self.anomaly_detector = DualAnomalyDetector()
        
        self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging"""
        logger.remove()
        
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>UEBA-P6</cyan> - <level>{message}</level>",
            level="INFO"
        )
        
        logger.add(
            "logs/ueba_phase6_{time:YYYY-MM-DD}.log",
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
    
    # ========================================================================
    # CONNECTIONS
    # ========================================================================
    
    async def connect_mongodb(self):
        """Connect to MongoDB"""
        logger.info(f"🔌 Connecting to MongoDB...")
        
        try:
            self.mongo_client = AsyncIOMotorClient(MONGODB_URI)
            self.db = self.mongo_client[MONGODB_DATABASE]
            await self.db.command('ping')
            logger.success("✅ MongoDB connected")
            
            await self.register_agent()
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            raise
    
    async def connect_kafka(self):
        """Initialize Kafka"""
        logger.info(f"🔌 Connecting to Kafka at {KAFKA_BOOTSTRAP}...")
        
        try:
            self.consumer = AIOKafkaConsumer(
                KAFKA_INPUT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id=KAFKA_GROUP_ID,
                auto_offset_reset='latest',
                value_deserializer=lambda m: json.loads(m.decode('utf-8'))
            )
            
            self.producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            
            await self.consumer.start()
            await self.producer.start()
            
            logger.success(f"✅ Kafka connected - Input: {KAFKA_INPUT_TOPIC}, Output: {KAFKA_OUTPUT_TOPIC}")
        except Exception as e:
            logger.error(f"❌ Kafka connection failed: {e}")
            raise
    
    async def connect_elasticsearch(self):
        """Connect to ElasticSearch"""
        logger.info(f"🔌 Connecting to ElasticSearch at {ELASTICSEARCH_HOST}...")
        
        try:
            self.es_client = AsyncElasticsearch(
                [f'http://{ELASTICSEARCH_HOST}'],
                request_timeout=30
            )
            
            info = await self.es_client.info()
            logger.success(f"✅ ElasticSearch connected - Version: {info['version']['number']}")
            
            await self.create_elasticsearch_indices()
        except Exception as e:
            logger.warning(f"⚠️  ElasticSearch connection failed: {e}")
            logger.info("UEBA will continue without ElasticSearch")
            self.es_client = None
    
    async def create_elasticsearch_indices(self):
        """Create ElasticSearch indices"""
        if not self.es_client:
            return
        
        activity_mapping = {
            "mappings": {
                "properties": {
                    "agent_id": {"type": "keyword"},
                    "action": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "latency_ms": {"type": "float"},
                    "status": {"type": "keyword"}
                }
            }
        }
        
        alerts_mapping = {
            "mappings": {
                "properties": {
                    "alert_id": {"type": "keyword"},
                    "agent_id": {"type": "keyword"},
                    "anomaly_score": {"type": "float"},
                    "metric": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "description": {"type": "text"}
                }
            }
        }
        
        try:
            if not await self.es_client.indices.exists(index=ELASTICSEARCH_INDEX_ACTIVITY):
                await self.es_client.indices.create(index=ELASTICSEARCH_INDEX_ACTIVITY, body=activity_mapping)
                logger.info(f"Created index: {ELASTICSEARCH_INDEX_ACTIVITY}")
            
            if not await self.es_client.indices.exists(index=ELASTICSEARCH_INDEX_ALERTS):
                await self.es_client.indices.create(index=ELASTICSEARCH_INDEX_ALERTS, body=alerts_mapping)
                logger.info(f"Created index: {ELASTICSEARCH_INDEX_ALERTS}")
        except Exception as e:
            logger.error(f"Failed to create ES indices: {e}")
    
    async def register_agent(self):
        """Register UEBA agent"""
        try:
            await self.db.agent_status.update_one(
                {"agent_id": AGENT_ID},
                {"$set": {
                    "agent_id": AGENT_ID,
                    "agent_type": "ueba_phase6",
                    "status": "active",
                    "last_heartbeat": datetime.now(timezone.utc),
                    "started_at": datetime.now(timezone.utc),
                    "configuration": {
                        "observation_window_minutes": OBSERVATION_WINDOW.total_seconds() / 60,
                        "anomaly_threshold": ANOMALY_THRESHOLD,
                        "contamination": CONTAMINATION,
                        "elasticsearch_enabled": self.es_client is not None
                    }
                }},
                upsert=True
            )
            logger.info(f"📝 Registered: {AGENT_ID}")
        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
    
    # ========================================================================
    # ACTIVITY PROCESSING
    # ========================================================================
    
    async def process_activity(self, activity: Dict):
        """Process incoming activity log"""
        try:
            if 'timestamp' not in activity:
                activity['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            self.feature_extractor.add_activity(activity)
            
            # Index to ElasticSearch
            if self.es_client:
                await self.index_activity_to_es(activity)
            
            self.messages_processed += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to process activity: {e}")
            self.errors_count += 1
    
    async def index_activity_to_es(self, activity: Dict):
        """Index activity to ElasticSearch"""
        try:
            await self.es_client.index(
                index=ELASTICSEARCH_INDEX_ACTIVITY,
                document=activity
            )
        except Exception as e:
            logger.debug(f"Failed to index activity to ES: {e}")
    
    # ========================================================================
    # ANOMALY ANALYSIS
    # ========================================================================
    
    async def analyze_agents(self):
        """Analyze all agents for anomalies"""
        
        now = datetime.now(timezone.utc)
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
            
            # Extract features
            features = self.feature_extractor.extract_features(agent_id, observation_start, now)
            
            if not features:
                continue
            
            # Add to training data
            self.anomaly_detector.add_training_sample(agent_id, features)
            
            # Train model if needed
            if agent_id not in self.anomaly_detector.if_models:
                trained = self.anomaly_detector.train(agent_id)
                if not trained:
                    continue
            
            # Detect anomaly
            scores = self.anomaly_detector.detect_anomaly(agent_id, features)
            
            if not scores:
                continue
            
            # Check threshold (combined score)
            if scores['combined'] >= ANOMALY_THRESHOLD:
                await self.handle_anomaly(agent_id, scores, features)
    
    async def handle_anomaly(self, agent_id: str, scores: Dict[str, float], features: Dict[str, float]):
        """Handle detected anomaly"""
        
        deviations = self.anomaly_detector.calculate_deviations(agent_id, features)
        
        # Find most deviated metric
        max_metric = max(deviations, key=deviations.get) if deviations else 'unknown'
        max_deviation = deviations.get(max_metric, 0)
        
        # Determine severity
        anomaly_score = scores['combined']
        if anomaly_score >= 0.9 or max_deviation >= 5:
            severity = 'critical'
        elif anomaly_score >= 0.8:
            severity = 'high'
        elif anomaly_score >= 0.7:
            severity = 'medium'
        else:
            severity = 'low'
        
        # Check for recent alerts
        recent = await self.db.security_alerts_history.find_one({
            "agent_id": agent_id,
            "timestamp": {"$gte": datetime.now(timezone.utc) - timedelta(minutes=5)}
        })
        
        if recent:
            logger.debug(f"⏭️  Recent alert exists for {agent_id}")
            return
        
        # Create alert
        alert = SecurityAlert(
            alert_id=f"ALERT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{agent_id}",
            agent_id=agent_id,
            anomaly_score=anomaly_score,
            metric=max_metric,
            current_value=features.get(max_metric, 0),
            expected_range={
                "mean": self.anomaly_detector.baseline_stats[agent_id]['mean'][
                    BehavioralFeatureExtractor.FEATURE_NAMES.index(max_metric)
                ],
                "std": self.anomaly_detector.baseline_stats[agent_id]['std'][
                    BehavioralFeatureExtractor.FEATURE_NAMES.index(max_metric)
                ]
            },
            deviation_sigma=max_deviation,
            severity=severity,
            description=self.generate_description(agent_id, max_metric, max_deviation),
            timestamp=datetime.now(timezone.utc),
            model_type="combined",
            additional_context={
                "if_score": scores['isolation_forest'],
                "lof_score": scores['lof'],
                "features": features,
                "deviations": deviations
            }
        )
        
        # Store and publish
        await self.store_alert(alert)
        await self.publish_alert(alert)
        await self.index_alert_to_es(alert)
        
        self.anomalies_detected += 1
        self.alerts_generated += 1
        
        logger.warning(
            f"🚨 SECURITY ALERT - {agent_id} | "
            f"Score: {anomaly_score:.3f} | "
            f"Metric: {max_metric} (σ={max_deviation:.2f}) | "
            f"Severity: {severity}"
        )
    
    def generate_description(self, agent_id: str, metric: str, deviation: float) -> str:
        """Generate alert description"""
        return (
            f"Agent {agent_id} showing anomalous behavior in {metric}. "
            f"Deviation: {deviation:.1f} standard deviations from baseline. "
            f"Immediate investigation recommended."
        )
    
    async def store_alert(self, alert: SecurityAlert):
        """Store alert in MongoDB"""
        try:
            await self.db.security_alerts_history.insert_one(asdict(alert))
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
    
    async def publish_alert(self, alert: SecurityAlert):
        """Publish alert to Kafka"""
        try:
            await self.producer.send(KAFKA_OUTPUT_TOPIC, value=asdict(alert))
        except Exception as e:
            logger.error(f"Failed to publish alert: {e}")
    
    async def index_alert_to_es(self, alert: SecurityAlert):
        """Index alert to ElasticSearch"""
        if not self.es_client:
            return
        
        try:
            await self.es_client.index(
                index=ELASTICSEARCH_INDEX_ALERTS,
                document=asdict(alert)
            )
        except Exception as e:
            logger.debug(f"Failed to index alert to ES: {e}")
    
    # ========================================================================
    # BACKGROUND TASKS
    # ========================================================================
    
    async def send_heartbeat(self):
        """Send heartbeat"""
        while self.running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            
            try:
                await self.db.agent_status.update_one(
                    {"agent_id": AGENT_ID},
                    {"$set": {
                        "status": "active",
                        "last_heartbeat": datetime.now(timezone.utc),
                        "messages_processed": self.messages_processed,
                        "anomalies_detected": self.anomalies_detected,
                        "alerts_generated": self.alerts_generated,
                        "errors_count": self.errors_count,
                        "models_trained": len(self.anomaly_detector.if_models)
                    }}
                )
                
                if self.messages_processed % 100 == 0 and self.messages_processed > 0:
                    logger.info(
                        f"📊 Stats - Processed: {self.messages_processed:,} | "
                        f"Anomalies: {self.anomalies_detected} | "
                        f"Alerts: {self.alerts_generated} | "
                        f"Models: {len(self.anomaly_detector.if_models)}"
                    )
            except Exception as e:
                logger.error(f"❌ Heartbeat failed: {e}")
    
    async def periodic_analysis(self):
        """Periodic behavior analysis"""
        await asyncio.sleep(120)  # Initial wait
        
        while self.running:
            await asyncio.sleep(FEATURE_EXTRACTION_INTERVAL)
            
            try:
                await self.analyze_agents()
            except Exception as e:
                logger.error(f"❌ Analysis failed: {e}", exc_info=True)
    
    # ========================================================================
    # MAIN LOOP
    # ========================================================================
    
    async def run(self):
        """Main run loop"""
        self.running = True
        
        logger.info("=" * 80)
        logger.info("🔒 UEBA AGENT PHASE 6 - STARTING")
        logger.info("=" * 80)
        logger.info(f"Agent ID: {AGENT_ID}")
        logger.info(f"Observation Window: {OBSERVATION_WINDOW.total_seconds() / 60:.0f} minutes")
        logger.info(f"Anomaly Threshold: {ANOMALY_THRESHOLD}")
        logger.info(f"Contamination: {CONTAMINATION}")
        
        await self.connect_mongodb()
        await self.connect_kafka()
        await self.connect_elasticsearch()
        
        logger.success("✅ UEBA Agent Phase 6 is operational")
        logger.info("Press Ctrl+C to stop...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.consume_activities()),
            asyncio.create_task(self.send_heartbeat()),
            asyncio.create_task(self.periodic_analysis())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Tasks cancelled")
    
    async def consume_activities(self):
        """Consume activity logs"""
        try:
            async for message in self.consumer:
                if not self.running:
                    break
                
                await self.process_activity(message.value)
        except Exception as e:
            logger.error(f"❌ Consumer error: {e}", exc_info=True)
    
    async def shutdown(self):
        """Shutdown"""
        logger.info("🛑 Shutting down UEBA Agent Phase 6...")
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
        if self.es_client:
            await self.es_client.close()
        if self.mongo_client:
            self.mongo_client.close()
        
        logger.success("✅ UEBA Agent Phase 6 shut down")
        logger.info(f"📊 Final: {self.anomalies_detected} anomalies, {self.alerts_generated} alerts")

# ============================================================================
# MAIN
# ============================================================================

async def main():
    agent = UEBAAgentPhase6()
    
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        asyncio.create_task(agent.shutdown())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    await agent.run()

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
