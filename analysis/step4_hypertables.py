import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

setup_sql = """
-- Create the 3-hour table and hypertable
CREATE TABLE IF NOT EXISTS energy_readings_3h (LIKE energy_readings INCLUDING ALL);
SELECT create_hypertable('energy_readings_3h', 'timestamp', chunk_time_interval => INTERVAL '3 hours', if_not_exists => TRUE);

-- Create the 1-week table and hypertable
CREATE TABLE IF NOT EXISTS energy_readings_week (LIKE energy_readings INCLUDING ALL);
SELECT create_hypertable('energy_readings_week', 'timestamp', chunk_time_interval => INTERVAL '1 week', if_not_exists => TRUE);
"""

copy_sql = """
-- Copy data safely if the target tables are empty
INSERT INTO energy_readings_3h SELECT * FROM energy_readings ON CONFLICT DO NOTHING;
INSERT INTO energy_readings_week SELECT * FROM energy_readings ON CONFLICT DO NOTHING;
"""

try:
    logging.info("Connecting to database...")
    conn = psycopg2.connect(config.db_url)
    conn.autocommit = True
    cursor = conn.cursor()
    
    logging.info("Creating tables and hypertables...")
    cursor.execute(setup_sql)
    
    logging.info("Migrating identical data across hypertables (this may take a moment)...")
    cursor.execute(copy_sql)
    
    logging.info("Setup completed successfully!")
except Exception as e:
    logging.error(f"Error during setup: {e}")
finally:
    if 'cursor' in locals(): cursor.close()
    if 'conn' in locals(): conn.close()
