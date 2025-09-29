#!/usr/bin/env python3
"""
Monitors air quality sensor data via MQTT and activates a buzzer
when the PM10 concentration exceeds a specified threshold.
"""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

# --- alarm state (add these near other globals) ---
alarm_active = False           # True while the 5s ON window is in progress
pending_off_timer = None       # threading.Timer used to send the OFF
last_triggered_time = None     # datetime when cooldown starts (after OFF)

# --- Configuration ---
# The rest period (in seconds) after the buzzer is triggered, before it can be triggered again.
REST_PERIOD_SECONDS = 7 * 60  # 7 minutes

# Default MQTT connection settings (can be overridden by command-line arguments)
DEFAULT_MQTT_BROKER = "localhost"
DEFAULT_MQTT_PORT = 1883
DEFAULT_MQTT_TOPIC_DATA = "airquality/sensor/data"
DEFAULT_MQTT_TOPIC_COMMAND = "airquality/sensor/command"

# --- Global Variables ---
# These are used to manage the state of the script, including the MQTT client
# and the last time the alarm was triggered.
mqtt_client = None
last_triggered_time = None
args = None  # Global variable to store command line arguments

def parse_arguments():
    """
    Parses command-line arguments for duty cycle, PM10 threshold, and MQTT settings.
    """
    parser = argparse.ArgumentParser(
        description="MQTT Buzzer Alerter for PM10 concentration.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--duty_cycle',
        type=float,
        default=0.2,
        help="The duty cycle for the buzzer when activated (0.0 to 1.0)."
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=75.0,
        help="The PM10 concentration threshold (in μg/m³) to trigger the buzzer."
    )
    parser.add_argument('--broker', default=DEFAULT_MQTT_BROKER, help="MQTT broker address.")
    parser.add_argument('--port', type=int, default=DEFAULT_MQTT_PORT, help="MQTT broker port.")
    parser.add_argument('--data-topic', default=DEFAULT_MQTT_TOPIC_DATA, help="MQTT topic to subscribe to for sensor data.")
    parser.add_argument('--command-topic', default=DEFAULT_MQTT_TOPIC_COMMAND, help="MQTT topic to publish buzzer commands to.")

    return parser.parse_args()


def send_buzzer_command(duty_cycle, period, command_topic):
    """
    Sends a command to the buzzer via MQTT (QoS 1).
    A duty cycle of 0 turns the buzzer off.
    """
    if not mqtt_client or not mqtt_client.is_connected():
        print("Error: MQTT client not connected. Cannot send command.")
        return

    try:
        message = {
            "type": "buzzer",
            "duty_cycle": float(duty_cycle),
            "period": float(period),
            "id": f"alerter_{int(time.time() * 1000)}"
        }
        result = mqtt_client.publish(command_topic, json.dumps(message), qos=1)
        if result.rc != 0:
            print(f"Failed to publish to '{command_topic}'. rc={result.rc}")
        else:
            print(f"Published -> duty_cycle={duty_cycle}, period={period}")
    except Exception as e:
        print(f"Error while sending buzzer command: {e}")

def trigger_buzzer_for(duration_sec, duty_cycle, period, command_topic):
    """
    Turn buzzer ON at 'duty_cycle' for 'duration_sec' seconds, then OFF,
    then start cooldown. Non-blocking.
    """
    import threading
    global alarm_active, pending_off_timer, last_triggered_time

    if alarm_active:
        print("Alarm already active; ignoring new trigger.")
        return

    # Turn ON now
    alarm_active = True
    print(f"Activating buzzer at duty_cycle={duty_cycle} for {duration_sec}s …")
    send_buzzer_command(duty_cycle, period, command_topic)

    # Schedule OFF + start cooldown after duration_sec
    def _turn_off_and_start_cooldown():
        global alarm_active, pending_off_timer, last_triggered_time
        print("Deactivating buzzer; starting cooldown …")
        send_buzzer_command(0.0, period, command_topic)
        alarm_active = False
        pending_off_timer = None

        # Cooldown starts *after* OFF is sent
        last_triggered_time = datetime.now()
        cooldown_end = last_triggered_time + timedelta(seconds=REST_PERIOD_SECONDS)
        print(f"Cooldown active until {cooldown_end.strftime('%H:%M:%S')}.")

    # Keep a handle in case you ever want to cancel it
    pending_off_timer = threading.Timer(duration_sec, _turn_off_and_start_cooldown)
    pending_off_timer.start()


def on_connect(client, userdata, flags, rc):
    """
    Callback function for when the client connects to the MQTT broker.
    """
    if rc == 0:
        print(f"Successfully connected to MQTT broker at {userdata['broker']}:{userdata['port']}")
        client.subscribe(userdata['data_topic'])
        print(f"Subscribed to data topic: {userdata['data_topic']}")
    else:
        print(f"Failed to connect to MQTT broker, return code {rc}\n")
        sys.exit(1)


def on_message(client, userdata, msg):
    """
    MQTT callback: reacts to incoming PM readings.
    Triggers buzzer for 5s at args.duty_cycle, then OFF, then cooldown.
    Ignores triggers during the 5s active window and during cooldown.
    """
    global last_triggered_time, alarm_active
    args = userdata['args']  # expects .threshold, .duty_cycle, .command_topic

    try:
        payload = json.loads(msg.payload.decode())
        pm10_value = payload.get('pm10_atm')
        if pm10_value is None:
            return  # not our message

        print(f"PM10={pm10_value:.2f} μg/m³ (threshold {args.threshold:.2f})")

        # If the buzzer is already sounding, do not retrigger
        if alarm_active:
            print(" -> Buzzer currently active; ignoring.")
            return

        # Check cooldown *after* last OFF
        now = datetime.now()
        in_cooldown = (
            last_triggered_time is not None
            and (now - last_triggered_time).total_seconds() < REST_PERIOD_SECONDS
        )
        if in_cooldown:
            remaining = REST_PERIOD_SECONDS - int((now - last_triggered_time).total_seconds())
            print(f" -> In cooldown ({remaining}s left); ignoring.")
            return

        # Threshold crossed => run 5s ON @ duty_cycle, then OFF, then cooldown
        if pm10_value >= args.threshold:
            trigger_buzzer_for(
                duration_sec=4.7,
                duty_cycle=float(args.duty_cycle),  # e.g., 0.2
                period=1.0,
                command_topic=args.command_topic,
            )

    except json.JSONDecodeError:
        print(f"Warning: could not decode JSON on topic '{msg.topic}'")
    except Exception as e:
        print(f"Error in on_message: {e}")


def signal_handler(sig, frame):
    """
    Handles exit signals (like Ctrl+C) to ensure the buzzer is turned off.
    """
    global args
    print("\nExit signal received. Shutting down...")
    if mqtt_client and mqtt_client.is_connected():
        print("Ensuring buzzer is turned off before exit.")
        send_buzzer_command(0.0, 1.0, args.command_topic)  # Fixed: added period parameter
        # Give a moment for the message to be sent
        time.sleep(0.5)
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
    print("Goodbye!")
    sys.exit(0)

if __name__ == "__main__":
    # Store the parsed arguments in the global variable
    args = parse_arguments()

    # Register the signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Store args in userdata to be accessible in callbacks
    userdata = {
        'args': args,
        'broker': args.broker,
        'port': args.port,
        'data_topic': args.data_topic
    }
    mqtt_client = mqtt.Client(userdata=userdata)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    print("--- PM10 Buzzer Alerter ---")
    print(f"Connecting to {args.broker}:{args.port}...")

    try:
        mqtt_client.connect(args.broker, args.port, 60)
        # Send an initial command to ensure the buzzer is off at startup
        # We need a small delay to allow the connection to establish before publishing
        mqtt_client.loop_start()
        time.sleep(1)
        print("Sending initial command to ensure buzzer is off.")
        send_buzzer_command(0.0, 1.0, args.command_topic)  # Fixed: added period parameter

        print("Monitoring for PM10 data. Press Ctrl+C to exit.")
        # Keep the script running indefinitely
        while True:
            time.sleep(1)

    except ConnectionRefusedError:
        print(f"Error: Connection refused. Is the MQTT broker running at {args.broker}:{args.port}?")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        # This part runs on normal exit, but signal_handler covers Ctrl+C
        if mqtt_client.is_connected():
            mqtt_client.disconnect()
        mqtt_client.loop_stop()