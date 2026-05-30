import csv
from pathlib import Path
import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Query to get chunk count only for hypertables starting with 'energy_readings'
chunk_count_query = """
    SELECT
        hypertable_name,
        COUNT(*) AS chunk_count
    FROM timescaledb_information.chunks
    WHERE hypertable_name LIKE 'energy_readings%'
    GROUP BY hypertable_name
    ORDER BY hypertable_name;
"""

# --- Dynamic Path Logic ---
project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "data"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "energy_chunk_counts.csv"

try:
    conn = psycopg2.connect(config.db_url)
    cursor = conn.cursor()

    logging.info("Querying chunk counts for energy_readings tables...")
    cursor.execute(chunk_count_query)
    rows = cursor.fetchall()

    if not rows:
        logging.warning("No tables found with prefix 'energy_readings'.")
    else:
        # Write to CSV (no header if you prefer, but added for clarity)
        with open(output_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["hypertable_name", "chunk_count"])   # optional header
            for hypertable_name, chunk_count in rows:
                writer.writerow([hypertable_name, chunk_count])

        logging.info(f"Success! Saved to '{output_file}'")

except Exception as e:
    logging.error(f"An error occurred: {e}")

finally:
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals():
        conn.close()