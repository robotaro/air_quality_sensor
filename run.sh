#!/bin/bash

# Air Quality Monitor - Run Script
# Starts or restarts the air quality monitoring containers

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
NETWORK_NAME="airquality-net"
MQTT_CONTAINER_NAME="airquality-mqtt"
MONITOR_CONTAINER_NAME="airquality-monitor"
DATA_DIR="$SCRIPT_DIR/data"
MOSQUITTO_DATA_DIR="$SCRIPT_DIR/mosquitto-data"
MOSQUITTO_LOGS_DIR="$SCRIPT_DIR/mosquitto-logs"

# Get current user ID and group ID
USER_ID=$(id -u)
GROUP_ID=$(id -g)

echo "🚀 Starting Air Quality Monitor..."

# Create data directories if they don't exist
echo "📁 Setting up data directories..."
mkdir -p "$DATA_DIR/csv"
mkdir -p "$MOSQUITTO_DATA_DIR"
mkdir -p "$MOSQUITTO_LOGS_DIR"

# Set proper ownership
sudo chown -R $USER:$USER "$DATA_DIR"
sudo chown -R 1883:1883 "$MOSQUITTO_DATA_DIR" "$MOSQUITTO_LOGS_DIR" 2>/dev/null || true

# Create Docker network if it doesn't exist
echo "🌐 Setting up Docker network..."
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    docker network create "$NETWORK_NAME"
    echo "✅ Created network: $NETWORK_NAME"
else
    echo "✅ Network already exists: $NETWORK_NAME"
fi

# Stop and remove existing containers if they exist
echo "🔄 Checking for existing containers..."

if docker ps -a | grep -q "$MQTT_CONTAINER_NAME"; then
    echo "🛑 Stopping existing MQTT container..."
    docker stop "$MQTT_CONTAINER_NAME" 2>/dev/null || true
    docker rm "$MQTT_CONTAINER_NAME" 2>/dev/null || true
fi

if docker ps -a | grep -q "$MONITOR_CONTAINER_NAME"; then
    echo "🛑 Stopping existing monitor container..."
    docker stop "$MONITOR_CONTAINER_NAME" 2>/dev/null || true
    docker rm "$MONITOR_CONTAINER_NAME" 2>/dev/null || true
fi

# Start MQTT broker
echo "📡 Starting MQTT broker..."
docker run -d \
    --name "$MQTT_CONTAINER_NAME" \
    --network "$NETWORK_NAME" \
    --restart unless-stopped \
    -p 1883:1883 \
    -p 9001:9001 \
    -v "$SCRIPT_DIR/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro" \
    -v "$MOSQUITTO_DATA_DIR:/mosquitto/data" \
    -v "$MOSQUITTO_LOGS_DIR:/mosquitto/log" \
    eclipse-mosquitto:2

echo "✅ MQTT broker started"

# Wait a moment for MQTT broker to be ready
sleep 2

# Start the main air quality monitor
echo "🌡️  Starting Air Quality Monitor..."
docker run -d \
    --name "$MONITOR_CONTAINER_NAME" \
    --network "$NETWORK_NAME" \
    --restart unless-stopped \
    -p 8050:8050 \
    -v "$DATA_DIR:/app/data:rw" \
    -u "$USER_ID:$GROUP_ID" \
    -e PYTHONUNBUFFERED=1 \
    airquality-monitor:latest

echo "✅ Air Quality Monitor started"

# Show status
echo ""
echo "🎉 Air Quality Monitor is now running!"
echo ""
echo "📊 Dashboard: http://localhost:8050"
echo "📡 MQTT Broker: localhost:1883"
echo "📁 Data Directory: $DATA_DIR/csv"
echo ""
echo "Container Status:"
docker ps --filter "name=airquality" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "📋 To view logs:"
echo "  docker logs -f $MONITOR_CONTAINER_NAME    # Main application"
echo "  docker logs -f $MQTT_CONTAINER_NAME       # MQTT broker"
echo ""
echo "🛑 To stop:"
echo "  ./stop.sh"
echo ""
echo "Note: Containers will auto-restart on system reboot unless explicitly stopped."