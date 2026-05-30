import logging
import psycopg2
import psycopg2.extras
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class DatabaseWriter:
    def __init__(self):
        """Create persistent connection to PostgreSQL."""
        try:
            self.conn = psycopg2.connect(config.db_url)
            self.conn.autocommit = True  # each insert commits immediately
            self.cursor = self.conn.cursor()
            logging.info("Connected to PostgreSQL.")
        except Exception as e:
            logging.error(f"DB connection failed: {e}")
            raise

    def insert_reading(self, data: dict):
        """Insert a single reading (used by subscriber)."""
        query = """
            INSERT INTO energy_readings
            (meter_id, timestamp, power, voltage, current, frequency, energy)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            data["meter_id"],
            data["timestamp"],
            data["power"],
            data["voltage"],
            data["current"],
            data["frequency"],
            data["energy"],
        )
        try:
            self.cursor.execute(query, values)
        except Exception as e:
            logging.error(f"Insert failed for meter {data['meter_id']}: {e}")

    def insert_batch(self, readings: list):
        """
        Bulk insert many readings.
        readings: list of dicts, each dict has the same keys as a single reading.
        """
        if not readings:
            return
        query = """
            INSERT INTO energy_readings
            (meter_id, timestamp, power, voltage, current, frequency, energy)
            VALUES %s
        """
        values_list = [
            (
                r["meter_id"],
                r["timestamp"],
                r["power"],
                r["voltage"],
                r["current"],
                r["frequency"],
                r["energy"],
            )
            for r in readings
        ]
        try:
            psycopg2.extras.execute_values(
                self.cursor, query, values_list, page_size=10000
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"Batch insert failed: {e}")
        
    def get_last_energies(self) -> dict:
        """
        Read the last known energy value for every meter.
        Uses DISTINCT ON to get one row per meter (the most recent).
        """
        query = """
            SELECT DISTINCT ON (meter_id) meter_id, energy
            FROM energy_readings
            ORDER BY meter_id, timestamp DESC
        """
        self.cursor.execute(query)
        rows = self.cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    def close(self):
        """Close cursor and connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")
