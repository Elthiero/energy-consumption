import logging
import psycopg2
from config.config import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Define the views with their SQL
VIEWS = {
    "energy_readings_15min": """
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
    """,
    "energy_readings_hourly": """
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
    """,
    "energy_readings_daily": """
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
    """,
}

# Refresh policies (view name -> policy parameters)
POLICIES = {
    "energy_readings_15min": {
        "start_offset": "INTERVAL '3 days'",
        "end_offset": "INTERVAL '0 minutes'",
        "schedule_interval": "INTERVAL '15 minutes'",
    },
    "energy_readings_hourly": {
        "start_offset": "INTERVAL '7 days'",
        "end_offset": "INTERVAL '0 minutes'",
        "schedule_interval": "INTERVAL '1 hour'",
    },
    "energy_readings_daily": {
        "start_offset": "INTERVAL '30 days'",
        "end_offset": "INTERVAL '1 day'",
        "schedule_interval": "INTERVAL '1 day'",
    },
}


def drop_view_if_exists(cursor, view_name):
    """Drop the materialized view if it exists (to allow recreation)."""
    cursor.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name} CASCADE;")
    logging.info(f"Dropped existing view '{view_name}' (if any).")


def create_view(cursor, view_name, view_sql):
    """Create the continuous aggregate view."""
    logging.info(f"Creating view: {view_name}")
    cursor.execute(view_sql)
    logging.info(f"View '{view_name}' created successfully.")


def add_policy(cursor, view_name, policy_params):
    """Add a refresh policy for the continuous aggregate."""
    # First, remove any existing policy on this view to avoid duplicates
    cursor.execute(
        f"SELECT remove_continuous_aggregate_policy('{view_name}', if_exists => true);"
    )

    sql = f"""
        SELECT add_continuous_aggregate_policy('{view_name}',
            start_offset => {policy_params['start_offset']},
            end_offset => {policy_params['end_offset']},
            schedule_interval => {policy_params['schedule_interval']});
    """
    logging.info(
        f"Adding policy to '{view_name}': start={policy_params['start_offset']}, end={policy_params['end_offset']}, interval={policy_params['schedule_interval']}"
    )
    cursor.execute(sql)
    result = cursor.fetchone()
    logging.info(f"Policy added with job_id = {result[0]}")


def main():
    try:
        conn = psycopg2.connect(config.db_url)
        # Autocommit is needed for DDL (CREATE/DROP MATERIALIZED VIEW)
        conn.autocommit = True
        cursor = conn.cursor()

        # Check if TimescaleDB extension is installed
        cursor.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'timescaledb';"
        )
        if not cursor.fetchone():
            logging.error("TimescaleDB extension is not installed in this database.")
            return

        # Step 1: Create views (optionally drop existing ones)
        for view_name, view_sql in VIEWS.items():
            drop_view_if_exists(cursor, view_name)  # comment out to keep existing data
            create_view(cursor, view_name, view_sql)

        # Step 2: Add refresh policies
        for view_name, policy_params in POLICIES.items():
            add_policy(cursor, view_name, policy_params)

        logging.info(
            "All continuous aggregates and policies have been set up successfully."
        )

    except Exception as e:
        logging.error(f"An error occurred: {e}")
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    main()
