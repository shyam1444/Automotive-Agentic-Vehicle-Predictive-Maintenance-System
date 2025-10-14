# 🚀 Quick Start Guide

Get your Automotive Predictive Maintenance System running in **under 10 minutes**!

---

## ⚡ Fast Track Setup

### Step 1: Clone Repository (30 seconds)

```bash
git clone https://github.com/PranavOaR/agentic-ai.git
cd agentic-ai
```

### Step 2: Start Infrastructure (2 minutes)

```bash
cd docker
docker-compose up -d
cd ..
```

**What's starting:**
- ✅ Kafka (port 9092)
- ✅ ClickHouse (port 9000)
- ✅ Mosquitto MQTT (port 1883)

### Step 3: Python Setup (1 minute)

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4: Initialize Database (30 seconds)

```bash
python3 init_clickhouse.py
```

### Step 5: Start Backend (Quick Method) (1 minute)

**Option A - All-in-One Script:**
```bash
chmod +x start_all.sh
./start_all.sh
```

**Option B - Manual (for troubleshooting):**
```bash
# Start simulators (11 vehicles)
for i in {1..11}; do python3 simulators/vehicle_simulator.py > logs/vehicle_$i.log 2>&1 & done

# Start data pipeline
python3 bridge/mqtt_to_kafka.py > logs/mqtt_bridge.log 2>&1 &
python3 consumers/cleaner_consumer.py > logs/cleaner.log 2>&1 &
python3 consumers/clickhouse_ingest.py > logs/clickhouse.log 2>&1 &

# Start API
python3 -m uvicorn api.main:socket_app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
```

### Step 6: Start Frontend (2 minutes)

```bash
cd frontend
npm install  # First time only
npm run dev
```

### Step 7: Access Application (Now!)

🎉 **You're live!**

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health

---

## 🔍 Verify Everything Works

### Check Backend Health
```bash
curl http://localhost:8000/health
```

Expected output:
```json
{
  "status": "healthy",
  "services": {
    "api": "operational",
    "telemetry": "operational"
  }
}
```

### Check Data Flow
```bash
curl http://localhost:8000/fleet/stats
```

Expected output:
```json
{
  "total_vehicles": 11,
  "healthy": 8,
  "warning": 2,
  "critical": 1
}
```

### Check Frontend
Open browser: http://localhost:3000

You should see:
- ✅ Vehicle cards with real-time data
- ✅ Alert notifications
- ✅ Fleet statistics
- ✅ WebSocket connection indicator (green)

---

## 🛠️ Common Issues & Fixes

### Issue: Port Already in Use

**Symptom:** Error: `Address already in use`

**Fix:**
```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or for port 3000
lsof -ti:3000 | xargs kill -9
```

### Issue: Docker Services Not Starting

**Symptom:** Connection refused errors

**Fix:**
```bash
# Check Docker is running
docker ps

# Restart services
cd docker
docker-compose down
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Issue: No Data in Frontend

**Symptom:** Dashboard shows 0 vehicles

**Fix:**
```bash
# Check if simulators are running
ps aux | grep vehicle_simulator

# Restart simulators
pkill -f vehicle_simulator
for i in {1..11}; do python3 simulators/vehicle_simulator.py > logs/vehicle_$i.log 2>&1 & done

# Wait 30 seconds and refresh browser
```

### Issue: ClickHouse Connection Error

**Symptom:** `Connection refused` to ClickHouse

**Fix:**
```bash
# Check ClickHouse is running
docker exec clickhouse clickhouse-client --password clickhouse_pass -q "SELECT 1"

# Reinitialize database
python3 init_clickhouse.py
```

---

## 📊 Test Each Component

### 1. Test MQTT → Kafka Bridge
```bash
# Watch Kafka topic
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic vehicle_telemetry_raw \
  --max-messages 1
```

### 2. Test Data Cleaner
```bash
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic vehicle_telemetry_clean \
  --max-messages 1
```

### 3. Test ClickHouse Data
```bash
docker exec clickhouse clickhouse-client --password clickhouse_pass -q \
  "SELECT COUNT(*) FROM telemetry_db.telemetry"
```

### 4. Test API Endpoints
```bash
# Fleet vehicles
curl http://localhost:8000/fleet/vehicles

# Alerts
curl http://localhost:8000/alerts

# Manufacturing CAPA
curl http://localhost:8000/manufacturing/feedback
```

---

## 🎮 Play with the System

### Simulate Critical Alert

1. **Modify simulator thresholds** (optional):
   Edit `simulators/vehicle_simulator.py` line ~50:
   ```python
   engine_temp = random.uniform(110, 120)  # Force high temp
   ```

2. **Restart one simulator:**
   ```bash
   pkill -f "vehicle_simulator.py"
   python3 simulators/vehicle_simulator.py &
   ```

3. **Watch alerts appear** in dashboard within 30 seconds

### View Real-Time WebSocket Updates

Open browser console (F12) → Network → WS tab

You should see:
- `vehicle_prediction` events every 10s
- `vehicle_alert` events when anomalies detected

---

## 🧹 Cleanup & Stop

### Stop All Processes
```bash
# Stop Python processes
pkill -f "python3"

# Or specific ones
pkill -f vehicle_simulator
pkill -f mqtt_to_kafka
pkill -f cleaner_consumer
pkill -f clickhouse_ingest
pkill -f uvicorn

# Stop frontend
# Press Ctrl+C in frontend terminal
```

### Stop Docker Services
```bash
cd docker
docker-compose down
```

### Complete Reset
```bash
# Stop everything
pkill -f "python3"
cd docker && docker-compose down -v  # -v removes volumes
cd ..

# Clear logs
rm -rf logs/*

# Start fresh
./start_all.sh
```

---

## 📚 Next Steps

Once running, explore:

1. **Dashboard Pages**
   - Vehicle Dashboard (`/vehicle-dashboard`)
   - Fleet Management (`/fleet`)
   - Manufacturing CAPA (`/manufacturing`)
   - Security UEBA (`/security`)
   - Analytics (`/analytics`)

2. **API Documentation**
   - Interactive docs at http://localhost:8000/docs
   - Try out endpoints directly in browser

3. **Customize**
   - Edit alert thresholds in `api/main.py`
   - Add new vehicle types in simulators
   - Create custom CAPA rules

4. **Scale Up**
   - Add more simulators (tested up to 50+)
   - Adjust Kafka partitions
   - Configure ClickHouse clustering

---

## 💡 Pro Tips

1. **Monitor Logs in Real-Time:**
   ```bash
   tail -f logs/*.log
   ```

2. **Check System Resource Usage:**
   ```bash
   docker stats
   ```

3. **Quick API Test:**
   ```bash
   # Save as test.sh
   echo "Fleet Stats:" && curl -s http://localhost:8000/fleet/stats | jq
   echo "\nAlerts:" && curl -s http://localhost:8000/alerts | jq '.count'
   echo "\nCAPAs:" && curl -s http://localhost:8000/manufacturing/feedback | jq '.count'
   ```

4. **WebSocket Test (Node.js):**
   ```javascript
   const io = require('socket.io-client');
   const socket = io('http://localhost:8000');
   socket.on('vehicle_alert', console.log);
   ```

---

## 🆘 Need Help?

- **Check logs:** `logs/` directory
- **API errors:** http://localhost:8000/docs
- **Frontend errors:** Browser console (F12)
- **Issues:** https://github.com/PranavOaR/agentic-ai/issues

---

**🎊 Congratulations! Your automotive predictive maintenance system is live!**

Happy monitoring! 🚗💨
