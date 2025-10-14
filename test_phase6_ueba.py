#!/usr/bin/env python3
"""
Phase 6 Test Activity Generator
Generates test agent activity for UEBA anomaly detection testing
"""

import asyncio
import json
import random
from datetime import datetime, timezone
from aiokafka import AIOKafkaProducer

KAFKA_BOOTSTRAP = 'localhost:9092'
KAFKA_TOPIC = 'agent_activity_log'

async def generate_normal_activity(producer, agent_id, count=100):
    """Generate normal agent activity"""
    print(f"📤 Generating {count} normal activities for {agent_id}...")
    
    actions = [
        "process_alert", "send_notification", "update_status",
        "query_database", "calculate_metrics", "heartbeat"
    ]
    
    for i in range(count):
        activity = {
            "agent_id": agent_id,
            "action": random.choice(actions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(30, 100),
            "status": "success" if random.random() > 0.05 else "error",  # 5% error rate
            "details": {
                "message_id": f"MSG_{i:06d}",
                "priority": random.choice(["low", "medium", "high"])
            }
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        
        if (i + 1) % 25 == 0:
            print(f"  ✓ Sent {i + 1}/{count} messages...")
        
        await asyncio.sleep(0.05)  # 20 msg/sec
    
    print(f"✅ Normal activity generation complete for {agent_id}")

async def generate_high_latency_anomaly(producer, agent_id, count=50):
    """Generate high latency anomaly"""
    print(f"⚠️  Generating {count} high-latency anomalies for {agent_id}...")
    
    for i in range(count):
        activity = {
            "agent_id": agent_id,
            "action": "slow_database_query",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(500, 1500),  # Very high latency!
            "status": "success",
            "details": {
                "query_type": "complex_aggregation",
                "records_scanned": random.randint(10000, 100000)
            }
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        await asyncio.sleep(0.1)
    
    print(f"✅ High-latency anomaly complete for {agent_id}")

async def generate_high_error_rate_anomaly(producer, agent_id, count=50):
    """Generate high error rate anomaly"""
    print(f"⚠️  Generating {count} high-error-rate anomalies for {agent_id}...")
    
    for i in range(count):
        activity = {
            "agent_id": agent_id,
            "action": "failing_operation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(50, 150),
            "status": "error" if random.random() > 0.3 else "success",  # 70% error rate!
            "details": {
                "error_code": "CONNECTION_TIMEOUT" if random.random() > 0.5 else "INVALID_RESPONSE"
            }
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        await asyncio.sleep(0.1)
    
    print(f"✅ High-error-rate anomaly complete for {agent_id}")

async def generate_burst_anomaly(producer, agent_id, count=100):
    """Generate activity burst anomaly"""
    print(f"⚠️  Generating {count} burst anomalies for {agent_id}...")
    
    for i in range(count):
        activity = {
            "agent_id": agent_id,
            "action": "rapid_fire_action",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(10, 30),
            "status": "success",
            "details": {
                "burst_sequence": i
            }
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        await asyncio.sleep(0.01)  # 100 msg/sec - very fast burst!
    
    print(f"✅ Burst anomaly complete for {agent_id}")

async def generate_idle_anomaly(producer, agent_id):
    """Generate unusual idle period"""
    print(f"⚠️  Generating idle anomaly for {agent_id}...")
    
    # Send a few activities with long gaps
    for i in range(5):
        activity = {
            "agent_id": agent_id,
            "action": "sporadic_heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(40, 80),
            "status": "success"
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        print(f"  Sent activity {i+1}/5, waiting 90 seconds...")
        await asyncio.sleep(90)  # Very long idle period
    
    print(f"✅ Idle anomaly complete for {agent_id}")

async def generate_diverse_actions_anomaly(producer, agent_id, count=50):
    """Generate unusually diverse actions"""
    print(f"⚠️  Generating diverse-actions anomaly for {agent_id}...")
    
    # Generate unique actions (high action diversity)
    for i in range(count):
        activity = {
            "agent_id": agent_id,
            "action": f"unique_action_{i:03d}",  # All different!
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "latency_ms": random.randint(40, 100),
            "status": "success"
        }
        
        await producer.send(KAFKA_TOPIC, value=activity)
        await asyncio.sleep(0.1)
    
    print(f"✅ Diverse-actions anomaly complete for {agent_id}")

async def main():
    """Main test script"""
    print("=" * 80)
    print("PHASE 6 - UEBA TEST ACTIVITY GENERATOR")
    print("=" * 80)
    print()
    
    # Initialize Kafka producer
    print(f"🔌 Connecting to Kafka at {KAFKA_BOOTSTRAP}...")
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
    )
    
    try:
        await producer.start()
        print("✅ Kafka producer connected")
        print()
        
        # Test Agent 1: Normal baseline + High Latency
        print("=" * 80)
        print("TEST 1: NORMAL_AGENT → High Latency Anomaly")
        print("=" * 80)
        await generate_normal_activity(producer, "NORMAL_AGENT", 100)
        await asyncio.sleep(2)
        await generate_high_latency_anomaly(producer, "NORMAL_AGENT", 30)
        print()
        
        # Test Agent 2: Normal baseline + High Error Rate
        print("=" * 80)
        print("TEST 2: ERROR_AGENT → High Error Rate Anomaly")
        print("=" * 80)
        await generate_normal_activity(producer, "ERROR_AGENT", 100)
        await asyncio.sleep(2)
        await generate_high_error_rate_anomaly(producer, "ERROR_AGENT", 30)
        print()
        
        # Test Agent 3: Normal baseline + Burst
        print("=" * 80)
        print("TEST 3: BURST_AGENT → Activity Burst Anomaly")
        print("=" * 80)
        await generate_normal_activity(producer, "BURST_AGENT", 100)
        await asyncio.sleep(2)
        await generate_burst_anomaly(producer, "BURST_AGENT", 100)
        print()
        
        # Test Agent 4: Normal baseline + Diverse Actions
        print("=" * 80)
        print("TEST 4: DIVERSE_AGENT → Action Diversity Anomaly")
        print("=" * 80)
        await generate_normal_activity(producer, "DIVERSE_AGENT", 100)
        await asyncio.sleep(2)
        await generate_diverse_actions_anomaly(producer, "DIVERSE_AGENT", 50)
        print()
        
        # Test Agent 5: Multiple anomalies (complex case)
        print("=" * 80)
        print("TEST 5: COMPLEX_AGENT → Multiple Anomalies")
        print("=" * 80)
        await generate_normal_activity(producer, "COMPLEX_AGENT", 80)
        await asyncio.sleep(1)
        await generate_high_latency_anomaly(producer, "COMPLEX_AGENT", 20)
        await asyncio.sleep(1)
        await generate_high_error_rate_anomaly(producer, "COMPLEX_AGENT", 20)
        print()
        
        print("=" * 80)
        print("✅ ALL TEST ACTIVITY GENERATED SUCCESSFULLY")
        print("=" * 80)
        print()
        print("⏳ Wait 3-5 minutes for UEBA agent to analyze...")
        print()
        print("Then check results:")
        print("  1. View alerts:")
        print("     curl http://localhost:8004/ueba/alerts | jq")
        print()
        print("  2. View statistics:")
        print("     curl http://localhost:8004/ueba/stats | jq")
        print()
        print("  3. Check specific agent:")
        print("     curl http://localhost:8004/ueba/agents/NORMAL_AGENT/alerts | jq")
        print()
        print("  4. View in Kibana:")
        print("     http://localhost:5601")
        print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await producer.stop()
        print("🛑 Producer stopped")

if __name__ == "__main__":
    asyncio.run(main())
