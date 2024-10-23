import socket
import struct
import asyncio
import websockets
from datetime import datetime
shaft_connectivity_flag = False
cabin_connectivity_flag = False
# Multicast group and ports
MCAST_GRP = '239.1.2.3'
MCAST_PORT = 2323 
SHAFT_WEBSOCKET_PORT = 5151  # WebSocket Port Shaft
CABIN_WEBSOCKET_PORT = 5050 #WebSocket Port Cabin

# Set up the UDP socket for multicast
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', MCAST_PORT))

mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

# Function to connect to Shaft WebSocket and receive data
async def connect_shaft_websocket(ip, port):
    uri = f"ws://{ip}:{port}/ws"
    try:
        print(f"Attempting to connect Shaft WebSocket at {uri}")
        async with websockets.connect(uri) as websocket:
            print(f"Connected Shaft WebSocket at {uri}")
            shaft_connectivity_flag = True
            # Continuously receive data from the WebSocket
            async for message in websocket:
                #print(f"Received Shaft WebSocket ({uri}): {len(message)}")
                if len(message) == 16:
                    print(" ".join(f" 0x{msg:02x}" for msg in message))
                    #for msg in message:
                     #   print(f"(0x{msg:02x})")
                    #print(message)
    except Exception as e:
        print(f"Error connecting Shaft WebSocket {uri}: {e}")


# Function to connect to Cabin WebSocket and receive data
async def connect_cabin_websocket(ip, port):
    uri = f"ws://{ip}:{port}/ws"
    try:
        print(f"Attempting to connect Cabin WebSocket at {uri}")
        async with websockets.connect(uri) as websocket:
            print(f"Connected to Cabin WebSocket at {uri}")
            cabin_connectivity_flag = True
            # Continuously receive data from the WebSocket
            async for message in websocket:
                #print(f"Received Cabin WebSocket ({uri}): {len(message)}")
                if len(message) == 10:
                    print(" ".join(f" 0x{msg:02x}" for msg in message))
    except Exception as e:
        print(f"Error connecting to Cabin WebSocket {uri}: {e}")


# UDP receive and check loop
async def udp_to_websocket():
    while True:
        # Receiving UDP data
        data, addr = sock.recvfrom(1024)  # Buffer size of 1024 bytes
        current_time = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        
        # Print received UDP data for debugging
        print(f"Time: {current_time} - Received message from {addr} - " +
              " ".join(f",0x{byte:02x}" for byte in data))

        # Check if the packet starts with 0xD5 and second byte is 0x01
        if data[0] == 0xDe and data[1] == 0x01 and shaft_connectivity_flag == False:
            print(f"Header matched for IP {addr[0]}, attempting WebSocket connection on port {SHAFT_WEBSOCKET_PORT}")
            # Connect to WebSocket on the IP from the UDP sender and port 5151
            await connect_shaft_websocket(addr[0], SHAFT_WEBSOCKET_PORT)
        elif data[0] == 0xde and data[1] == 2 and cabin_connectivity_flag == False:
            print(f"Header matched for ip {addr[0]}, attempting Websocket connection on port {CABIN_WEBSOCKET_PORT}")
             # Connect to WebSocket on the IP from the UDP sender and port 5151
            await connect_cabin_websocket(addr[0], CABIN_WEBSOCKET_PORT)

# Run the async loop
async def main():
    await udp_to_websocket()

# Start the asyncio event loop
asyncio.run(main())
