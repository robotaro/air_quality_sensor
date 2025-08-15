#!/usr/bin/env python3
"""
Air Quality Data Collector Service (1-Minute Chunks)
Subscribes to MQTT and saves sensor data in 1-minute CSV chunks
"""

import json
import csv
import os
import time
from datetime import datetime, timezone
from collections import deque
from threading import Thread, Lock
import paho.mqtt.client as mqtt
import signal
import sys
from dateutil import parser as date_parser

# Configuration
MQTT_BROKER = "192.168.1.114"
MQTT_PORT = 1883
MQTT_USER = ""  # Leave empty if no auth
MQTT_PASSWORD = ""
MQTT_TOPIC_DATA = "airquality/sensor/data"
MQTT_TOPIC_STATUS = "airquality/sensor/status"

# Data storage configuration
DATA_DIR = "data/csv"
BUFFER_DURATION = 300  # 1 minute in seconds (changed from 300 to 60)
CSV_HEADERS = [
    "timestamp", "device_id", "pm1_0_cf1", "pm2_5_cf1", "pm10_cf1",
    "pm1_0_atm", "pm2_5_atm", "pm10_atm", "particles_03", "particles_05",
    "particles_10", "particles_25", "particles_50", "particles_100",
    "version", "error_code"
]


class DataCollector:
    def __init__(self):
        self.data_buffer = deque()
        self.buffer_lock = Lock()
        self.running = True
        self.last_dump_time = time.time()
        self.file_counter = 1  # Counter for sequential numbering

        # Ensure data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)

        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect

        if MQTT_USER:
            self.mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            client.subscribe(MQTT_TOPIC_DATA)
            client.subscribe(MQTT_TOPIC_STATUS)
        else:
            print(f"Failed to connect, return code {rc}")

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected from MQTT broker (rc={rc})")
        if rc != 0:
            print("Unexpected disconnection. Will auto-reconnect")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())

            if msg.topic == MQTT_TOPIC_DATA:
                # Standardize timestamp format
                if 'timestamp' in payload:
                    try:
                        dt = date_parser.isoparse(payload['timestamp'])
                        payload['timestamp'] = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                    except ValueError as e:
                        print(f"Error parsing timestamp: {e}")
                        payload['timestamp'] = datetime.now(timezone.utc).isoformat(timespec='milliseconds')

                with self.buffer_lock:
                    self.data_buffer.append(payload)

                if len(self.data_buffer) % 100 == 0:
                    print(f"Buffer: {len(self.data_buffer)} | "
                          f"PM2.5: {payload.get('pm2_5_atm', 'N/A')} μg/m³ | "
                          f"Time: {payload.get('timestamp', 'N/A')}")

            elif msg.topic == MQTT_TOPIC_STATUS:
                device_id = payload.get('device_id', 'unknown')
                status = payload.get('status', 'unknown')
                print(f"Device {device_id} status: {status}")

        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def dump_buffer_to_csv(self):
        """Dump the current buffer to a CSV file every 1 minute"""
        with self.buffer_lock:
            if not self.data_buffer:
                return
            data_to_save = list(self.data_buffer)
            self.data_buffer.clear()

        if not data_to_save:
            return

        # Generate filename with sequential numbering and timestamp
        try:
            first_timestamp = date_parser.isoparse(data_to_save[0]['timestamp'])
            base_timestamp = first_timestamp.strftime('%Y%m%d_%H%M')
            filename = os.path.join(DATA_DIR, f"airquality_{base_timestamp}_{self.file_counter:03d}.csv")
            self.file_counter += 1
        except (KeyError, ValueError):
            current_time = datetime.now(timezone.utc)
            base_timestamp = current_time.strftime('%Y%m%d_%H%M')
            filename = os.path.join(DATA_DIR, f"airquality_{base_timestamp}_{self.file_counter:03d}.csv")
            self.file_counter += 1

        try:
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
                writer.writeheader()

                for row in data_to_save:
                    csv_row = {header: row.get(header, '') for header in CSV_HEADERS}

                    if 'timestamp' in csv_row and csv_row['timestamp']:
                        try:
                            dt = date_parser.isoparse(csv_row['timestamp'])
                            csv_row['timestamp'] = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                        except ValueError:
                            csv_row['timestamp'] = datetime.now(timezone.utc).isoformat(timespec='milliseconds')

                    writer.writerow(csv_row)

            print(f"Saved {len(data_to_save)} records to {filename}")

        except Exception as e:
            print(f"Error saving CSV: {e}")
            with self.buffer_lock:
                self.data_buffer.extendleft(reversed(data_to_save))

    def buffer_manager_thread(self):
        """Thread that dumps buffer every 1 minute"""
        while self.running:
            current_time = time.time()
            if current_time - self.last_dump_time >= BUFFER_DURATION:
                self.dump_buffer_to_csv()
                self.last_dump_time = current_time
                self.file_counter = 1  # Reset counter at each new minute
            time.sleep(1)

    def start(self):
        """Start the collector service"""
        print("Starting Air Quality Data Collector (1-minute chunks)...")
        print(f"Data will be saved to: {os.path.abspath(DATA_DIR)}")
        print(f"CSV files will be created every {BUFFER_DURATION} seconds")

        buffer_thread = Thread(target=self.buffer_manager_thread, daemon=True)
        buffer_thread.start()

        try:
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as e:
            print(f"MQTT connection error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the collector and save remaining data"""
        self.running = False
        if self.data_buffer:
            print("Saving remaining data...")
            self.dump_buffer_to_csv()
        self.mqtt_client.disconnect()
        print("Collector stopped")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nReceived interrupt signal")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    collector = DataCollector()
    collector.start()