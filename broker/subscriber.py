import json
import logging
import threading
import time
from collections import deque
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from config.config import config
from database.db_writer import DatabaseWriter

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

db = DatabaseWriter()

# Batch configuration
BATCH_SIZE = 500
BATCH_TIMEOUT_SEC = 2.0

message_buffer = []
buffer_lock = threading.Lock()
last_flush = time.monotonic()
msg_counter = 0


def flush_buffer():
    """Insert all buffered messages and clear the buffer."""
    global message_buffer, last_flush
    if not message_buffer:
        return
    with buffer_lock:
        to_insert = message_buffer.copy()
        message_buffer.clear()
        last_flush = time.monotonic()
    try:
        db.insert_batch(to_insert)
        logging.info(f"Batch inserted {len(to_insert)} rows. Total rows so far: {msg_counter}")
    except Exception as e:
        logging.error(f"Batch insert failed: {e}")


def on_connect(client, userdata, flags, reasonCode, properties=None):
    if reasonCode == 0:
        logging.info(f"Connected to {config.MQTT_HOST}")
        client.subscribe(config.MQTT_TOPIC)
        logging.info(f"Subscribed to {config.MQTT_TOPIC}")
    else:
        logging.error(f"Connection failed with code {reasonCode}")


def on_message(client, userdata, msg, properties=None):
    global msg_counter, last_flush
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        with buffer_lock:
            message_buffer.append(data)
            msg_counter += 1

        # Flush if batch size reached
        if len(message_buffer) >= BATCH_SIZE:
            flush_buffer()
        # Also flush if timeout reached (called from timer thread)
    except json.JSONDecodeError:
        logging.error("Invalid JSON payload received")
    except Exception as e:
        logging.error(f"Error processing message: {e}")


def periodic_flush():
    """Background thread that flushes the buffer if timeout elapsed."""
    while True:
        time.sleep(1)
        now = time.monotonic()
        if message_buffer and (now - last_flush) >= BATCH_TIMEOUT_SEC:
            flush_buffer()


def start_subscriber():
    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=config.MQTT_Client_ID)
    client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    # Start periodic flush thread
    flush_thread = threading.Thread(target=periodic_flush, daemon=True)
    flush_thread.start()

    try:
        client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
        logging.info("Subscriber running with batching. Press Ctrl+C to stop.")
        client.loop_forever()
    except KeyboardInterrupt:
        logging.info("Subscriber stopped by user.")
    finally:
        flush_buffer()  # Final flush
        client.disconnect()
        db.close()
        logging.info("Disconnected and database closed.")


if __name__ == "__main__":
    start_subscriber()