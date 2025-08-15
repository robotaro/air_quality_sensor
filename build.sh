#!/bin/bash

# Air Quality Monitor - Build Script
# Builds the Docker image for the air quality monitoring system

set -e

echo "🔨 Building Air Quality Monitor Docker image..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Build the image
docker build -t airquality-monitor:latest .

# Also build the MQTT broker image (just pull it)
echo "📡 Pulling MQTT broker image..."
docker pull eclipse-mosquitto:2

echo "✅ Build completed successfully!"
echo ""
echo "Images built:"
echo "  - airquality-monitor:latest"
echo "  - eclipse-mosquitto:2"
echo ""
echo "Run './run.sh' to start the services."