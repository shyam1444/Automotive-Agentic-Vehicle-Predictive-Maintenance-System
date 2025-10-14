#!/bin/bash
# Phase 4 Testing Script
# Tests all agents end-to-end

set -e

echo "========================================="
echo "   PHASE 4 - END-TO-END TESTING"
echo "========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_case() {
    local test_name=$1
    shift
    local command=$@
    
    echo -n "🧪 Testing: $test_name... "
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "========================================="
echo "   1. INFRASTRUCTURE TESTS"
echo "========================================="
echo ""

test_case "MongoDB is running" "docker ps | grep -q mongodb"
test_case "Kafka is running" "docker ps | grep -q kafka"
test_case "MongoDB is accessible" "docker exec mongodb mongosh --eval 'db.version()' > /dev/null"

echo ""
echo "========================================="
echo "   2. MONGODB COLLECTION TESTS"
echo "========================================="
echo ""

test_case "agent_status collection exists" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.count()' | grep -qE '[0-9]+'"
test_case "customer_info collection has data" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.customer_info.count()' | grep -q '3'"
test_case "service_schedule collection exists" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.service_schedule.count()' | grep -qE '[0-9]+'"
test_case "manufacturing_reports collection exists" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.manufacturing_reports.count()' | grep -qE '[0-9]+'"
test_case "alerts_history collection exists" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.alerts_history.count()' | grep -qE '[0-9]+'"

echo ""
echo "========================================="
echo "   3. KAFKA TOPIC TESTS"
echo "========================================="
echo ""

test_case "diagnostic_results topic exists" "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q diagnostic_results"
test_case "customer_ack topic exists" "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q customer_ack"
test_case "manufacturing_feedback topic exists" "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q manufacturing_feedback"
test_case "agent_activity_log topic exists" "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q agent_activity_log"
test_case "security_alerts topic exists" "docker exec kafka kafka-topics --list --bootstrap-server localhost:9092 | grep -q security_alerts"

echo ""
echo "========================================="
echo "   4. AGENT STATUS TESTS"
echo "========================================="
echo ""

# Wait for agents to register
sleep 3

test_case "Master Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"MASTER_001\"})' | grep -q MASTER_001"
test_case "Diagnostics Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"DIAGNOSTICS_001\"})' | grep -q DIAGNOSTICS_001"
test_case "Customer Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"CUSTOMER_001\"})' | grep -q CUSTOMER_001"
test_case "Scheduling Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"SCHEDULING_001\"})' | grep -q SCHEDULING_001"
test_case "Manufacturing Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"MANUFACTURING_001\"})' | grep -q MANUFACTURING_001"
test_case "UEBA Agent is registered" "docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.findOne({agent_id: \"UEBA_001\"})' | grep -q UEBA_001"

echo ""
echo "========================================="
echo "   5. DASHBOARD API TESTS"
echo "========================================="
echo ""

test_case "Dashboard API is running" "curl -s http://localhost:8002/health | grep -q healthy"
test_case "Dashboard stats endpoint" "curl -s http://localhost:8002/dashboard/stats | grep -q total_agents"
test_case "Agent status endpoint" "curl -s http://localhost:8002/agents/status | grep -q agent_id"
test_case "Alerts endpoint" "curl -s http://localhost:8002/alerts | grep -q '\[\]\\|vehicle_id'"
test_case "Schedules endpoint" "curl -s http://localhost:8002/schedules | grep -q '\[\]\\|booking_id'"
test_case "Manufacturing feedback endpoint" "curl -s http://localhost:8002/manufacturing/feedback | grep -q '\[\]\\|recommendation_id'"
test_case "Security alerts endpoint" "curl -s http://localhost:8002/security/alerts | grep -q '\[\]\\|anomaly_id'"

echo ""
echo "========================================="
echo "   6. AGENT HEALTH TESTS"
echo "========================================="
echo ""

# Check if agents are active
ACTIVE_AGENTS=$(docker exec mongodb mongosh --quiet --eval 'use agents_db; db.agent_status.count({status: "active"})' | tail -1)

if [ "$ACTIVE_AGENTS" -ge 6 ]; then
    echo -e "✅ All agents active: $ACTIVE_AGENTS/6"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}⚠️  Only $ACTIVE_AGENTS/6 agents active${NC}"
    ((TESTS_FAILED++))
fi

echo ""
echo "========================================="
echo "   7. DETAILED AGENT INSPECTION"
echo "========================================="
echo ""

echo "📊 Agent Status Details:"
docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.agent_status.find({}, {
        agent_id:1,
        agent_type:1,
        status:1,
        messages_processed:1,
        errors_count:1,
        _id:0
    }).forEach(printjson)
" | grep -E "agent_id|agent_type|status|messages_processed|errors_count" | head -30

echo ""
echo "========================================="
echo "   8. SAMPLE DATA VERIFICATION"
echo "========================================="
echo ""

echo "📇 Sample Customers:"
docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.customer_info.find({}, {
        customer_id:1,
        vehicle_id:1,
        contact_info:1,
        _id:0
    }).limit(3).forEach(printjson)
" | grep -E "customer_id|vehicle_id|phone|email" | head -15

echo ""
echo "========================================="
echo "   TEST RESULTS"
echo "========================================="
echo ""

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
SUCCESS_RATE=$((TESTS_PASSED * 100 / TOTAL_TESTS))

echo "Total Tests:    $TOTAL_TESTS"
echo -e "${GREEN}Tests Passed:   $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Tests Failed:   $TESTS_FAILED${NC}"
else
    echo "Tests Failed:   $TESTS_FAILED"
fi
echo "Success Rate:   $SUCCESS_RATE%"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}=========================================${NC}"
    echo -e "${GREEN}   ✅ ALL TESTS PASSED!${NC}"
    echo -e "${GREEN}=========================================${NC}"
    exit 0
else
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "${YELLOW}   ⚠️  SOME TESTS FAILED${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo ""
    echo "Check logs for details:"
    echo "  - logs/*_quickstart.log"
    echo "  - logs/*_agent_*.log"
    exit 1
fi
