#!/usr/bin/env python3
"""
MQTT Diagnostics Script
Tests MQTT connectivity and helps troubleshoot issues
"""

import socket
import paho.mqtt.client as mqtt
import time
import sys


def test_port(host, port):
    """Test if a port is open"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0


def test_mqtt_broker(broker_ip, port=1883):
    """Test MQTT broker connectivity"""
    print(f"\n1. Testing connection to {broker_ip}:{port}")

    # Test if port is open
    if test_port(broker_ip, port):
        print(f"   ✓ Port {port} is open on {broker_ip}")
    else:
        print(f"   ✗ Port {port} is NOT open on {broker_ip}")
        print(f"   → MQTT broker is not running or not accessible")
        return False

    # Try MQTT connection
    print(f"\n2. Testing MQTT connection...")

    connected = False

    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        if rc == 0:
            print("   ✓ Successfully connected to MQTT broker")
            connected = True
        else:
            print(f"   ✗ MQTT connection failed with code: {rc}")

    client = mqtt.Client()
    client.on_connect = on_connect

    try:
        client.connect(broker_ip, port, 60)
        client.loop_start()

        # Wait for connection
        timeout = 5
        start = time.time()
        while not connected and time.time() - start < timeout:
            time.sleep(0.1)

        client.loop_stop()
        client.disconnect()

        return connected

    except Exception as e:
        print(f"   ✗ MQTT connection error: {e}")
        return False


def main():
    print("MQTT Diagnostics Tool")
    print("====================")

    # Test different common MQTT broker locations
    test_locations = [
        ("localhost", 1883, "Local machine"),
        ("127.0.0.1", 1883, "Local machine (IP)"),
        ("192.168.1.100", 1883, "Configured server"),
    ]

    # Add current machine's IP
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        if local_ip not in ["127.0.0.1", "localhost"]:
            test_locations.append((local_ip, 1883, "This machine's IP"))
    except:
        pass

    print("\nTesting MQTT broker at common locations...")

    working_brokers = []

    for host, port, description in test_locations:
        print(f"\n--- Testing {description}: {host}:{port} ---")
        if test_mqtt_broker(host, port):
            working_brokers.append((host, port))

    print("\n" + "=" * 50)
    print("RESULTS:")

    if working_brokers:
        print(f"\n✓ Found MQTT broker(s) at:")
        for host, port in working_brokers:
            print(f"  - {host}:{port}")
        print(f"\nUpdate your scripts to use: MQTT_BROKER = '{working_brokers[0][0]}'")
    else:
        print("\n✗ No MQTT broker found!")
        print("\nTo fix this, you need to:")
        print("\n1. Install Mosquitto MQTT Broker:")
        print("   - Download from: https://mosquitto.org/download/")
        print("   - For Windows: Download and run the installer")
        print("   - After installation, Mosquitto should start automatically as a service")

        print("\n2. Or start Mosquitto manually:")
        print("   - Open Command Prompt as Administrator")
        print("   - Navigate to Mosquitto installation folder")
        print("     (usually C:\\Program Files\\mosquitto)")
        print("   - Run: mosquitto.exe -v")

        print("\n3. Check Windows Firewall:")
        print("   - Make sure port 1883 is not blocked")
        print("   - You may need to add an inbound rule for Mosquitto")


if __name__ == "__main__":
    main()