import sys
import threading
import socket
import struct
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout, QBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

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
LL_android_cabin_data_to = [
    bytearray([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])   # 4th byte 1 RGB turned On 0 RGB turned off
   # bytes([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])    #
]
LL_android_cabin_data =  bytearray([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])   # 4th byte 1 RGB turned On 0 RGB turned off
RGB_android_cabin_dataC = bytearray([0x65, 0x05, 0x00, 0x00, 0x09, 0x00, 0x01, 0xff]) #Header, RGB-5, Timer, Bright, Color,  stay_0, stay_1, footer
FanDatatoCab = bytearray([0x65, 0x04, 0x01, 0x32, 0x01, 0xFF, 0xFF, 0xFF]) #Header, Dev, FAN-1, Time, 0-off 15 to 100% bright, Dummey, Dummey, Footer  


# Function to format WebSocket URL
def get_ip(ip, port):
    return f"ws://{ip}:{port}/ws"

# Call booking logic
def call_booking(call_type, floor_name):
    floor_mapping = {
        "Ground Floor": 0,
        "First Floor": 1,
        "Second Floor": 2,
        "Third Floor": 3}

    if floor_name not in floor_mapping:
        print(f"Invalid floor name: {floor_name}")
        return

    floor_number = floor_mapping[floor_name]
   
    print(f"{call_type} Call Booked for ............ {floor_number}")

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
              " ".join(f",0x{byte:02x}" for byte in message))
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
        

        def add_call_buttons(call_type, floors):
            layout.addWidget(QLabel(f"{call_type} Call Booking"))
            layout = QVBoxLayout()
            for i in floors:

                button = QPushButton(f"{call_type} Ground {i}")
                button.setStyleSheet('QPushButton {background-color: #A3C1DA; color: red;}')
                button.clicked.connect(lambda _, c=call_type, f=i: call_booking(c, f))
                layout.addWidget(button)

        add_call_buttons("LOP", range(4))
        add_call_buttons("COP", range(4))

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

class LiftControlUI(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Lift Control - LOP & COP Panels")
        self.setGeometry(100, 100, 800, 600)

        # Main layout for both panels
        main_layout = QHBoxLayout()
        
        # Create LOP and COP panels
        lop_panel = self.create_lop_panel()
        cop_panel = self.create_cop_panel()
        
        # Add the panels to the main layout
        main_layout.addWidget(lop_panel)
        main_layout.addWidget(cop_panel)
        self.setLayout(main_layout)

    def create_lop_panel(self):
        # Create a group box for the LOP Panel
        lop_box = QGroupBox("LOP PANEL")
        lop_layout = QVBoxLayout()
        grid_layout = QGridLayout()

        # Create buttons for LOP Panel
        lop_buttons = [
            "Ground Floor", "First Floor", "Second Floor",
            "Third Floor", "Solenoid",
            "Door Switch", "Mechanical Lock"
        ]
        ml_states = [ "ML Open", "ML Close", "ML Semi"]

        type = "LOP"
        for btn_text in lop_buttons:
            if btn_text == "Mechanical Lock" :
                button_number = 0
                for row in range(3):  # 3 rows
                    color_button = QPushButton(ml_states[row] + " " + str(button_number))
                    color_button.setStyleSheet(self.color_button_style())
                    #color_button.clicked.connect(lambda checked, num=button_number: self.on_button_click(num))
                    color_button.clicked.connect(lambda _, type="ML", num=button_number: self.rgb_ml_color_button(type, num))
                    grid_layout.addWidget(color_button, row, 1)
                    button_number += 1
                lop_layout.addLayout(grid_layout)
            else :
                button = QPushButton(btn_text)
                button.setStyleSheet(self.toggle_button_style())
                button.setCheckable(True)
                button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(type,btn, checked))
                lop_layout.addWidget(button)

        lop_box.setLayout(lop_layout)
        lop_box.setStyleSheet(self.panel_style())
        return lop_box

    def create_cop_panel(self):
        # Create a group box for the COP Panel
        cop_box = QGroupBox("COP PANEL")
        cop_layout = QVBoxLayout()
        layout = QHBoxLayout()
        grid_layout = QGridLayout()
        
        type = "COP"
        # Create buttons for COP Panel
        cop_buttons = [
            "Ground Floor", "First Floor", "Second Floor",
            "Third Floor", "Landing Lever", 
            "Child Lock", "Emergency", "Light", "Fan" 
        ]
        rgb_color_name = [
        ["Aqua", "Doger Blue", "Warm White", "Neutral White"], 
        ["Cold White", "Teal", "Gold", "Pale Blue"], [ "Orange Red", "Green Yellow", "Red", "Fuchsia"]
        ]
       
        for btn_text in cop_buttons:
            if btn_text == "Light" :
                button = QPushButton(btn_text)
                button.setStyleSheet(self.toggle_button_style())
                button.setCheckable(True)
                button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(type,btn, checked))
                cop_layout.addWidget(button)

                light_label = QLabel("Light Control")
                light_slider = QSlider(Qt.Orientation.Horizontal)
                light_slider.setRange(0, 100)
                light_slider.setValue(50)
                light_slider.valueChanged.connect(lambda value: self.on_slider_change("Light", value))
                #cop_layout.addWidget(light_label)
                cop_layout.addWidget(light_slider)  
              
                button_number = 0
                for row in range(len(rgb_color_name)):  # 3 rows
                    for col in range(len(rgb_color_name[row])):  # 4 columns
                        color_button = QPushButton(str(rgb_color_name[row][col]))
                        color_button.setStyleSheet(self.color_button_style())
                        #color_button.clicked.connect(lambda checked, num=button_number: self.on_button_click(num))
                        color_button.clicked.connect(lambda _, type="RGB", num=button_number: self.rgb_ml_color_button(type, num))
                        grid_layout.addWidget(color_button, row, col)
                        button_number += 1
                cop_layout.addLayout(grid_layout) 

         
            else :
                button = QPushButton(btn_text)
                button.setStyleSheet(self.toggle_button_style())
                button.setCheckable(True)
                button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(type,btn, checked))
                cop_layout.addWidget(button)

        # Add sliders for light and fan control with labels

        fan_label = QLabel("Fan Control")
        fan_slider = QSlider(Qt.Orientation.Horizontal)
        fan_slider.setRange(0, 100)
        fan_slider.setValue(50)
        fan_slider.valueChanged.connect(lambda value: self.on_slider_change("Fan", value))

        
        #cop_layout.addWidget(fan_label)
        cop_layout.addWidget(fan_slider)

        cop_box.setLayout(cop_layout)
        cop_box.setStyleSheet(self.panel_style())
        return cop_box
    
    def create_shaft_panel(self) :
        shaft_box = QGroupBox("SHAFT PANEL")
        shaft_layout = QVBoxLayout()

        shaft_buttons = [
            "Power", "lidar_connection", "lidar_distance",
            "TAutocalibration_Button", "Alarm", "Emergency" 
        ]



    def rgb_ml_color_button(self, type, num):
        if(type == "RGB") :
            RGB_android_cabin_dataC[4] = num
        elif(type == "ML") :
            print(f"Buttons {num} clicked!")
    
    
    def on_button_click(self, button_number):
        RGB_android_cabin_dataC[4] = button_number
        print(f"Button {button_number} clicked!")


    def on_toggle_button(self, type, button_name, checked):
        color = "green" if checked else "red"
        if button_name == "Landing Lever" and type == "COP":
            if checked == False:
                LL_android_cabin_data[4] = 0
            elif checked == True:
                LL_android_cabin_data[4] = 1

        if button_name == "Fan" and type == "COP":
            if checked == False:
                FanDatatoCab[4] = 0
            elif checked == True:
                FanDatatoCab[4] = 50
        if button_name == "Light" and type == "COP":
            print(checked)
            if  checked == False:
                RGB_android_cabin_dataC[2] = 0
                RGB_android_cabin_dataC[3] = 0
                
            elif checked == True :
                RGB_android_cabin_dataC[2] = 0x10
                RGB_android_cabin_dataC[3] = 50
        if button_name == "Child Lock" and type == "COP": 
            if  checked == False:
                RGB_android_cabin_dataC[2] = 0
                RGB_android_cabin_dataC[3] = 0
                
            elif checked == True :
                RGB_android_cabin_dataC[2] = 0x10
                RGB_android_cabin_dataC[3] = 50
        if button_name == "Emergency" and type == "COP":  
            if  checked == False:
                RGB_android_cabin_dataC[2] = 0
                RGB_android_cabin_dataC[3] = 0
                
            elif checked == True :
                RGB_android_cabin_dataC[2] = 0x10
                RGB_android_cabin_dataC[3] = 50
        if (button_name == "Ground Floor" or  button_name == "First Floor" or button_name =="Second Floor" or button_name == "Third Floor") :
            call_booking(type, button_name)  
        
        print(f"{button_name} toggled {'ON' if checked else 'OFF'}")
        self.sender().setStyleSheet(f"background-color: {color}; color: white; border-radius: 10px; padding: 10px;")

    def on_slider_change(self, slider_name, value):
        
        print(f"{slider_name} slider set to {value}")
        if(slider_name == "Light") :
            RGB_android_cabin_dataC[3] = value
            RGB_android_cabin_dataC[2] = 0x32
        
        if(slider_name == "Fan") :
            FanDatatoCab[4] = value

    def panel_style(self):
        return """
        QGroupBox {
            border: 2px solid #00ADB5;
            border-radius: 10px;
            margin-top: 10px;
            padding: 10px;
            font-weight: bold;
            color: white;
            background-color: #393E46;
        }
        QLabel {
            color: white;
            font-size: 14px;
        }
        """

    def toggle_button_style(self):
        return """
        QPushButton {
            background-color: #00ADB5;
            color: white;
            border-radius: 10px;
            padding: 10px;
            font-size: 14px;
        }
        QPushButton:hover {
            background-color: #007B7F;
        }
        """

    def color_button_style(self):
        return """
        QPushButton {
            background-color: #008367; 
            color: white;
            font-size: 16px;
            border-radius: 10px;
            padding: 10px;
        }
        QPushButton:hover {
            background-color: #007B7F;
        }
        """

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
   # np.array_equal()
    
    ws.send(LL_android_cabin_data)
    ws.send(RGB_android_cabin_dataC)
    ws.send(FanDatatoCab)
    print("Data Sent to cabin")
    print("cabnf" + " ".join(f",0x{byte:02x}" for byte in RGB_android_cabin_dataC))

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
#window = MainWindow()
window2 = LiftControlUI()
window2.setStyleSheet("background-color: #222831;")
#window.show()
window2.show()
# Start the PyQt event loop
sys.exit(app.exec())
