import os

MQTT_BROKER = os.getenv('MQTT_BROKER_IP', '192.168.1.114')
MQTT_PORT = int(os.getenv('MQTT_BROKER_PORT', '1883'))
BUFFER_DURATION = int(os.getenv('BUFFER_DURATION', '300'))  # 5 minutes