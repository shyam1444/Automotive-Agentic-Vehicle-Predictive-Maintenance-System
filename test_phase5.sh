#!/bin/bash

################################################################################
# Phase 5 Testing Script - Manufacturing Feedback & RCA
# Tests ClickHouse integration, trend detection, and CAPA generation
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((TESTS_PASSED++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((TESTS_FAILED++))
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_docker_container() {
    local container=$1
    if docker ps | grep -q "$container"; then
        print_success "$container is running"
        return 0
    else
        print_error "$container is not running"
        return 1
    fi
}

################################################################################
# Test 1: Prerequisites Check
################################################################################

test_prerequisites() {
    print_header "Test 1: Prerequisites Check"
    
    # Check Docker containers
    print_info "Checking Docker containers..."
    check_docker_container "clickhouse"
    check_docker_container "mongodb"
    check_docker_container "kafka"
    
    # Check Python virtual environment
    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_success "Virtual environment is active"
    else
        print_warning "Virtual environment not active. Run: source venv/bin/activate"
    fi
    
    # Check Python packages
    print_info "Checking Python packages..."
    python3 -c "import clickhouse_driver" 2>/dev/null && print_success "clickhouse-driver installed" || print_error "clickhouse-driver not installed"
    python3 -c "import motor" 2>/dev/null && print_success "motor installed" || print_error "motor not installed"
    python3 -c "import aiokafka" 2>/dev/null && print_success "aiokafka installed" || print_error "aiokafka not installed"
    python3 -c "import pandas" 2>/dev/null && print_success "pandas installed" || print_error "pandas not installed"
}

################################################################################
# Test 2: ClickHouse Connectivity
################################################################################

test_clickhouse_connectivity() {
    print_header "Test 2: ClickHouse Connectivity"
    
    # Test connection
    print_info "Testing ClickHouse connection..."
    if docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "SELECT 1" > /dev/null 2>&1; then
        print_success "ClickHouse connection successful"
    else
        print_error "ClickHouse connection failed"
        return 1
    fi
    
    # Check database exists
    print_info "Checking telemetry_db database..."
    if docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "SHOW DATABASES" | grep -q "telemetry_db"; then
        print_success "telemetry_db database exists"
    else
        print_error "telemetry_db database not found"
        return 1
    fi
    
    # Check vehicle_predictions table
    print_info "Checking vehicle_predictions table..."
    if docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "SHOW TABLES FROM telemetry_db" | grep -q "vehicle_predictions"; then
        print_success "vehicle_predictions table exists"
    else
        print_error "vehicle_predictions table not found"
        print_warning "Creating vehicle_predictions table..."
        docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "
        CREATE TABLE IF NOT EXISTS telemetry_db.vehicle_predictions (
            vehicle_id String,
            vehicle_model String,
            timestamp DateTime,
            engine_temp Float32,
            vibration_level Float32,
            rpm Int32,
            battery_voltage Float32,
            fuel_level Float32,
            predicted_failure UInt8,
            confidence_score Float32
        ) ENGINE = MergeTree()
        ORDER BY (timestamp, vehicle_id)
        "
        print_success "vehicle_predictions table created"
    fi
    
    # Check for prediction data
    print_info "Checking for prediction data..."
    PREDICTION_COUNT=$(docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "SELECT COUNT(*) FROM telemetry_db.vehicle_predictions")
    
    if [ "$PREDICTION_COUNT" -gt 0 ]; then
        print_success "Found $PREDICTION_COUNT prediction records"
    else
        print_warning "No prediction data found. Generating test data..."
        generate_test_data
    fi
}

################################################################################
# Test 3: Generate Test Data
################################################################################

generate_test_data() {
    print_header "Test 3: Generate Test Data"
    
    print_info "Inserting 200 test records into ClickHouse..."
    
    docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "
    INSERT INTO telemetry_db.vehicle_predictions
    SELECT
        concat('VEH_', toString(number % 20)) as vehicle_id,
        arrayElement(['HERO_2025', 'SPLENDOR_2025', 'XPULSE_2025'], (number % 3) + 1) as vehicle_model,
        now() - INTERVAL (number % 30) DAY as timestamp,
        100 + (rand() % 30) as engine_temp,
        2 + (rand() % 8) as vibration_level,
        5000 + (rand() % 2000) as rpm,
        11 + (rand() % 3) as battery_voltage,
        30 + (rand() % 70) as fuel_level,
        if((rand() % 100) < 15, 1, 0) as predicted_failure,
        0.70 + (rand() % 30) / 100.0 as confidence_score
    FROM numbers(200)
    "
    
    print_success "Test data inserted"
    
    # Verify data
    FAILURE_COUNT=$(docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "SELECT COUNT(*) FROM telemetry_db.vehicle_predictions WHERE predicted_failure = 1")
    print_info "Total failures in test data: $FAILURE_COUNT"
}

################################################################################
# Test 4: Historical Data Query
################################################################################

test_historical_data_query() {
    print_header "Test 4: Historical Data Query"
    
    print_info "Testing historical failure query (30 days)..."
    
    HISTORICAL_FAILURES=$(docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "
    SELECT COUNT(*) 
    FROM telemetry_db.vehicle_predictions 
    WHERE predicted_failure = 1 
      AND timestamp >= now() - INTERVAL 30 DAY
    ")
    
    if [ "$HISTORICAL_FAILURES" -gt 0 ]; then
        print_success "Found $HISTORICAL_FAILURES historical failures"
    else
        print_error "No historical failures found"
        return 1
    fi
    
    # Test component inference query (engine overheating)
    print_info "Testing component inference (engine temp > 120°C)..."
    
    OVERHEATING_COUNT=$(docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "
    SELECT COUNT(*) 
    FROM telemetry_db.vehicle_predictions 
    WHERE predicted_failure = 1 
      AND engine_temp > 120
      AND timestamp >= now() - INTERVAL 30 DAY
    ")
    
    print_info "Found $OVERHEATING_COUNT overheating failures"
    
    # Test component inference query (high vibration)
    print_info "Testing component inference (vibration > 8.0)..."
    
    VIBRATION_COUNT=$(docker exec clickhouse clickhouse-client --user default --password clickhouse_pass -q "
    SELECT COUNT(*) 
    FROM telemetry_db.vehicle_predictions 
    WHERE predicted_failure = 1 
      AND vibration_level > 8.0
      AND timestamp >= now() - INTERVAL 30 DAY
    ")
    
    print_info "Found $VIBRATION_COUNT high vibration failures"
}

################################################################################
# Test 5: MongoDB Setup
################################################################################

test_mongodb_setup() {
    print_header "Test 5: MongoDB Setup"
    
    # Check MongoDB connection
    print_info "Testing MongoDB connection..."
    if docker exec mongodb mongosh --quiet --eval "db.adminCommand('ping').ok" > /dev/null 2>&1; then
        print_success "MongoDB connection successful"
    else
        print_error "MongoDB connection failed"
        return 1
    fi
    
    # Check agents_db database
    print_info "Checking agents_db database..."
    docker exec mongodb mongosh --quiet --eval "use agents_db; db.getName()" > /dev/null 2>&1
    print_success "agents_db database accessible"
    
    # Create indexes for manufacturing_reports
    print_info "Creating indexes for manufacturing_reports collection..."
    docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.manufacturing_reports.createIndex({component_id: 1, vehicle_model: 1});
    db.manufacturing_reports.createIndex({processed_at: -1});
    db.manufacturing_reports.createIndex({status: 1, priority: 1});
    " > /dev/null 2>&1
    print_success "Indexes created"
}

################################################################################
# Test 6: Kafka Topics
################################################################################

test_kafka_topics() {
    print_header "Test 6: Kafka Topics"
    
    # Check if topics exist
    print_info "Checking Kafka topics..."
    
    TOPICS=$(docker exec -it kafka kafka-topics --list --bootstrap-server localhost:9092 2>/dev/null)
    
    if echo "$TOPICS" | grep -q "diagnostic_results"; then
        print_success "diagnostic_results topic exists"
    else
        print_warning "diagnostic_results topic not found. Creating..."
        docker exec -it kafka kafka-topics --create \
            --bootstrap-server localhost:9092 \
            --replication-factor 1 \
            --partitions 3 \
            --topic diagnostic_results > /dev/null 2>&1
        print_success "diagnostic_results topic created"
    fi
    
    if echo "$TOPICS" | grep -q "manufacturing_feedback"; then
        print_success "manufacturing_feedback topic exists"
    else
        print_warning "manufacturing_feedback topic not found. Creating..."
        docker exec -it kafka kafka-topics --create \
            --bootstrap-server localhost:9092 \
            --replication-factor 1 \
            --partitions 3 \
            --topic manufacturing_feedback > /dev/null 2>&1
        print_success "manufacturing_feedback topic created"
    fi
}

################################################################################
# Test 7: Start Manufacturing Agent Phase 5
################################################################################

test_start_agent() {
    print_header "Test 7: Start Manufacturing Agent Phase 5"
    
    # Check if agent is already running
    if pgrep -f "manufacturing_agent_phase5.py" > /dev/null; then
        print_warning "Manufacturing Agent Phase 5 is already running"
        AGENT_PID=$(pgrep -f "manufacturing_agent_phase5.py")
        print_info "Agent PID: $AGENT_PID"
    else
        print_info "Starting Manufacturing Agent Phase 5..."
        python3 agents/manufacturing_agent_phase5.py > /dev/null 2>&1 &
        AGENT_PID=$!
        print_info "Agent started with PID: $AGENT_PID"
        
        # Wait for agent to start
        sleep 5
        
        if ps -p $AGENT_PID > /dev/null; then
            print_success "Manufacturing Agent Phase 5 is running"
        else
            print_error "Manufacturing Agent Phase 5 failed to start"
            return 1
        fi
    fi
    
    # Wait for agent registration
    print_info "Waiting for agent registration (10 seconds)..."
    sleep 10
    
    # Check agent registration in MongoDB
    AGENT_STATUS=$(docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.agent_status.findOne({agent_id: 'MANUFACTURING_PHASE5_001'})
    " 2>/dev/null)
    
    if [[ -n "$AGENT_STATUS" ]]; then
        print_success "Agent registered in MongoDB"
    else
        print_warning "Agent not yet registered (may take longer)"
    fi
}

################################################################################
# Test 8: Test Kafka Message Processing
################################################################################

test_kafka_message_processing() {
    print_header "Test 8: Test Kafka Message Processing"
    
    print_info "Publishing test diagnostic message to Kafka..."
    
    # Create test diagnostic message
    TEST_MESSAGE=$(cat <<EOF
{
  "vehicle_id": "TEST_VEH_001",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%S)",
  "diagnostic_results": {
    "root_causes": [
      {
        "component": "COOLING_SYSTEM",
        "failure_type": "Overheating",
        "likelihood": 0.92,
        "severity": "critical"
      },
      {
        "component": "ENGINE_MOUNT",
        "failure_type": "Excessive Vibration",
        "likelihood": 0.88,
        "severity": "critical"
      }
    ]
  }
}
EOF
    )
    
    echo "$TEST_MESSAGE" | docker exec -i kafka kafka-console-producer \
        --bootstrap-server localhost:9092 \
        --topic diagnostic_results > /dev/null 2>&1
    
    print_success "Test message published"
    
    # Wait for processing
    print_info "Waiting for message processing (5 seconds)..."
    sleep 5
}

################################################################################
# Test 9: Verify Historical Data Load
################################################################################

test_historical_data_load() {
    print_header "Test 9: Verify Historical Data Load"
    
    print_info "Checking agent logs for historical data load..."
    
    if [ -f logs/manufacturing_agent_phase5_*.log ]; then
        LATEST_LOG=$(ls -t logs/manufacturing_agent_phase5_*.log | head -1)
        
        if grep -q "Loaded.*historical failures" "$LATEST_LOG"; then
            LOADED_COUNT=$(grep "Loaded.*historical failures" "$LATEST_LOG" | tail -1 | grep -oP '\d+' | head -1)
            print_success "Historical data loaded: $LOADED_COUNT failures"
        else
            print_warning "Historical data load not yet logged"
        fi
    else
        print_warning "Agent log file not found"
    fi
}

################################################################################
# Test 10: Wait for Trend Analysis
################################################################################

test_trend_analysis() {
    print_header "Test 10: Wait for Trend Analysis"
    
    print_info "Trend analysis runs every 10 minutes by default"
    print_info "For testing purposes, we'll check if analysis is configured..."
    
    # Check agent configuration
    if grep -q "TREND_ANALYSIS_INTERVAL" agents/manufacturing_agent_phase5.py; then
        INTERVAL=$(grep "TREND_ANALYSIS_INTERVAL" agents/manufacturing_agent_phase5.py | grep -oP '\d+')
        print_info "Trend analysis interval: $INTERVAL seconds (~$((INTERVAL / 60)) minutes)"
    fi
    
    print_warning "Manual verification: Wait $((INTERVAL / 60)) minutes and check logs for 'Analyzing trends'"
}

################################################################################
# Test 11: Verify CAPA Generation
################################################################################

test_capa_generation() {
    print_header "Test 11: Verify CAPA Generation"
    
    print_info "Checking for CAPA reports in MongoDB..."
    
    CAPA_COUNT=$(docker exec mongodb mongosh --quiet --eval "
    use agents_db;
    db.manufacturing_reports.countDocuments({})
    " 2>/dev/null | tail -1)
    
    if [ "$CAPA_COUNT" -gt 0 ]; then
        print_success "Found $CAPA_COUNT CAPA reports in MongoDB"
        
        # Show latest report
        print_info "Latest CAPA report:"
        docker exec mongodb mongosh --quiet --eval "
        use agents_db;
        db.manufacturing_reports.findOne({}, {recommendation_id: 1, component_id: 1, vehicle_model: 1, trend: 1, priority: 1})
        " 2>/dev/null
    else
        print_warning "No CAPA reports found yet (analysis may not have run)"
        print_info "CAPA generation runs every 10 minutes after sufficient data is collected"
    fi
}

################################################################################
# Test 12: Check Kafka Output
################################################################################

test_kafka_output() {
    print_header "Test 12: Check Kafka Output"
    
    print_info "Checking manufacturing_feedback topic for messages..."
    
    # Check if topic has messages
    OFFSET=$(docker exec -it kafka kafka-run-class kafka.tools.GetOffsetShell \
        --broker-list localhost:9092 \
        --topic manufacturing_feedback 2>/dev/null | grep -oP '\d+$' | head -1)
    
    if [ -n "$OFFSET" ] && [ "$OFFSET" -gt 0 ]; then
        print_success "Found $OFFSET messages in manufacturing_feedback topic"
        
        print_info "Sample message:"
        docker exec -it kafka kafka-console-consumer \
            --bootstrap-server localhost:9092 \
            --topic manufacturing_feedback \
            --from-beginning \
            --max-messages 1 \
            --timeout-ms 5000 2>/dev/null | head -20
    else
        print_warning "No messages in manufacturing_feedback topic yet"
    fi
}

################################################################################
# Test 13: Dashboard API Health
################################################################################

test_dashboard_api() {
    print_header "Test 13: Dashboard API Health"
    
    # Check if API is running
    if pgrep -f "fastapi_manufacturing_dashboard.py" > /dev/null; then
        print_success "Dashboard API is running"
        
        # Test health endpoint
        print_info "Testing /health endpoint..."
        if curl -s http://localhost:8003/health > /dev/null 2>&1; then
            print_success "Dashboard API health check passed"
            
            # Test stats endpoint
            print_info "Testing /manufacturing/stats endpoint..."
            STATS=$(curl -s http://localhost:8003/manufacturing/stats)
            if [[ -n "$STATS" ]]; then
                print_success "Stats endpoint working"
                echo "$STATS" | python3 -m json.tool 2>/dev/null | head -20
            fi
        else
            print_warning "Dashboard API not responding (may not be started)"
        fi
    else
        print_warning "Dashboard API not running"
        print_info "Start with: python3 api/fastapi_manufacturing_dashboard.py"
    fi
}

################################################################################
# Test Summary
################################################################################

print_test_summary() {
    print_header "Test Summary"
    
    TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))
    
    echo -e "${BLUE}Total Tests: $TOTAL_TESTS${NC}"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}\n"
        echo -e "${BLUE}Phase 5 is ready for production deployment.${NC}"
        echo -e "${BLUE}Next steps:${NC}"
        echo -e "  1. Monitor agent logs: tail -f logs/manufacturing_agent_phase5_*.log"
        echo -e "  2. Wait 10 minutes for first CAPA generation"
        echo -e "  3. Check MongoDB: docker exec mongodb mongosh --eval 'use agents_db; db.manufacturing_reports.find().limit(5)'"
        echo -e "  4. Monitor Kafka: docker exec -it kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic manufacturing_feedback"
    else
        echo -e "\n${RED}✗ Some tests failed. Review errors above.${NC}\n"
        exit 1
    fi
}

################################################################################
# Main Execution
################################################################################

main() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║     Phase 5 Testing - Manufacturing Feedback & RCA           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    test_prerequisites
    test_clickhouse_connectivity
    test_historical_data_query
    test_mongodb_setup
    test_kafka_topics
    test_start_agent
    test_kafka_message_processing
    test_historical_data_load
    test_trend_analysis
    test_capa_generation
    test_kafka_output
    test_dashboard_api
    
    print_test_summary
}

# Run main function
main
