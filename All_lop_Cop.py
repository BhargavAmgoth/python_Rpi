



import sys
import threading
import socket
import struct
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QVBoxLayout, QLabel
import websocket
from datetime import datetime

# Constants for multicast group
MCAST_GRP = '239.1.2.3'
MCAST_PORT = 2323
shaft_connectivity_flag = False
cabin_connectivity_flag = False

# Data lists
lops_shaft = [
    bytearray([0x55, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x00, 0xff]),  #head, lop_flor, calBok_stat, cabin_flor, Door_sensor, ML, D_solenoid, update, foot 
    bytearray([0x55, 0x01, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01, 0x00, 0xff]),
    #bytearray([0x55, 0x02, 0x00, 0x00, 0x01, 0x02, 0x00, 0x00, 0x00, 0xff]),
    #bytearray([0x55, 0x03, 0x00, 0x00, 0x01, 0x02, 0x00, 0x00, 0x00, 0xff])
]
cabin_data_list = bytearray([0xd5, 0x00, 0x00, 0x00, 0x00, 0x64, 0x00, 0x00, 0x00, 0xff])

# Data for Android Cabin
LL_android_cabin_data = [
    bytes([0x65, 0x00, 0x09, 0x02, 0x01, 0xFF, 0xFF, 0xFF]),
    bytes([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])
]
RGB_android_cabin_dataC = bytes([0x65, 0x05, 0x1E, 0x32, 0x09, 0x00, 0x01, 0xff])

# Function to format WebSocket URL
def get_ip(ip, port):
    return f"ws://{ip}:{port}/ws"

# Call booking logic
def call_booking(call_type, floor_number):
    print(f"{call_type} Call Booked for Ground {floor_number}")

    if call_type == "LOP":
        for floor in range(len(lops_shaft)):
            if floor == floor_number:
                lops_shaft[floor][2] = 0x01  # Set the specific floor active
                print(f"Updated lops_shaft floor one [{floor}]: ", end="")
                print(" ".join(f"0x{byte:02x}" for byte in lops_shaft[floor]))
                send_lop_to_shaft(floor)
            else:
                lops_shaft[floor][2] = 0x00  # Reset other floors
                print(f"Updated lops_shaft floor zero [{floor}]: ", end="")
                print(" ".join(f"0x{byte:02x}" for byte in lops_shaft[floor]))

    elif call_type == "COP":
        if 0 <= floor_number < len(lops_shaft):
            cabin_data_list[4] = 2 ** floor_number
            print("Updated cabin data: ", " ".join(f"0x{byte:02x}" for byte in cabin_data_list))
            send_cop_to_cabin(floor_number)

# Sending logic placeholders
def send_lop_to_shaft(floor):
    print(f"Sending LOP data to shaft for floor {floor}")
    # Placeholder: Add WebSocket communication logic here

def send_cop_to_cabin(floor):
    print(f"Sending COP data to cabin for floor {floor}")
    # Placeholder: Add WebSocket communication logic here

# WebSocket handling for real-time communication
def run_websocket_client(url, client_name):
    def on_message(ws, message):
        current_time = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        print(f"Time: {current_time} - Received message from {client_name}: " +
              " ".join(f"0x{byte:02x}" for byte in message))
        if client_name == 'cabin':     
            send_cabin_data(ws)
        elif client_name == 'shaft':
            send_shaft_data(ws)
        
    def on_error(ws, error):
        print(f"{client_name} encountered error: {error}")

    def on_close(ws, close_status_code, close_msg):
        global shaft_connectivity_flag, cabin_connectivity_flag
        if client_name == "shaft":
            shaft_connectivity_flag = False
        elif client_name == "cabin":
            cabin_connectivity_flag = False
        print(f"{client_name} connection closed with code: {close_status_code}, message: {close_msg}")

    def on_open(ws):
        global shaft_connectivity_flag, cabin_connectivity_flag
        if client_name == "shaft":
            shaft_connectivity_flag = True
        elif client_name == "cabin":
            cabin_connectivity_flag = True
        print(f"{client_name} connection opened")

    # Creating a WebSocket app with the callbacks
    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.on_open = on_open

    # Running the WebSocket client
    ws.run_forever()

# GUI Implementation using PyQt6
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Call Booking System")

        central_widget = QWidget()
        layout = QVBoxLayout()

        def add_call_buttons(call_type, floors):
            layout.addWidget(QLabel(f"{call_type} Call Booking"))
            for i in floors:
                button = QPushButton(f"{call_type} Ground {i}")
                button.setStyleSheet('QPushButton {background-color: #A3C1DA; color: red;}')
                button.clicked.connect(lambda _, c=call_type, f=i: call_booking(c, f))
                layout.addWidget(button)

        add_call_buttons("LOP", range(4))
        add_call_buttons("COP", range(4))

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

# Start UDP listener and WebSocket in separate threads
def udp_to_websocket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MCAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size of 1024 bytes
        if data[0] == 0xde and data[1] == 0x01 and not shaft_connectivity_flag:
            print("Connecting to shaft at ", addr[0])
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5151), "shaft")).start()
        elif data[0] == 0xde and data[1] == 0x02 and not cabin_connectivity_flag:
            print("Connecting to cabin at ", addr[0])
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5050), "cabin")).start()

def send_cabin_data(ws):
    ws.send(LL_android_cabin_data[1])
    ws.send(RGB_android_cabin_dataC)
    print("Data Sent to cabin")

def send_shaft_data(ws):
    for lop in lops_shaft:
        ws.send(lop)
        print("Data lop to Shaft")
    ws.send(cabin_data_list)
    print("Data cabin to Shaft")

# Thread for UDP listening
udp_thread = threading.Thread(target=udp_to_websocket)
udp_thread.daemon = True  # Ensures the thread exits when the main program exits
udp_thread.start()

# Run the application
app = QApplication(sys.argv)
window = MainWindow()
window.show()

# Start the PyQt event loop
sys.exit(app.exec())
