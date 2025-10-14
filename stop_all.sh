#!/bin/bash

# Automotive Predictive Maintenance System - Shutdown Script
# This script stops all running services gracefully

echo "🛑 Stopping Automotive Predictive Maintenance System..."
echo "=================================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${RED}Stopping Python processes...${NC}"

# Stop vehicle simulators
pkill -f "vehicle_simulator.py" && echo "  ✓ Vehicle simulators stopped"

# Stop data pipeline
pkill -f "mqtt_to_kafka.py" && echo "  ✓ MQTT bridge stopped"
pkill -f "cleaner_consumer.py" && echo "  ✓ Data cleaner stopped"
pkill -f "clickhouse_ingest.py" && echo "  ✓ ClickHouse ingest stopped"

# Stop API server
pkill -f "uvicorn api.main" && echo "  ✓ API server stopped"

# Stop any remaining Python processes (optional - commented out for safety)
# pkill -f "python3"

echo ""
echo -e "${RED}Stopping Docker services...${NC}"
cd docker
docker-compose down
echo -e "${GREEN}  ✓ Docker services stopped${NC}"
cd ..

echo ""
echo -e "${GREEN}=================================================="
echo "✅ All services stopped successfully!"
echo "==================================================${NC}"
echo ""
echo "📊 Cleanup Options:"
echo "  • View logs: ls -lh logs/"
echo "  • Clear logs: rm logs/*.log"
echo "  • Reset database: docker-compose down -v && python3 init_clickhouse.py"
echo ""
echo "🔄 Restart System:"
echo "  ./start_all.sh"
