#!/bin/bash
# Phase 4 Quick Start Script
# Launches all agents and dashboard API

set -e

echo "========================================="
echo "   PHASE 4 - QUICK START"
echo "========================================="
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "❌ Virtual environment not activated"
    echo "   Run: source venv/bin/activate"
    exit 1
fi

# Check if MongoDB is running
if ! docker ps | grep -q mongodb; then
    echo "⚠️  MongoDB not running. Starting..."
    cd docker
    docker-compose up -d mongodb
    cd ..
    sleep 5
fi

# Check if Kafka is running
if ! docker ps | grep -q kafka; then
    echo "⚠️  Kafka not running. Starting..."
    cd docker
    docker-compose up -d zookeeper kafka
    cd ..
    sleep 10
fi

echo "✅ Infrastructure ready"
echo ""

# Initialize MongoDB if needed
if ! docker exec mongodb mongosh --quiet --eval "use agents_db; db.customer_info.count()" | grep -q "3"; then
    echo "📦 Initializing MongoDB..."
    python3 init_phase4.py
    echo ""
fi

# Create logs directory
mkdir -p logs

# Function to start agent in background
start_agent() {
    local agent_name=$1
    local agent_file=$2
    
    echo "🚀 Starting $agent_name..."
    nohup python3 "$agent_file" > "logs/${agent_name}_quickstart.log" 2>&1 &
    echo $! > "logs/${agent_name}.pid"
    sleep 2
}

# Start all agents
echo "========================================="
echo "   LAUNCHING AGENTS"
echo "========================================="
echo ""

start_agent "master_agent" "agents/master_agent.py"
start_agent "diagnostics_agent" "agents/diagnostics_agent.py"
start_agent "customer_agent" "agents/customer_agent.py"
start_agent "scheduling_agent" "agents/scheduling_agent.py"
start_agent "manufacturing_agent" "agents/manufacturing_agent.py"
start_agent "ueba_agent" "agents/ueba_agent.py"

echo ""
echo "========================================="
echo "   LAUNCHING DASHBOARD API"
echo "========================================="
echo ""

start_agent "agent_dashboard" "api/fastapi_agent_dashboard.py"

echo ""
echo "✅ All agents started!"
echo ""
echo "========================================="
echo "   STATUS"
echo "========================================="
echo ""

# Wait for agents to register
sleep 5

# Check agent status
echo "📊 Agent Status:"
docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.agent_status.find({}, {
        agent_id:1,
        agent_type:1,
        status:1,
        _id:0
    }).forEach(printjson)
"

echo ""
echo "========================================="
echo "   ENDPOINTS"
echo "========================================="
echo ""
echo "📊 Agent Dashboard API: http://localhost:8002"
echo "   - Health:     http://localhost:8002/health"
echo "   - Stats:      http://localhost:8002/dashboard/stats"
echo "   - Agents:     http://localhost:8002/agents/status"
echo "   - Alerts:     http://localhost:8002/alerts/unresolved"
echo "   - Schedules:  http://localhost:8002/schedules"
echo "   - CAPA:       http://localhost:8002/manufacturing/feedback"
echo "   - Security:   http://localhost:8002/security/alerts"
echo ""
echo "========================================="
echo "   MONITORING"
echo "========================================="
echo ""
echo "📋 Log Files:"
ls -1 logs/*_quickstart.log | while read log; do
    echo "   - $log"
done
echo ""
echo "📝 View logs:"
echo "   tail -f logs/master_agent_quickstart.log"
echo ""
echo "📊 Monitor Kafka:"
echo "   docker exec -it kafka kafka-console-consumer \\"
echo "     --bootstrap-server localhost:9092 \\"
echo "     --topic agent_activity_log"
echo ""
echo "========================================="
echo "   SHUTDOWN"
echo "========================================="
echo ""
echo "🛑 To stop all agents:"
echo "   ./stop_agents.sh"
echo ""
echo "========================================="
echo "   ✅ PHASE 4 READY"
echo "========================================="
echo ""
