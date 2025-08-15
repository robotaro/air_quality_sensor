#!/bin/bash

# Air Quality Monitor - Setup Script
# Sets up the project directory and permissions

set -e

echo "🔧 Setting up Air Quality Monitor..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Make all scripts executable
echo "🔐 Setting script permissions..."
chmod +x build.sh run.sh stop.sh clean.sh start_all.sh setup.sh

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/csv
mkdir -p mosquitto-data
mkdir -p mosquitto-logs

# Set proper ownership for data directory
echo "👤 Setting data directory ownership..."
sudo chown -R $USER:$USER data/

echo "✅ Setup completed!"
echo ""
echo "📋 Available commands:"
echo "  ./build.sh         # Build Docker images"
echo "  ./run.sh           # Start/restart services"
echo "  ./stop.sh          # Stop services"
echo "  ./clean.sh         # Remove containers and optionally data"
echo ""
echo "🚀 Quick start:"
echo "  ./build.sh && ./run.sh"
echo ""
echo "⚠️  Remember to update MQTT_BROKER in your Python files:"
echo "     Change '192.168.1.114' to 'mqtt-broker'"