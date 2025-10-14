-- ClickHouse Schema Initialization for Phase 2
-- Automotive Predictive Maintenance - Telemetry Storage
-- Creates Kafka Engine table, MergeTree persistent storage, and materialized view

-- Create database if not exists
CREATE DATABASE IF NOT EXISTS telemetry_db;

-- Use the telemetry database
USE telemetry_db;

-- ============================================================================
-- 1. KAFKA ENGINE TABLE - Direct consumption from Kafka topic
-- ============================================================================
-- This table reads directly from Kafka topic 'vehicle_telemetry_clean'
-- Data flows through this table into the MergeTree table via materialized view

CREATE TABLE IF NOT EXISTS telemetry_kafka (
    vehicle_id String,
    timestamp DateTime,
    engine_rpm Int32,
    engine_temp Float32,
    vibration Float32,
    speed Float32,
    gps_lat Float32,
    gps_lon Float32,
    fuel_level Float32,
    battery_voltage Float32,
    rolling_avg_rpm Float32,
    rolling_avg_temp Float32,
    rolling_avg_vibration Float32,
    rolling_avg_speed Float32
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'kafka:9093',
    kafka_topic_list = 'vehicle_telemetry_clean',
    kafka_group_name = 'clickhouse_consumer',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 4,
    kafka_skip_broken_messages = 100;

-- ============================================================================
-- 2. MERGETREE TABLE - Persistent storage with optimized queries
-- ============================================================================
-- Primary storage table with partitioning by date and ordering by vehicle_id/timestamp
-- Optimized for time-series queries and analytics

CREATE TABLE IF NOT EXISTS telemetry (
    vehicle_id String,
    timestamp DateTime,
    engine_rpm Int32,
    engine_temp Float32,
    vibration Float32,
    speed Float32,
    gps_lat Float32,
    gps_lon Float32,
    fuel_level Float32,
    battery_voltage Float32,
    
    -- Rolling averages from Phase 1 enrichment
    rolling_avg_rpm Float32,
    rolling_avg_temp Float32,
    rolling_avg_vibration Float32,
    rolling_avg_speed Float32,
    
    -- Metadata
    received_at DateTime DEFAULT now(),
    ingestion_date Date DEFAULT toDate(now()),
    
    -- Computed columns for analytics
    engine_health_score Float32 DEFAULT 
        100 - (engine_temp / 110 * 20) - (vibration / 10 * 20) - ((7500 - engine_rpm) / 7500 * 10),
    battery_health_status String DEFAULT 
        multiIf(
            battery_voltage < 11.0, 'CRITICAL',
            battery_voltage < 11.5, 'WARNING',
            battery_voltage < 12.0, 'LOW',
            'NORMAL'
        ),
    fuel_status String DEFAULT
        multiIf(
            fuel_level < 5, 'CRITICAL',
            fuel_level < 15, 'WARNING',
            fuel_level < 25, 'LOW',
            'NORMAL'
        )
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (vehicle_id, timestamp)
TTL timestamp + INTERVAL 90 DAY  -- Data retention: 90 days
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 3. MATERIALIZED VIEW - Auto-transfer from Kafka to MergeTree
-- ============================================================================
-- Automatically consumes from telemetry_kafka and inserts into telemetry table
-- This runs continuously as new messages arrive

CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_mv TO telemetry AS
SELECT
    vehicle_id,
    timestamp,
    engine_rpm,
    engine_temp,
    vibration,
    speed,
    gps_lat,
    gps_lon,
    fuel_level,
    battery_voltage,
    rolling_avg_rpm,
    rolling_avg_temp,
    rolling_avg_vibration,
    rolling_avg_speed,
    now() AS received_at,
    toDate(now()) AS ingestion_date
FROM telemetry_kafka;

-- ============================================================================
-- 4. ANOMALIES TABLE - Store detected anomalies for quick access
-- ============================================================================

CREATE TABLE IF NOT EXISTS anomalies (
    vehicle_id String,
    timestamp DateTime,
    anomaly_type String,  -- 'HIGH_TEMP', 'LOW_BATTERY', 'HIGH_VIBRATION', etc.
    severity String,      -- 'CRITICAL', 'WARNING', 'INFO'
    metric_name String,
    metric_value Float32,
    threshold Float32,
    message String,
    detected_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (vehicle_id, timestamp, severity)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- ============================================================================
-- 5. AGGREGATED VIEWS - Pre-computed analytics for dashboards
-- ============================================================================

-- Hourly aggregates for dashboard performance
CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(timestamp_hour)
ORDER BY (vehicle_id, timestamp_hour)
AS SELECT
    vehicle_id,
    toStartOfHour(timestamp) AS timestamp_hour,
    count() AS message_count,
    avg(engine_rpm) AS avg_rpm,
    avg(engine_temp) AS avg_temp,
    avg(vibration) AS avg_vibration,
    avg(speed) AS avg_speed,
    avg(fuel_level) AS avg_fuel,
    avg(battery_voltage) AS avg_battery,
    max(engine_temp) AS max_temp,
    max(vibration) AS max_vibration,
    min(battery_voltage) AS min_battery,
    min(fuel_level) AS min_fuel
FROM telemetry
GROUP BY vehicle_id, timestamp_hour;

-- Fleet-wide statistics (all vehicles combined)
CREATE MATERIALIZED VIEW IF NOT EXISTS fleet_stats_hourly
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(timestamp_hour)
ORDER BY timestamp_hour
AS SELECT
    toStartOfHour(timestamp) AS timestamp_hour,
    count() AS total_messages,
    uniq(vehicle_id) AS active_vehicles,
    avg(engine_temp) AS fleet_avg_temp,
    avg(battery_voltage) AS fleet_avg_battery,
    avg(fuel_level) AS fleet_avg_fuel,
    countIf(battery_voltage < 11.5) AS low_battery_count,
    countIf(fuel_level < 15) AS low_fuel_count,
    countIf(engine_temp > 100) AS high_temp_count
FROM telemetry
GROUP BY timestamp_hour;

-- ============================================================================
-- 6. INDEXES - Optimize query performance
-- ============================================================================

-- Create skip index for faster filtering by vehicle_id
ALTER TABLE telemetry ADD INDEX IF NOT EXISTS vehicle_id_idx vehicle_id TYPE set(0) GRANULARITY 4;

-- Create skip index for timestamp range queries
ALTER TABLE telemetry ADD INDEX IF NOT EXISTS timestamp_idx timestamp TYPE minmax GRANULARITY 1;

-- ============================================================================
-- 7. PHASE 3 - PREDICTIVE MAINTENANCE TABLES
-- ============================================================================

-- Table for storing ML predictions
CREATE TABLE IF NOT EXISTS vehicle_predictions (
    vehicle_id String,
    timestamp DateTime,
    failure_probability Float32,
    health_status String,  -- 'Healthy', 'Warning', 'Critical'
    engine_temp Float32,
    vibration Float32,
    engine_rpm Float32,
    speed Float32,
    fuel_level Float32,
    battery_voltage Float32,
    reason String,
    model_version String DEFAULT '1.0.0',
    predicted_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (vehicle_id, timestamp)
TTL timestamp + INTERVAL 180 DAY
SETTINGS index_granularity = 8192;

-- Table for storing critical alerts
CREATE TABLE IF NOT EXISTS vehicle_alerts (
    alert_id String DEFAULT generateUUIDv4(),
    vehicle_id String,
    timestamp DateTime,
    failure_probability Float32,
    health_status String,
    reason String,
    severity String,  -- 'WARNING', 'CRITICAL'
    acknowledged Bool DEFAULT false,
    acknowledged_at Nullable(DateTime),
    acknowledged_by Nullable(String),
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, vehicle_id)
TTL timestamp + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Index for fast alert queries
ALTER TABLE vehicle_alerts ADD INDEX IF NOT EXISTS alert_status_idx acknowledged TYPE set(0) GRANULARITY 4;

-- Materialized view for hourly prediction aggregates
CREATE MATERIALIZED VIEW IF NOT EXISTS prediction_stats_hourly
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(timestamp_hour)
ORDER BY (timestamp_hour, vehicle_id)
AS SELECT
    toStartOfHour(timestamp) AS timestamp_hour,
    vehicle_id,
    avg(failure_probability) AS avg_failure_prob,
    max(failure_probability) AS max_failure_prob,
    countIf(health_status = 'Critical') AS critical_count,
    countIf(health_status = 'Warning') AS warning_count,
    countIf(health_status = 'Healthy') AS healthy_count
FROM vehicle_predictions
GROUP BY timestamp_hour, vehicle_id;

-- ============================================================================
-- 8. INITIAL STATISTICS
-- ============================================================================

-- Query to verify setup (run after data ingestion starts)
-- SELECT 'Setup Complete!' AS status;
-- SELECT count() AS kafka_table_exists FROM system.tables WHERE name = 'telemetry_kafka' AND database = 'telemetry_db';
-- SELECT count() AS mergetree_table_exists FROM system.tables WHERE name = 'telemetry' AND database = 'telemetry_db';
-- SELECT count() AS materialized_view_exists FROM system.tables WHERE name = 'telemetry_mv' AND database = 'telemetry_db';
-- SELECT count() AS predictions_table_exists FROM system.tables WHERE name = 'vehicle_predictions' AND database = 'telemetry_db';
-- SELECT count() AS alerts_table_exists FROM system.tables WHERE name = 'vehicle_alerts' AND database = 'telemetry_db';

