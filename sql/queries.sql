-- Step 3:
-- Query 1: Average power consumption per hour today
SELECT time_bucket('1 hour', timestamp) AS hour,
       AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= DATE_TRUNC('day', NOW())
GROUP BY hour ORDER BY hour;

-- Query 2: Find peak consumption periods in the past week
SELECT time_bucket('15 minutes', timestamp) AS period,
       AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY period
ORDER BY avg_power DESC LIMIT 10;

-- Query 3: Monthly consumption per meter
SELECT meter_id,
       DATE_TRUNC('month', timestamp) as month,
       SUM(energy) as total_energy
FROM energy_readings
GROUP BY meter_id, month
ORDER BY month, total_energy DESC;

-- Query 4: Full dataset scan
SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
FROM energy_readings;



-- Step 4: Chunk Interval Experimentation
CREATE TABLE energy_readings_3h (LIKE energy_readings INCLUDING
ALL);

CREATE TABLE energy_readings_week (LIKE energy_readings INCLUDING
ALL);

SELECT create_hypertable('energy_readings_3h', 'timestamp',
chunk_time_interval => INTERVAL '3 hours');

SELECT create_hypertable('energy_readings_week', 'timestamp',
chunk_time_interval => INTERVAL '1 week');​



-- Step 5: Compression Implementation
-- Check the storage size of the hypertables before compression
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size(format('%I', hypertable_name)::regclass))
FROM timescaledb_information.hypertables;

-- Compress hypertable and add a compression policy
ALTER TABLE energy_readings SET (
    timescaledb.compress = true,
    timescaledb.compress_orderby = 'timestamp DESC'
);
SELECT add_compression_policy('energy_readings', INTERVAL '24 hours');

ALTER TABLE energy_readings_3h SET (
    timescaledb.compress = true,
    timescaledb.compress_orderby = 'timestamp DESC'
);
SELECT add_compression_policy('energy_readings_3h', INTERVAL '24 hours');

ALTER TABLE energy_readings_week SET (
    timescaledb.compress = true,
    timescaledb.compress_orderby = 'timestamp DESC'
);
SELECT add_compression_policy('energy_readings_week', INTERVAL '24 hours');

-- Check the storage size of the hypertables after compression
SELECT
    hypertable_name,
    pg_size_pretty(hypertable_size(format('%I', hypertable_name)::regclass))
FROM timescaledb_information.hypertables;

-- select queries to run for the report on 1 day, 3 hour, and 1 week compressed hypertables
-- 1 day compressed hypertable
SELECT time_bucket('1 hour', timestamp) AS hour, AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= DATE_TRUNC('day', NOW())
GROUP BY hour ORDER BY hour;

SELECT time_bucket('15 minutes', timestamp) AS period, AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY period ORDER BY avg_power DESC LIMIT 10;

SELECT meter_id, DATE_TRUNC('month', timestamp) as month, SUM(energy) as total_energy
FROM energy_readings
GROUP BY meter_id, month
ORDER BY month, total_energy DESC;

SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
FROM energy_readings;

-- 3 hour compressed hypertable
SELECT time_bucket('1 hour', timestamp) AS hour, AVG(power) as avg_power
FROM energy_readings_3h
WHERE timestamp >= DATE_TRUNC('day', NOW())
GROUP BY hour ORDER BY hour;

SELECT time_bucket('15 minutes', timestamp) AS period, AVG(power) as avg_power
FROM energy_readings_3h
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY period ORDER BY avg_power DESC LIMIT 10;

SELECT meter_id, DATE_TRUNC('month', timestamp) as month, SUM(energy) as total_energy
FROM energy_readings_3h
GROUP BY meter_id, month
ORDER BY month, total_energy DESC;

SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
FROM energy_readings_3h;

-- 1 week compressed hypertable
SELECT time_bucket('1 hour', timestamp) AS hour, AVG(power) as avg_power
FROM energy_readings_week
WHERE timestamp >= DATE_TRUNC('day', NOW())
GROUP BY hour ORDER BY hour;

SELECT time_bucket('15 minutes', timestamp) AS period, AVG(power) as avg_power
FROM energy_readings_week
WHERE timestamp >= NOW() - INTERVAL '7 days'
GROUP BY period ORDER BY avg_power DESC LIMIT 10;

SELECT meter_id, DATE_TRUNC('month', timestamp) as month, SUM(energy) as total_energy
FROM energy_readings_week
GROUP BY meter_id, month
ORDER BY month, total_energy DESC;

SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
FROM energy_readings_week;

-- Manually compression of chunks older than 24 hours for all three hypertables
-- For energy_readings
SELECT compress_chunk(chunk) 
FROM show_chunks('energy_readings', older_than => INTERVAL '24 hours') AS chunk;

-- For energy_readings_3h
SELECT compress_chunk(chunk) 
FROM show_chunks('energy_readings_3h', older_than => INTERVAL '24 hours') AS chunk;

-- For energy_readings_week
SELECT compress_chunk(chunk) 
FROM show_chunks('energy_readings_week', older_than => INTERVAL '24 hours') AS chunk;



-- Step 6: Continuous Aggregations

-- Drop the 15-minute materialized view if it already exists to allow a clean recreation
DROP MATERIALIZED VIEW IF EXISTS energy_readings_15min CASCADE;

-- Create a continuous aggregate materialized view for 15-minute interval metrics
CREATE MATERIALIZED VIEW energy_readings_15min
WITH (timescaledb.continuous) AS
SELECT 
    meter_id,
    time_bucket('15 minutes', timestamp) AS bucket,
    AVG(power) AS avg_power,
    MAX(power) AS max_power,
    SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

-- Drop the hourly materialized view if it already exists to allow a clean recreation
DROP MATERIALIZED VIEW IF EXISTS energy_readings_hourly CASCADE;

-- Create a continuous aggregate materialized view for 1-hour interval metrics
CREATE MATERIALIZED VIEW energy_readings_hourly
WITH (timescaledb.continuous) AS
SELECT 
    meter_id,
    time_bucket('1 hour', timestamp) AS bucket,
    AVG(power) AS avg_power,
    MAX(power) AS max_power,
    SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

-- Drop the daily materialized view if it already exists to allow a clean recreation
DROP MATERIALIZED VIEW IF EXISTS energy_readings_daily CASCADE;

-- Create a continuous aggregate materialized view for 1-day interval metrics
CREATE MATERIALIZED VIEW energy_readings_daily
WITH (timescaledb.continuous) AS
SELECT 
    meter_id,
    time_bucket('1 day', timestamp) AS bucket,
    AVG(power) AS avg_power,
    MAX(power) AS max_power,
    SUM(energy) AS total_energy
FROM energy_readings
GROUP BY meter_id, bucket;

-- Remove any existing refresh policy on the 15-minute view to avoid duplicate policy errors
SELECT remove_continuous_aggregate_policy('energy_readings_15min', if_exists => true);

-- Add a policy to refresh the 15-minute view every 15 minutes, covering data from 3 days ago up to now
SELECT add_continuous_aggregate_policy('energy_readings_15min',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '15 minutes');

-- Remove any existing refresh policy on the hourly view to avoid duplicate policy errors
SELECT remove_continuous_aggregate_policy('energy_readings_hourly', if_exists => true);

-- Add a policy to refresh the hourly view every hour, covering data from 7 days ago up to now
SELECT add_continuous_aggregate_policy('energy_readings_hourly',
    start_offset => INTERVAL '7 days',
    end_offset => INTERVAL '0 minutes',
    schedule_interval => INTERVAL '1 hour');

-- Remove any existing refresh policy on the daily view to avoid duplicate policy errors
SELECT remove_continuous_aggregate_policy('energy_readings_daily', if_exists => true);

-- Add a policy to refresh the daily view every day, covering data from 30 days ago up to 1 hour ago
SELECT add_continuous_aggregate_policy('energy_readings_daily',
    start_offset => INTERVAL '30 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day');

-- 15-Minute Raw Query: Aggregates raw data on the fly for meter '10000000500' over the past 1 day
SELECT meter_id, time_bucket('15 minutes', timestamp) AS bucket, AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '1 day'
  AND meter_id = '10000000500'
GROUP BY meter_id, bucket
ORDER BY bucket;

-- 15-Minute Aggregate Query: Fetches pre-computed 15-minute data for meter '10000000500' over the past 1 day
SELECT meter_id, bucket, avg_power
FROM energy_readings_15min
WHERE bucket >= NOW() - INTERVAL '1 day'
  AND meter_id = '10000000500'
ORDER BY bucket;

-- Hourly Raw Query: Aggregates raw data on the fly for meter '10000000500' over the past 7 days
SELECT meter_id, time_bucket('1 hour', timestamp) AS bucket, AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '7 days'
  AND meter_id = '10000000500'
GROUP BY meter_id, bucket
ORDER BY bucket;

-- Hourly Aggregate Query: Fetches pre-computed hourly data for meter '10000000500' over the past 7 days
SELECT meter_id, bucket, avg_power
FROM energy_readings_hourly
WHERE bucket >= NOW() - INTERVAL '7 days'
  AND meter_id = '10000000500'
ORDER BY bucket;

-- Daily Raw Query: Aggregates raw data on the fly for meter '10000000500' over the past 30 days
SELECT meter_id, time_bucket('1 day', timestamp) AS bucket, AVG(power) as avg_power
FROM energy_readings
WHERE timestamp >= NOW() - INTERVAL '30 days'
  AND meter_id = '10000000500'
GROUP BY meter_id, bucket
ORDER BY bucket;

-- Daily Aggregate Query: Fetches pre-computed daily data for meter '10000000500' over the past 30 days
SELECT meter_id, bucket, avg_power
FROM energy_readings_daily
WHERE bucket >= NOW() - INTERVAL '30 days'
  AND meter_id = '10000000500'
ORDER BY bucket;
