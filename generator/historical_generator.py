import logging
from datetime import datetime, timedelta, timezone
from tqdm import tqdm  # to show progress bar

from config.config import config
from generator.generator import (
    generate_reading,
    get_all_meter_ids,
    reset_simulator,
)
from database.db_writer import DatabaseWriter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def generate_historical():
    reset_simulator()  # start with fresh cumulative energies

    # Date range: from N weeks ago to yesterday (inclusive, 00:00:00 to 23:59:59)
    end_date = datetime.now(timezone.utc).replace(
        hour=23, minute=59, second=59, microsecond=0
    ) - timedelta(days=1)
    start_date = (
        end_date - timedelta(weeks=config.HISTORICAL_WEEKS) + timedelta(seconds=1)
    )

    step = timedelta(seconds=config.PUBLISH_INTERVAL_SEC)
    logging.info(f"Generating from {start_date} to {end_date} (interval {step})")

    meter_ids = get_all_meter_ids(config.NUM_METERS)
    total_meters = len(meter_ids)
    logging.info(f"Number of meters: {total_meters}")

    db = DatabaseWriter()
    batch = []
    batch_size = 10000
    total_readings = 0

    # Pre‑compute total timestamps for progress bar
    num_steps = int((end_date - start_date).total_seconds() / step.total_seconds()) + 1
    total_expected = total_meters * num_steps
    logging.info(f"Total readings to generate: {total_expected:,}")

    with tqdm(total=total_expected, desc="Progress") as pbar:
        current_ts = start_date
        while current_ts <= end_date:
            for meter_id in meter_ids:
                reading = generate_reading(meter_id, current_ts)
                batch.append(reading)
                total_readings += 1
                pbar.update(1)

                if len(batch) >= batch_size:
                    db.insert_batch(batch)
                    batch.clear()

            current_ts += step

        # Insert any remaining readings
        if batch:
            db.insert_batch(batch)

    logging.info(f"Done. Inserted {total_readings:,} rows.")
    db.close()


if __name__ == "__main__":
    generate_historical()
