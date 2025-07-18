#!/usr/bin/env python3
"""
MQTT Connection Test
Tests connection between Python scripts and MQTT broker
"""

import paho.mqtt.client as mqtt
import time
import json

# Test with localhost
MQTT_BROKER = "192.168.1.114"
MQTT_PORT = 1883


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✓ Connected successfully to MQTT broker")
        client.subscribe("airquality/sensor/data")
        print("✓ Subscribed to airquality/sensor/data")
    else:
        print(f"✗ Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    print(f"\n✓ Received message on {msg.topic}")
    try:
        payload = json.loads(msg.payload.decode())
        if 'pm2_5_atm' in payload:
            print(f"  PM2.5: {payload['pm2_5_atm']} μg/m³")
    except:
        print(f"  Raw: {msg.payload.decode()[:100]}...")


def test_publish(client):
    """Send a test message"""
    test_data = {
        "timestamp": int(time.time() * 1000),
        "device_id": "test_device",
        "pm1_0_atm": 10,
        "pm2_5_atm": 15,
        "pm10_atm": 20,
    }

    client.publish("airquality/sensor/data", json.dumps(test_data))
    print("\n✓ Published test message")


def main():
    print("MQTT Connection Test")
    print("===================")
    print(f"Connecting to: {MQTT_BROKER}:{MQTT_PORT}")

    # Create client
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    # Try to connect
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()

        # Wait for connection
        time.sleep(2)

        # Send test message
        test_publish(client)

        print("\nListening for messages (press Ctrl+C to stop)...")

        while True:
            time.sleep(1)

    except ConnectionRefusedError:
        print(f"\n✗ Connection refused!")
        print("Make sure the MQTT broker is running:")
        print("- Simple broker: python simple_mqtt_broker.py")
        print("- Or Mosquitto: mosquitto -v")
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"\n✗ Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()