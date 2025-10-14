#!/bin/bash
# Stop all Phase 4 agents

echo "========================================="
echo "   STOPPING PHASE 4 AGENTS"
echo "========================================="
echo ""

# Function to stop agent by PID file
stop_agent() {
    local agent_name=$1
    local pid_file="logs/${agent_name}.pid"
    
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo "🛑 Stopping $agent_name (PID: $pid)..."
            kill $pid
            rm "$pid_file"
        else
            echo "⚠️  $agent_name not running (stale PID file)"
            rm "$pid_file"
        fi
    else
        echo "ℹ️  $agent_name PID file not found"
    fi
}

# Stop all agents
stop_agent "master_agent"
stop_agent "diagnostics_agent"
stop_agent "customer_agent"
stop_agent "scheduling_agent"
stop_agent "manufacturing_agent"
stop_agent "ueba_agent"
stop_agent "agent_dashboard"

echo ""
echo "✅ All agents stopped"
echo ""

# Check MongoDB agent status
echo "📊 Final Agent Status in MongoDB:"
docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.agent_status.find({}, {
        agent_id:1,
        status:1,
        messages_processed:1,
        _id:0
    }).forEach(printjson)
"

echo ""
echo "========================================="
echo "   CLEANUP COMPLETE"
echo "========================================="
echo ""
