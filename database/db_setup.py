import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

SQL = """
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create the base table
CREATE TABLE IF NOT EXISTS energy_readings (
    meter_id   TEXT         NOT NULL,
    timestamp  TIMESTAMPTZ  NOT NULL,
    power      FLOAT,
    voltage    FLOAT,
    current    FLOAT,
    frequency  FLOAT,
    energy     FLOAT
);

-- Convert to hypertable (1-day chunks, safe to re-run)
SELECT create_hypertable(
    'energy_readings',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE,
    migrate_data        => TRUE
);

-- Add unique constraint to prevent duplicates (one reading per meter per timestamp)
ALTER TABLE energy_readings ADD CONSTRAINT energy_readings_pk 
    PRIMARY KEY (meter_id, timestamp);

-- Index for fast per-meter queries (used by get_last_energies)
CREATE INDEX IF NOT EXISTS idx_energy_readings_meter_ts
    ON energy_readings (meter_id, timestamp DESC);
"""


def setup():
    try:
        conn = psycopg2.connect(config.db_url)
        conn.autocommit = True  # DDL must run outside a transaction block
        cursor = conn.cursor()

        logging.info("Running schema setup...")
        cursor.execute(SQL)
        logging.info("Schema ready. energy_readings hypertable is set up.")

    except Exception as e:
        logging.error(f"Setup failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
        logging.info("Connection closed.")


if __name__ == "__main__":
    setup()
