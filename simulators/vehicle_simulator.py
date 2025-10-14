#!/usr/bin/env python3
"""
Vehicle Telemetry Simulator
Simulates 10-50 vehicles publishing telemetry data to MQTT broker.
Each vehicle publishes at intervals of 1-5 seconds with realistic sensor readings.
"""

import asyncio
import json
import random
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import os

import paho.mqtt.client as mqtt
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
NUM_VEHICLES = int(os.getenv("NUM_VEHICLES", "20"))
MIN_PUBLISH_INTERVAL = float(os.getenv("MIN_PUBLISH_INTERVAL", "1.0"))
MAX_PUBLISH_INTERVAL = float(os.getenv("MAX_PUBLISH_INTERVAL", "5.0"))
ANOMALY_PROBABILITY = float(os.getenv("ANOMALY_PROBABILITY", "0.05"))  # 5% chance


@dataclass
class GPSLocation:
    """GPS coordinates"""
    lat: float
    lon: float


@dataclass
class VehicleTelemetry:
    """Vehicle telemetry data schema"""
    vehicle_id: str
    timestamp: str
    engine_rpm: int
    engine_temp: float
    vibration: float
    speed: float
    gps: Dict[str, float]
    fuel_level: float
    battery_voltage: float

    def to_json(self) -> str:
        """Convert to JSON string"""
        data = asdict(self)
        return json.dumps(data)


class VehicleState:
    """Maintains state for a single vehicle to generate realistic telemetry"""
    
    def __init__(self, vehicle_id: str):
        self.vehicle_id = vehicle_id
        # Initialize with random but realistic base values
        self.speed = random.uniform(40, 100)  # km/h
        self.engine_rpm = int(self.speed * 30 + random.uniform(500, 1500))
        self.engine_temp = random.uniform(80, 95)
        self.vibration = random.uniform(1, 3)
        self.fuel_level = random.uniform(30, 100)
        self.battery_voltage = random.uniform(12.5, 14.5)
        
        # GPS starting location (random location in a city grid)
        self.lat = random.uniform(37.7, 37.8)  # San Francisco area
        self.lon = random.uniform(-122.5, -122.4)
        
        # Vehicle characteristics (affects behavior)
        self.max_speed = random.uniform(140, 180)
        self.acceleration_rate = random.uniform(2, 8)
        self.deceleration_rate = random.uniform(3, 10)
        
    def update(self, time_delta: float) -> VehicleTelemetry:
        """
        Update vehicle state and generate new telemetry reading.
        
        Args:
            time_delta: Time since last update in seconds
        """
        # Randomly change speed (simulate acceleration/deceleration)
        speed_change = random.uniform(-self.deceleration_rate, self.acceleration_rate) * time_delta
        self.speed = max(0, min(self.max_speed, self.speed + speed_change))
        
        # Engine RPM correlates with speed + some variation
        target_rpm = self.speed * 30 + random.uniform(500, 1500)
        self.engine_rpm = int(target_rpm + random.gauss(0, 100))
        self.engine_rpm = max(0, min(8000, self.engine_rpm))
        
        # Engine temperature increases with RPM and speed
        target_temp = 70 + (self.engine_rpm / 8000) * 40 + (self.speed / 180) * 10
        self.engine_temp += (target_temp - self.engine_temp) * 0.1  # Smooth transition
        self.engine_temp += random.gauss(0, 0.5)
        self.engine_temp = max(60, min(120, self.engine_temp))
        
        # Vibration increases with speed and RPM
        base_vibration = 0.5 + (self.speed / 180) * 2 + (self.engine_rpm / 8000) * 2
        self.vibration = base_vibration + random.gauss(0, 0.3)
        self.vibration = max(0, min(10, self.vibration))
        
        # Fuel consumption (faster speeds = more consumption)
        fuel_consumption = (self.speed / 180) * 0.01 * time_delta
        self.fuel_level = max(0, self.fuel_level - fuel_consumption)
        
        # Battery voltage slight fluctuation
        self.battery_voltage += random.gauss(0, 0.05)
        self.battery_voltage = max(10, min(15, self.battery_voltage))
        
        # Update GPS (simple movement simulation)
        # Approximate: 1 degree lat/lon ≈ 111 km
        distance_km = (self.speed / 3600) * time_delta  # km traveled
        self.lat += random.gauss(0, distance_km / 111)
        self.lon += random.gauss(0, distance_km / 111)
        
        # Inject anomalies occasionally
        if random.random() < ANOMALY_PROBABILITY:
            self._inject_anomaly()
        
        # Create telemetry message
        return VehicleTelemetry(
            vehicle_id=self.vehicle_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            engine_rpm=self.engine_rpm,
            engine_temp=round(self.engine_temp, 2),
            vibration=round(self.vibration, 2),
            speed=round(self.speed, 2),
            gps={"lat": round(self.lat, 6), "lon": round(self.lon, 6)},
            fuel_level=round(self.fuel_level, 2),
            battery_voltage=round(self.battery_voltage, 2)
        )
    
    def _inject_anomaly(self):
        """Inject an anomaly into vehicle state"""
        anomaly_type = random.choice([
            "high_temp", "high_vibration", "low_battery", 
            "high_rpm", "rapid_fuel_drop"
        ])
        
        if anomaly_type == "high_temp":
            self.engine_temp = random.uniform(105, 115)
            logger.warning(f"Anomaly injected: {self.vehicle_id} - High temperature: {self.engine_temp:.2f}°C")
        elif anomaly_type == "high_vibration":
            self.vibration = random.uniform(7, 9.5)
            logger.warning(f"Anomaly injected: {self.vehicle_id} - High vibration: {self.vibration:.2f}")
        elif anomaly_type == "low_battery":
            self.battery_voltage = random.uniform(10.5, 11.5)
            logger.warning(f"Anomaly injected: {self.vehicle_id} - Low battery: {self.battery_voltage:.2f}V")
        elif anomaly_type == "high_rpm":
            self.engine_rpm = random.randint(7000, 7900)
            logger.warning(f"Anomaly injected: {self.vehicle_id} - High RPM: {self.engine_rpm}")
        elif anomaly_type == "rapid_fuel_drop":
            self.fuel_level = max(0, self.fuel_level - random.uniform(10, 30))
            logger.warning(f"Anomaly injected: {self.vehicle_id} - Fuel drop: {self.fuel_level:.2f}%")


class VehicleSimulator:
    """Manages multiple vehicle simulations and MQTT publishing"""
    
    def __init__(self, num_vehicles: int = NUM_VEHICLES):
        self.num_vehicles = num_vehicles
        self.vehicles: List[VehicleState] = []
        self.mqtt_client: Optional[mqtt.Client] = None
        self.running = False
        self.message_count = 0
        self.error_count = 0
        
        # Setup logging
        logger.remove()  # Remove default handler
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
            level="INFO"
        )
        logger.add(
            "logs/vehicle_simulator_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function} - {message}",
            level="DEBUG"
        )
    
    def setup_mqtt(self):
        """Initialize MQTT client with connection callbacks"""
        self.mqtt_client = mqtt.Client(client_id=f"vehicle_simulator_{random.randint(1000, 9999)}")
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.success(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            else:
                logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
        
        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.warning(f"Unexpected disconnect from MQTT broker. Return code: {rc}")
        
        def on_publish(client, userdata, mid):
            self.message_count += 1
        
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_publish = on_publish
        
        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            logger.info("MQTT client loop started")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def initialize_vehicles(self):
        """Create vehicle instances"""
        logger.info(f"Initializing {self.num_vehicles} vehicles...")
        for i in range(self.num_vehicles):
            vehicle_id = f"VEHICLE_{i+1:03d}"
            self.vehicles.append(VehicleState(vehicle_id))
        logger.success(f"Initialized {len(self.vehicles)} vehicles")
    
    async def simulate_vehicle(self, vehicle: VehicleState):
        """
        Simulate a single vehicle's telemetry publishing loop.
        
        Args:
            vehicle: VehicleState instance to simulate
        """
        last_update = asyncio.get_event_loop().time()
        
        while self.running:
            try:
                # Random publish interval between MIN and MAX
                interval = random.uniform(MIN_PUBLISH_INTERVAL, MAX_PUBLISH_INTERVAL)
                await asyncio.sleep(interval)
                
                # Calculate time delta
                current_time = asyncio.get_event_loop().time()
                time_delta = current_time - last_update
                last_update = current_time
                
                # Generate telemetry
                telemetry = vehicle.update(time_delta)
                
                # Publish to MQTT
                topic = f"/vehicle/{vehicle.vehicle_id}/telemetry"
                payload = telemetry.to_json()
                
                result = self.mqtt_client.publish(topic, payload, qos=1)
                
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    logger.debug(f"Published: {vehicle.vehicle_id} - Speed: {telemetry.speed:.1f} km/h, "
                               f"Temp: {telemetry.engine_temp:.1f}°C, RPM: {telemetry.engine_rpm}")
                else:
                    logger.error(f"Failed to publish for {vehicle.vehicle_id}. RC: {result.rc}")
                    self.error_count += 1
                    
            except Exception as e:
                logger.error(f"Error simulating vehicle {vehicle.vehicle_id}: {e}")
                self.error_count += 1
                await asyncio.sleep(1)  # Brief pause before retry
    
    async def monitor_stats(self):
        """Periodically log statistics"""
        last_count = 0
        
        while self.running:
            await asyncio.sleep(10)  # Report every 10 seconds
            
            current_count = self.message_count
            messages_per_sec = (current_count - last_count) / 10.0
            last_count = current_count
            
            logger.info(
                f"📊 Stats - Total Messages: {self.message_count:,} | "
                f"Rate: {messages_per_sec:.2f} msg/s | "
                f"Errors: {self.error_count} | "
                f"Active Vehicles: {len(self.vehicles)}"
            )
    
    async def run(self):
        """Main simulation loop"""
        self.running = True
        logger.info("🚗 Starting Vehicle Telemetry Simulator...")
        
        # Setup MQTT
        self.setup_mqtt()
        await asyncio.sleep(2)  # Give MQTT time to connect
        
        # Initialize vehicles
        self.initialize_vehicles()
        
        # Create tasks for all vehicles + stats monitor
        tasks = [
            asyncio.create_task(self.simulate_vehicle(vehicle))
            for vehicle in self.vehicles
        ]
        tasks.append(asyncio.create_task(self.monitor_stats()))
        
        logger.success(f"✅ Simulator running with {len(self.vehicles)} vehicles")
        logger.info(f"Publishing to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        logger.info(f"Publish interval: {MIN_PUBLISH_INTERVAL}-{MAX_PUBLISH_INTERVAL} seconds")
        logger.info("Press Ctrl+C to stop...")
        
        try:
            # Run until interrupted
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Simulation tasks cancelled")
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down simulator...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        logger.info(f"Final stats - Messages published: {self.message_count}, Errors: {self.error_count}")
        logger.success("Simulator stopped successfully")


# Global simulator instance for signal handling
simulator: Optional[VehicleSimulator] = None


def signal_handler(signum, frame):
    """Handle interrupt signals for graceful shutdown"""
    logger.info(f"\nReceived signal {signum}")
    if simulator:
        simulator.shutdown()
    sys.exit(0)


async def main():
    """Main entry point"""
    global simulator
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run simulator
    simulator = VehicleSimulator(num_vehicles=NUM_VEHICLES)
    
    try:
        await simulator.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        simulator.shutdown()


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Run the simulator
    asyncio.run(main())
