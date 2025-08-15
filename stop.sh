#!/bin/bash

# Air Quality Monitor - Stop Script
# Stops the air quality monitoring containers

set -e

# Configuration
MQTT_CONTAINER_NAME="airquality-mqtt"
MONITOR_CONTAINER_NAME="airquality-monitor"

echo "🛑 Stopping Air Quality Monitor..."

# Stop containers
if docker ps | grep -q "$MONITOR_CONTAINER_NAME"; then
    echo "🌡️  Stopping monitor container..."
    docker stop "$MONITOR_CONTAINER_NAME"
    echo "✅ Monitor container stopped"
else
    echo "ℹ️  Monitor container is not running"
fi

if docker ps | grep -q "$MQTT_CONTAINER_NAME"; then
    echo "📡 Stopping MQTT broker..."
    docker stop "$MQTT_CONTAINER_NAME"
    echo "✅ MQTT broker stopped"
else
    echo "ℹ️  MQTT broker is not running"
fi

# Show current status
echo ""
echo "📋 Container Status:"
if docker ps -a --filter "name=airquality" --format "table {{.Names}}\t{{.Status}}" | grep -q airquality; then
    docker ps -a --filter "name=airquality" --format "table {{.Names}}\t{{.Status}}"
else
    echo "No airquality containers found"
fi

echo ""
echo "✅ Air Quality Monitor stopped"
echo ""
echo "💡 Options:"
echo "  ./run.sh          # Start again"
echo "  ./clean.sh         # Remove stopped containers and data"
echo "  docker logs $MONITOR_CONTAINER_NAME  # View logs from last run"
echo ""
echo "Note: Containers are stopped but not removed. Data is preserved."