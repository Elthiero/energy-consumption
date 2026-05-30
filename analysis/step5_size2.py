import csv
from pathlib import Path
import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Query to get hypertable names and their total size (pretty printed)
hypertable_query = """
    SELECT
        hypertable_name,
        pg_size_pretty(hypertable_size(format('%I', hypertable_name)::regclass))
    FROM timescaledb_information.hypertables;
"""

# --- Dynamic Path Logic ---
project_root = Path(__file__).resolve().parent.parent
output_dir = project_root / "data"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "hypertable_sizes2.csv"

try:
    # Connect to the database
    conn = psycopg2.connect(config.db_url)
    cursor = conn.cursor()

    logging.info("Fetching hypertable sizes...")
    cursor.execute(hypertable_query)
    rows = cursor.fetchall()

    # Write to CSV
    with open(output_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hypertable_name", "total_size"])

        for row in rows:
            hypertable_name, total_size = row
            writer.writerow([hypertable_name, total_size])

    logging.info(f"Success! Hypertable sizes saved to '{output_file}'")

except Exception as e:
    logging.error(f"An error occurred: {e}")

finally:
    if "cursor" in locals():
        cursor.close()
    if "conn" in locals():
        conn.close()
