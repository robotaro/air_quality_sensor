#!/bin/bash

# Air Quality Monitor - Clean Script
# Removes containers, network, and optionally data

set -e

# Configuration
NETWORK_NAME="airquality-net"
MQTT_CONTAINER_NAME="airquality-mqtt"
MONITOR_CONTAINER_NAME="airquality-monitor"

echo "🧹 Cleaning up Air Quality Monitor..."

# Stop containers first
./stop.sh 2>/dev/null || true

echo ""
echo "🗑️  Removing containers..."

# Remove containers
if docker ps -a | grep -q "$MONITOR_CONTAINER_NAME"; then
    docker rm "$MONITOR_CONTAINER_NAME"
    echo "✅ Removed monitor container"
fi

if docker ps -a | grep -q "$MQTT_CONTAINER_NAME"; then
    docker rm "$MQTT_CONTAINER_NAME"
    echo "✅ Removed MQTT container"
fi

# Remove network
if docker network ls | grep -q "$NETWORK_NAME"; then
    docker network rm "$NETWORK_NAME"
    echo "✅ Removed network: $NETWORK_NAME"
fi

# Ask about removing data
echo ""
read -p "🗂️  Remove data directories? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing data directories..."
    rm -rf data/ mosquitto-data/ mosquitto-logs/
    echo "✅ Data directories removed"
else
    echo "ℹ️  Data directories preserved"
fi

# Ask about removing image
echo ""
read -p "🐳 Remove Docker image? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing Docker image..."
    docker rmi airquality-monitor:latest 2>/dev/null || echo "Image not found"
    echo "✅ Docker image removed"
else
    echo "ℹ️  Docker image preserved"
fi

echo ""
echo "🎉 Cleanup completed!"
echo ""
echo "💡 To start fresh:"
echo "  ./build.sh         # Rebuild image"
echo "  ./run.sh           # Start services"