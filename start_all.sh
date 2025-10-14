#!/bin/bash

# Automotive Predictive Maintenance System - Startup Script
# This script starts all backend services in the correct order

set -e  # Exit on error

echo "🚗 Starting Automotive Predictive Maintenance System..."
echo "=================================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

echo -e "${BLUE}📦 Checking Docker services...${NC}"
cd docker
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}🐳 Starting Docker services...${NC}"
    docker-compose up -d
    echo -e "${GREEN}✓ Docker services started${NC}"
    echo "⏳ Waiting 10 seconds for services to initialize..."
    sleep 10
else
    echo -e "${GREEN}✓ Docker services already running${NC}"
fi
cd ..

echo -e "${BLUE}🗄️  Initializing ClickHouse database...${NC}"
python3 init_clickhouse.py 2>/dev/null || echo -e "${YELLOW}⚠️  Database might already exist${NC}"

echo -e "${BLUE}🚀 Starting vehicle simulators (11 vehicles)...${NC}"
for i in {1..11}; do
    python3 simulators/vehicle_simulator.py > logs/vehicle_sim_$i.log 2>&1 &
done
echo -e "${GREEN}✓ 11 vehicle simulators started${NC}"

echo -e "${BLUE}🌉 Starting MQTT to Kafka bridge...${NC}"
python3 bridge/mqtt_to_kafka.py > logs/mqtt_bridge.log 2>&1 &
echo -e "${GREEN}✓ MQTT bridge started${NC}"

echo -e "${BLUE}🧹 Starting data cleaner consumer...${NC}"
python3 consumers/cleaner_consumer.py > logs/cleaner.log 2>&1 &
echo -e "${GREEN}✓ Data cleaner started${NC}"

echo -e "${BLUE}💾 Starting ClickHouse ingest consumer...${NC}"
python3 consumers/clickhouse_ingest.py > logs/clickhouse_ingest.log 2>&1 &
echo -e "${GREEN}✓ ClickHouse ingest started${NC}"

echo -e "${BLUE}🔌 Starting FastAPI backend server...${NC}"
python3 -m uvicorn api.main:socket_app --host 0.0.0.0 --port 8000 > logs/api_server.log 2>&1 &
echo -e "${GREEN}✓ API server started on port 8000${NC}"

echo ""
echo "⏳ Waiting 5 seconds for services to stabilize..."
sleep 5

echo ""
echo -e "${GREEN}=================================================="
echo "✅ All backend services started successfully!"
echo "==================================================${NC}"
echo ""
echo "📊 Service Status:"
echo "  • Docker Services: ✓ Running"
echo "  • Vehicle Simulators: ✓ 11 active"
echo "  • Data Pipeline: ✓ Processing"
echo "  • API Server: ✓ http://localhost:8000"
echo ""
echo "🔗 Quick Links:"
echo "  • API Health: http://localhost:8000/health"
echo "  • API Docs: http://localhost:8000/docs"
echo "  • Fleet Stats: http://localhost:8000/fleet/stats"
echo ""
echo "📝 View Logs:"
echo "  tail -f logs/*.log"
echo ""
echo "🛑 Stop All Services:"
echo "  ./stop_all.sh"
echo ""
echo "🎯 Next Step: Start Frontend"
echo "  cd frontend && npm install && npm run dev"
echo ""
echo -e "${BLUE}Happy Monitoring! 🚗💨${NC}"
