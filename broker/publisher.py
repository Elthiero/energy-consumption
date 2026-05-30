import time
import json
import logging
from datetime import datetime, timezone
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from config.config import config
from generator.generator import generate_reading, get_all_meter_ids, seed_from_db
from database.db_writer import DatabaseWriter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def on_connect(client, userdata, flags, reasonCode, properties=None):
    """Callback on connection to MQTT broker."""
    if reasonCode == 0:
        logging.info(
            f"Connected to MQTT broker at {config.MQTT_HOST}:{config.MQTT_PORT}"
        )
    else:
        logging.error(f"Connection failed with code {reasonCode}")


def start_publisher():
    """Initialise MQTT client and start the infinite publishing loop."""
    # Create client
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="smart_meter_simulator")
    client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
    client.on_connect = on_connect

    # Connect to broker
    try:
        client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
        client.loop_start()  # background thread for network traffic
    except Exception as e:
        logging.error(f"Unable to connect: {e}")
        return

    meter_ids = get_all_meter_ids(config.NUM_METERS)

    #logging.info(f"Loaded {len(meter_ids)} meters. Starting simulation...")
    
    # Seed energy cache from DB
    db = DatabaseWriter()
    last_energies = db.get_last_energies()
    db.close()
    
    if last_energies:
        seed_from_db(last_energies, datetime.now(timezone.utc))
        logging.info(f"Resuming from historical data ({len(last_energies)} meters).")
    else:
        logging.info("No historical data found. Fresh baselines will be used.")

    try:
        while True:
            now = datetime.now(timezone.utc)
            published = 0
            for mid in meter_ids:
                reading = generate_reading(mid, now)
                topic = f"energy/meters/{mid}"
                payload = json.dumps(reading)
                client.publish(topic, payload, qos=2)
                published += 1

            logging.info(f"Published {published} readings.")
            time.sleep(config.PUBLISH_INTERVAL_SEC)

    except KeyboardInterrupt:
        logging.info("Publisher stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()
        logging.info("Disconnected from broker.")


if __name__ == "__main__":
    start_publisher()
