import csv
from pathlib import Path
import logging
import time
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# 1. Define the target meter ID here
TARGET_METER = "10000000500" 

# Define the paired queries
QUERY_RAW_15MIN = """
    SELECT meter_id, time_bucket('15 minutes', timestamp) AS bucket, AVG(power) as avg_power
    FROM energy_readings
    WHERE timestamp >= NOW() - INTERVAL '1 day'
      AND meter_id = '{meter_id}'
    GROUP BY meter_id, bucket
    ORDER BY bucket;
"""

QUERY_AGG_15MIN = """
    SELECT meter_id, bucket, avg_power
    FROM energy_readings_15min
    WHERE bucket >= NOW() - INTERVAL '1 day'
      AND meter_id = '{meter_id}'
    ORDER BY bucket;
"""

# You can add similar pairs for hourly and daily aggregates
QUERY_RAW_HOURLY = """
    SELECT meter_id, time_bucket('1 hour', timestamp) AS bucket, AVG(power) as avg_power
    FROM energy_readings
    WHERE timestamp >= NOW() - INTERVAL '7 days'
      AND meter_id = '{meter_id}'
    GROUP BY meter_id, bucket
    ORDER BY bucket;
"""

QUERY_AGG_HOURLY = """
    SELECT meter_id, bucket, avg_power
    FROM energy_readings_hourly
    WHERE bucket >= NOW() - INTERVAL '7 days'
      AND meter_id = '{meter_id}'
    ORDER BY bucket;
"""

QUERY_RAW_DAILY = """
    SELECT meter_id, time_bucket('1 day', timestamp) AS bucket, AVG(power) as avg_power
    FROM energy_readings
    WHERE timestamp >= NOW() - INTERVAL '30 days'
      AND meter_id = '{meter_id}'
    GROUP BY meter_id, bucket
    ORDER BY bucket;
"""

QUERY_AGG_DAILY = """
    SELECT meter_id, bucket, avg_power
    FROM energy_readings_daily
    WHERE bucket >= NOW() - INTERVAL '30 days'
      AND meter_id = '{meter_id}'
    ORDER BY bucket;
"""

PAIRS = [
    ("15min - raw", QUERY_RAW_15MIN),
    ("15min - continuous aggregate", QUERY_AGG_15MIN),
    ("hourly - raw", QUERY_RAW_HOURLY),
    ("hourly - continuous aggregate", QUERY_AGG_HOURLY),
    ("daily - raw", QUERY_RAW_DAILY),
    ("daily - continuous aggregate", QUERY_AGG_DAILY),
]

project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "data"
output_dir.mkdir(parents=True, exist_ok=True)
output_file = output_dir / "continuous_agg_benchmark.csv"

try:
    conn = psycopg2.connect(config.db_url)
    cursor = conn.cursor()

    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["query_description", "execution_time_ms"])

        # Warm up the cache? For fair comparison, run each query once cold.
        # TimescaleDB will cache the aggregate data after first use.
        # If you want cold results, restart PostgreSQL before running.
        for desc, sql in PAIRS:
            logging.info(f"Running: {desc}")
            start = time.perf_counter()
            cursor.execute(sql)
            cursor.fetchall()
            elapsed_ms = (time.perf_counter() - start) * 1000
            writer.writerow([desc, round(elapsed_ms, 2)])
            logging.info(f"Finished in {elapsed_ms:.2f} ms")

    logging.info(f"Benchmark saved to {output_file}")

except Exception as e:
    logging.error(f"An error occurred: {e}")
finally:
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals():
        conn.close()
