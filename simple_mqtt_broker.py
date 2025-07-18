#!/usr/bin/env python3
"""
Simple MQTT Broker for Testing
A minimal MQTT broker implementation for quick testing
Note: For production use, please use Mosquitto
"""

import asyncio
import socket
import struct
import json
from datetime import datetime


class SimpleMQTTBroker:
    def __init__(self, host='0.0.0.0', port=1883):
        self.host = host
        self.port = port
        self.clients = {}
        self.subscriptions = {}
        self.message_count = 0

    async def handle_client(self, reader, writer):
        """Handle a client connection"""
        client_addr = writer.get_extra_info('peername')
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        print(f"New connection from {client_id}")

        try:
            while True:
                # Read packet header
                header = await reader.read(2)
                if not header:
                    break

                # Parse packet type and remaining length
                packet_type = header[0] >> 4
                remaining_length = header[1]

                # Read remaining data
                data = await reader.read(remaining_length)

                # Handle different packet types
                if packet_type == 1:  # CONNECT
                    # Send CONNACK
                    connack = bytes([0x20, 0x02, 0x00, 0x00])
                    writer.write(connack)
                    await writer.drain()
                    print(f"Client {client_id} connected")
                    self.clients[client_id] = writer

                elif packet_type == 3:  # PUBLISH
                    # Parse topic length
                    topic_len = struct.unpack('>H', data[0:2])[0]
                    topic = data[2:2 + topic_len].decode('utf-8')

                    # Get message
                    msg_start = 2 + topic_len
                    message = data[msg_start:]

                    self.message_count += 1

                    # Print received data
                    try:
                        payload = json.loads(message)
                        if 'pm2_5_atm' in payload:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                                  f"PM2.5: {payload['pm2_5_atm']} μg/m³ "
                                  f"(msg #{self.message_count})")
                    except:
                        print(f"Received on {topic}: {message[:50]}...")

                    # Forward to subscribers
                    await self.forward_message(topic, message)

                elif packet_type == 8:  # SUBSCRIBE
                    # Simple subscribe handling
                    # Send SUBACK
                    packet_id = struct.unpack('>H', data[0:2])[0]
                    suback = bytes([0x90, 0x03, (packet_id >> 8) & 0xFF,
                                    packet_id & 0xFF, 0x00])
                    writer.write(suback)
                    await writer.drain()

                    # Store subscription
                    topic_start = 2
                    topic_len = struct.unpack('>H', data[topic_start:topic_start + 2])[0]
                    topic = data[topic_start + 2:topic_start + 2 + topic_len].decode('utf-8')

                    if topic not in self.subscriptions:
                        self.subscriptions[topic] = []
                    self.subscriptions[topic].append(client_id)
                    print(f"Client {client_id} subscribed to {topic}")

                elif packet_type == 12:  # PINGREQ
                    # Send PINGRESP
                    pingresp = bytes([0xD0, 0x00])
                    writer.write(pingresp)
                    await writer.drain()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            print(f"Client {client_id} disconnected")
            if client_id in self.clients:
                del self.clients[client_id]
            # Remove from subscriptions
            for topic in self.subscriptions:
                if client_id in self.subscriptions[topic]:
                    self.subscriptions[topic].remove(client_id)
            writer.close()
            await writer.wait_closed()

    async def forward_message(self, topic, message):
        """Forward message to subscribers"""
        if topic in self.subscriptions:
            for client_id in self.subscriptions[topic]:
                if client_id in self.clients:
                    writer = self.clients[client_id]

                    # Create PUBLISH packet
                    topic_bytes = topic.encode('utf-8')
                    topic_len = len(topic_bytes)

                    # Fixed header
                    fixed_header = bytes([0x30])  # PUBLISH, QoS 0

                    # Variable header
                    variable_header = struct.pack('>H', topic_len) + topic_bytes

                    # Payload
                    payload = message

                    # Remaining length
                    remaining_length = len(variable_header) + len(payload)

                    # Complete packet
                    packet = fixed_header + bytes([remaining_length]) + variable_header + payload

                    try:
                        writer.write(packet)
                        await writer.drain()
                    except:
                        print(f"Failed to forward to {client_id}")

    async def start(self):
        """Start the broker"""
        server = await asyncio.start_server(
            self.handle_client, self.host, self.port)

        addr = server.sockets[0].getsockname()
        print(f"Simple MQTT Broker running on {addr[0]}:{addr[1]}")
        print("This is a test broker - for production use Mosquitto")
        print("-" * 50)

        async with server:
            await server.serve_forever()


def main():
    print("Simple MQTT Broker for Air Quality Monitor Testing")
    print("=" * 50)

    # Get local IP
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    print(f"\nBroker will be available at:")
    print(f"  - localhost:1883")
    print(f"  - 127.0.0.1:1883")
    print(f"  - {local_ip}:1883")

    print(f"\nUpdate your ESP32 code to use:")
    print(f'  const char* MQTT_SERVER = "{local_ip}";')

    print("\nPress Ctrl+C to stop the broker\n")

    # Run broker
    broker = SimpleMQTTBroker()

    try:
        asyncio.run(broker.start())
    except KeyboardInterrupt:
        print("\nBroker stopped")


if __name__ == "__main__":
    main()