import csv
from pathlib import Path
import logging
import time
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define your queries
queries = {
    "Query 1: Hourly Average Today": """
        SELECT time_bucket('1 hour', timestamp) AS hour, AVG(power) as avg_power
        FROM energy_readings
        WHERE timestamp >= DATE_TRUNC('day', NOW())
        GROUP BY hour ORDER BY hour;
    """,
    "Query 2: Peak Weekly 15m": """
        SELECT time_bucket('15 minutes', timestamp) AS period, AVG(power) as avg_power
        FROM energy_readings
        WHERE timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY period ORDER BY avg_power DESC LIMIT 10;
    """,
    "Query 3: Monthly Meter Summary": """
        SELECT meter_id, DATE_TRUNC('month', timestamp) as month, SUM(energy) as total_energy
        FROM energy_readings
        GROUP BY meter_id, month
        ORDER BY month, total_energy DESC;
    """,
    "Query 4: Full Dataset Scan": """
        SELECT COUNT(*), AVG(power), MAX(power), MIN(power)
        FROM energy_readings;
    """,
}

# --- Dynamic Path Logic ---
# Finds the root directory (where analysis/, broker/, data/, etc. live)
project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "data"

# Safely create the data directory if it is missing
output_dir.mkdir(parents=True, exist_ok=True)

# Define the absolute file path to data/compressed_1day.csv
output_file = output_dir / "compressed_1day.csv"
# ---------------------------

try:
    # Connect to the database
    conn = psycopg2.connect(config.db_url)
    cursor = conn.cursor()

    # Open CSV file for writing (Path objects are supported natively by open())
    with open(output_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        # Write CSV Header
        writer.writerow(["query_name", "execution_time_ms"])

        # Execute and time each query
        for name, sql in queries.items():
            logging.info(f"Running {name}...")

            # Start timer
            start_time = time.perf_counter()

            # Execute query and fetch results to ensure full processing
            cursor.execute(sql)
            cursor.fetchall()

            # Stop timer
            end_time = time.perf_counter()

            # Calculate duration in milliseconds
            duration_ms = (end_time - start_time) * 1000

            # Save to CSV
            writer.writerow([name, round(duration_ms, 2)])
            logging.info(f"Finished in {duration_ms:.2f} ms")

    logging.info(f"Success! Benchmarks saved to '{output_file}'")

except Exception as e:
    logging.error(f"An error occurred: {e}")

finally:
    # Clean up connections
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals():
        conn.close()
