import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

HYPERTABLES = [
    "energy_readings",
    "energy_readings_3h",
    "energy_readings_week",
]

# SQL statements
COMPRESS_SETTINGS = """
    ALTER TABLE {table} SET (
        timescaledb.compress = true,
        -- timescaledb.compress_orderby = 'meter_id, timestamp DESC'
        timescaledb.compress_orderby = 'timestamp DESC',
    );
"""

ADD_POLICY = """
    SELECT add_compression_policy('{table}', INTERVAL '24 hours', if_not_exists => true);
"""


def enable_compression(table_name):
    """Enable compression on a single hypertable and add policy (idempotent)."""
    logging.info(f"Processing hypertable: {table_name}")
    try:
        # Set compression attributes (safe to run multiple times)
        cursor.execute(COMPRESS_SETTINGS.format(table=table_name))
        logging.info(f"Compression enabled on {table_name}")

        # Add compression policy (now idempotent)
        cursor.execute(ADD_POLICY.format(table=table_name))
        policy_result = cursor.fetchone()
        logging.info(
            f"Compression policy added (policy_id={policy_result[0] if policy_result else 'unknown'})"
        )
    except Exception as e:
        logging.error(f"Failed on {table_name}: {e}")
        raise
    
def compress_existing_chunks(table_name, older_than=None):
    """Compress all chunks, skipping already compressed ones."""
    if older_than:
        query = f"""
            SELECT compress_chunk(c, if_not_compressed => true)
            FROM show_chunks('{table_name}', older_than => INTERVAL '{older_than}')
            AS c
        """
    else:
        query = f"""
            SELECT compress_chunk(c, if_not_compressed => true)
            FROM show_chunks('{table_name}')
            AS c
        """
    cursor.execute(query)
    # compress_chunk returns the chunk name if compressed, else NULL
    compressed_count = sum(1 for row in cursor.fetchall() if row[0] is not None)
    logging.info(f"Compressed {compressed_count} chunks on {table_name}.")


if __name__ == "__main__":
    try:
        conn = psycopg2.connect(config.db_url)
        conn.autocommit = True
        cursor = conn.cursor()

        for ht in HYPERTABLES:
            enable_compression(ht)
            compress_existing_chunks(ht)

        logging.info("Compression successfully applied to all hypertables.")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()
