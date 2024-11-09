import sys
import threading
import socket
import struct
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QDialog,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout, QBoxLayout, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtProperty, QPropertyAnimation, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QPainter, QBrush


import websocket
from datetime import datetime
import time
import ctypes
import random

# Constants for multicast group
MCAST_GRP = '239.1.2.3'
MCAST_PORT = 2323
shaft_connectivity_flag = False
cabin_connectivity_flag = False

# Data lists
Broadcast_form_shaft = [0x60 ,0x00 ,0x00 ,0x00 ,0xdf ,0x00 ,0x00 ,0x00 ,0x00 ,0x03 ,0x05 ,0x00 ,0x00 ,0x80 ,0x07 ,0xff]
#Header, CabinCurrentFloor(A), Booking(L), ErrorStatus(A), CS, LDR Val, LL/Lop Floor num, Booking(cabin), DL status(L), DorSwitch(cabin), ML, SOS status, Ev state, DA, NeworkAvailability, Footer
#0x60 ,0x00 ,0x00 ,0xaf ,0xdf ,0x00 ,0x00 ,0x00 ,0x00 ,0x03 ,0x0a ,0x00 ,0x00 ,0x01 ,0x07 ,0xff
cabin_to_shaft = [0x25, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff]



#websocket objects 
wifi_cabin = None
wifi_shaft = None

lops_shaft = [
    bytearray([0x55, 0x00, 0x00, 0x01, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff]),  #Head, lop_flor, calBok_stat, cabin_flor, Door_sensor, ML, D_solenoid, dummy-to-see-missed, foot 
    bytearray([0x55, 0x01, 0x00, 0x01, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff]),
    #bytearray([0x55, 0x02, 0x00, 0x00, 0x01, 0x00, 0x00, 0x01, 0x00, 0xff]),
    #bytearray([0x55, 0x03, 0x00, 0x00, 0x01, 0x01, 0x00, 0x01, 0x00, 0xff])
]
cabin_to_tab = bytearray([0xd5, 0x00, 0x00, 0x00, 0x00, 0x64, 0x02, 0x00, 0x00, 0xff])  #Header, Call booking, Siren & downtime, CL, Emg, Battery,  charge, max_flr, update, footer (Totle floors count, LaFLiLo PWM, Update status, Footer)
                           #  0xd5 ,0x00 ,0x00 ,0x00 ,0x00 ,0x64 ,0x00 ,0x00 ,0x00 ,0xff   

# Data for Android Cabin
LL_android_cabin_data_to = [
    bytearray([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])   # 4th byte 1 RGB turned On 0 RGB turned off
    #bytes([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])    #
]
LL_android_cabin_data =  bytearray([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])   # 4th byte 1 RGB turned On 0 RGB turned off
RGB_android_cabin_dataC = bytearray([0x65, 0x05, 0x00, 0x00, 0x09, 0x00, 0x01, 0xff]) #Header, RGB-5, Timer, Bright, Color,  stay_0, stay_1, footer
FanDatatoCab = bytearray([0x65, 0x04, 0x01, 0x32, 0x01, 0xFF, 0xFF, 0xFF]) #Header, Dev, FAN-1, Time, 0-off 15 to 100% bright, Dummey, Dummey, Footer  


shaft_broad_cast = [] ##used to store the currentrecived brodcast
prev_err_state = "" #used to store the previous error state
prev_shaft_broad_cast = [] #used to store the previous error state of the Shaft broad cst
lidar_data = "" #contain the lidar value
# Function to format WebSocket URL
def get_ip(ip, port):
    return f"ws://{ip}:{port}/ws"

# Call booking logic
def call_booking(call_type, floor_name, checked):
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
        data = lops_shaft
        for floor in range(len(data)):
            if floor == floor_number and checked:
                data[floor][2] = 0x01  # Set the specific floor active
                print(f"Updated lops_shaft floor one [{floor}]: ", end="")
                print(" ".join(f"0x{byte:02x}" for byte in data[floor]))
                if(wifi_shaft != None):
                    wifi_shaft.send(data[floor])
            else:
                data[floor][2] = 0x00  # Reset other floors
                print(f"Updated lops_shaft floor [{floor}]: ", end="")
                print(" ".join(f"0x{byte:02x}" for byte in data[floor]))
                #wifi_shaft.send(data[floor])
            
            #window2.update_lidar_data(floor_number) #just to see the data is updating or not

    elif call_type == "COP": 
             
        if 0 <= floor_number <= len(lops_shaft)+1 and checked:
            data2 = cabin_to_tab
            data2[1] = 2 ** floor_number
            print("Updated cabin data: ", " ".join(f"0x{byte:02x}" for byte in data2))
            if(wifi_cabin != None):
                wifi_cabin.send(data2)
                
        elif not checked:
            data2 = cabin_to_tab
            print("Updated cabin data: ", " ".join(f"0x{byte:02x}" for byte in data2))
            if(wifi_cabin != None):            
                data2[1] = 0
                wifi_cabin.send(data2)
         
# WebSocket handling for real-time communication
def run_websocket_client(url, client_name):
    connect_error_panel = pyqtSignal(bytearray)
    data_recived = []
    
    def on_message(ws, message):
        ''' current_time = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        print(f"Time: {current_time} - Received message from {client_name}: " +
              " ".join(f",0x{byte:02x}" for byte in message))'''
        if client_name == 'cabin':
            data_received = [int.from_bytes([byte], byteorder='big', signed=True) for byte in message]
            print("Broadcast Cabin INT:", data_received)
            print(" ")
        elif client_name == 'shaft':
            global shaft_broad_cast, prev_shaft_broad_cast
            prev_shaft_broad_cast = [hex(bytess) for bytess in message]
            data_received = [int.from_bytes([byte], byteorder='big', signed=True) for byte in message]
            print("Broadcast shaft INT:", data_received)
            if(prev_shaft_broad_cast != shaft_broad_cast):
                shaft_broad_cast = [hex(bytess) for bytess in message]
                #print("In shafrt broadcast updater ", shaft_broad_cast)
                shaft_brodcast_updater()
                #threading.Thread(window2.update_lidar_data(shaft_broad_cast[5]))    
    def on_error(ws, error):
        print(f"{client_name} encountered error: {error}")

    def on_close(ws, close_status_code, close_msg):
        global shaft_connectivity_flag, cabin_connectivity_flag,wifi_cabin,wifi_shaft 
        if client_name == "shaft":
            shaft_connectivity_flag = False
            wifi_shaft = None
        elif client_name == "cabin":
            cabin_connectivity_flag = False
            wifi_cabin = None
        print(f"{client_name} connection closed with code: {close_status_code}, message: {close_msg}")

    def on_open(ws):
        global shaft_connectivity_flag, cabin_connectivity_flag,wifi_cabin,wifi_shaft
        if client_name == "shaft":
            print("shaft open")
            shaft_connectivity_flag = True
            #sendDataToShaft()
            threading.Thread(target=sendDataToShaft).start()
            wifi_shaft = ws
        elif client_name == "cabin":
            print("cabin open")
            cabin_connectivity_flag = True
            wifi_cabin = ws
            #sendDataToCabin()
            #threading.Thread(target=sendDataToCabin).start()
 
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

def shaft_brodcast_updater():
    global shaft_broad_cast
    #print("The updater  ....................................................",shaft_broad_cast)
    window2.check_update_brodcast_error(shaft_broad_cast)
    window2.update_lidar_data(shaft_broad_cast[5])
    window2.change_data(shaft_broad_cast[13])
    #return shaft_broad_cast

class AnimatedToggle(QCheckBox):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self.label = label
        self.setFixedSize(40, 20)
        self.setStyleSheet("background: transparent;")
        self._circle_position = 5
        self._circle_color = QColor("#FFFFFF")
        self._bg_color = QColor("#FF0000")
        self._active_color = QColor("#00FF00")
        self._animation = QPropertyAnimation(self, b"circle_position", self)
        self._animation.setDuration(100)

        self.stateChanged.connect(self.start_animation)
        
        # Disable user interaction with the checkbox (so it can't be toggled by the user)
        self.setEnabled(False)

    @pyqtProperty(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def start_animation(self):
        self._animation.stop()
        if self.isChecked():
            self._animation.setEndValue(self.width() - self.height() + 3)
            self._bg_color = self._active_color
        else:
            self._animation.setEndValue(3)
            self._bg_color = QColor("#FF0000")
        self._animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(self._bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        painter.setBrush(QBrush(self._circle_color))
        painter.drawEllipse(int(self._circle_position), 3, self.height() - 6, self.height() - 6)
        painter.end()

    def set_state(self, on):
        self.setChecked(on)  # This will update the toggle state
        self.start_animation()

class LiftControlUI(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Lift Control - LOP & COP Panels")
        #print("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        self.setGeometry(100, 100, 800, 600)
        global shaft_broad_cast
        # Main layout for both panels
        main_layout = QHBoxLayout()
        self.error_buttons = {}
        self.data_label = QLabel("Current Data: 0", self)
        connection_status_signal = pyqtSignal(bool)

        # Create LOP and COP panels
        lop_panel = self.create_lop_panel()
        cop_panel = self.create_cop_panel()
        shaft_panel = self.create_shaft_panel()
        Error_panel = self.create_error_panel()
        Data_panel = self.create_data_panel(shaft_broad_cast)
        # Add the panels to the main layout
        main_layout.addWidget(lop_panel)
        main_layout.addWidget(cop_panel)
        main_layout.addWidget(shaft_panel)
        main_layout.addWidget(Error_panel)

        outer_layout = QVBoxLayout()
        outer_layout.addLayout(main_layout)
        outer_layout.addWidget(Data_panel)
        self.setLayout(outer_layout)
        Device_panel = self.DerviceAvailablityPanel()
        Network_panel = self.DoorAvailablityPanel()
        outer_layout.addWidget(Device_panel)
        outer_layout.addWidget(Network_panel)
        self.setLayout(outer_layout)

                       
    def create_lop_panel(self):
        # Create a group box for the LOP Panel
        lop_box = QGroupBox("LOP PANEL")
        lop_layout = QVBoxLayout()
        grid_layout = QGridLayout()

        # Create buttons for LOP Panel
        lop_buttons = [
            "Ground Floor", "First Floor", "Second Floor",
            "Third Floor"
        ]
        ml_states = ["DS On","DS Off", "DL On", "DL Off", "ML Open", "ML Close", "ML Semi"]

        type = "LOP"

        for lop in range(len(lop_buttons)):
            button = QPushButton(lop_buttons[lop])
            button.setStyleSheet(self.toggle_button_style())
            button.setCheckable(True)
            button.toggled.connect(lambda checked, btn=lop_buttons[lop]:  self.on_toggle_button(type, btn, checked))
            lop_layout.addWidget(button)
            
            grid_layout = QGridLayout()
            for lock_index in range(len(ml_states)):
                lock_button = QPushButton(ml_states[lock_index])
                lock_button.setStyleSheet(self.color_button_style())
                lock_button.clicked.connect(lambda _, type="ML", btn=ml_states[lock_index], btn_num=lock_index, floor=lop: self.lop_data_button(type, btn, floor))
                grid_layout.addWidget(lock_button, lock_index // 4, lock_index % 4)  # Arrange in a grid (2 columns)

            # Add the grid layout under the floor button
            lop_layout.addLayout(grid_layout)
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
                        color_button.clicked.connect(lambda _, type="RGB", num=button_number: self.rgb_color_button(type, num))
                        grid_layout.addWidget(color_button, row, col)
                        button_number += 1
                cop_layout.addLayout(grid_layout) 

         
            else :
                button = QPushButton(btn_text)
                button.setStyleSheet(self.toggle_button_style())
                button.setCheckable(True)
                button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(type, btn, checked))
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
    
    def rgb_color_button(self, type, num):
        if(type == "RGB") :
            RGB_android_cabin_dataC[4] = num
        elif(type == "ML") :
            print(f"Buttons {num} clicked!")

    def create_shaft_panel(self) :
        shaft_box = QGroupBox("SHAFT PANEL")
        shaft_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        shaft_buttons = [
            "Power", "lidar_connection", "lidar_distance",
            "Autocalibration_Button", "Alarm", "Emergency" 
        ]

        for btn_text in shaft_buttons:
            #if btn_text == "Light":
            button = QPushButton(btn_text)
            button.setStyleSheet(self.toggle_button_style())
            button.setCheckable(True)
            button.toggled.connect(lambda checked, type = "SHAFT", btn=btn_text: self.on_toggle_button(type, btn, checked))
            shaft_layout.addWidget(button)

        shaft_box.setLayout(shaft_layout)
        shaft_box.setStyleSheet(self.panel_style())
        return shaft_box

    def check_update_brodcast_error(self, data):
        #print("Mesagee",data)
        global prev_err_state 
        if len(data) == 16 and data[0] == "0x60" and data[-1] == "0xff": #QPushButton { background-color: green; color: white;font-size: 12px; border-radius: 8px;padding: 8px; }"""
            print(type(data[3]), " " ,data[3])
            
            
            hex_data = data[14]
            cleaned_hex_data = hex_data.replace("0x", "").replace("x", "")
            binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_hex_data)
            print(f"Hex: {hex_data}")
            print(f"Binary: {binary_data}")
                        
            if data[3] == "0xaf" :
                if prev_err_state != "NF" and prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                prev_err_state = "NF"
                print("PrevErrorState  in None  ",type(prev_err_state), prev_err_state)
                print("No error")
            elif data[3] == "0x0":  #Door Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                    #print("....................................................")
                print("Door Lock error")
                button = self.error_buttons["DL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "DL"
                print("PrevErrorState  in Door  ",type(prev_err_state), prev_err_state)
            elif data[3] == "0x1":  #Mech Lock error
                
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["ML"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "ML"
            elif data[3] == "0x2":  #Mech Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["WF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "WF"
            elif data[3] == "0x3":  #Mech Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["WF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "WF"
            elif data[3] == "0x4":  #Lidar Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["LR"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "LR"
            elif data[3] == "0x5":  #Over Load error from device
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["OD"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OD"
            elif data[3] == "0x6":  #Over Load error from user
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["OU"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OU"
            elif data[3] == "0x7" or data[13] == "0x1" :  #Power error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["PF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "PF"            
            elif data[3] == "0x8":  #Cabin out of range
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["CO"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CO"
            elif data[3] == "0xA" or  data[3] == "0xa":  #Cabin Not available
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["CN"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CN"
            elif data[3] == "0xc" or data[3] == "0xC":  #Child Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["CL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CL"
            elif data[3] == "0xE" or data[3] == "0xe":  #Parental Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["PL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "PL"
            elif data[3] == "0xF" or data[3] == "0xf":  #Light Curtain error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["LC"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "LC"
            elif data[3] == "0x10":  #Over Speed error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["OS"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OS"
            elif data[3] == "0x11":  #Device Under Update 
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                button = self.error_buttons["OTA"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OTA"
            
        #print(" ".join(f"0x{byte:02x}" for byte in data))
    
    def update_lidar_data(self, data):
        global lidar_data
        lidar_data = int(data, 16) 
        self.data_label.setText(f"Lidar Value: {lidar_data} ")
        #self.data_label.setText(f"<span style='color: yellow; font-weight: bold;'>Lidar Value: {lidar_data} place</span>")
        return lidar_data

    def create_data_panel(self, data):
        data_box = QGroupBox("Data PANEL")
        data_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        print("Data")

        global shaft_broad_cast
        global  lidar_data #self.update_lidar_data() #100 #data[5]
        print("Lidar Val is .....................", lidar_data)
    # Randomly update global_data to simulate changes
        #lidar_val   = random.randint(0, 100)

        #self.setWindowTitle("Global Data Error Monitor")
        self.data_label = QLabel((f"Lidar Value: {lidar_data}   "),self)
        #self.data_label.setText(f"Lidar Value: {lidar_data} place")
        err_button = QPushButton("Lidar Val" + "")
        """self.error_label = QLabel("", self)
        self.error_label.setStyleSheet("color: red; font-weight: bold;")"""

        #layout = QVBoxLayout()
        data_layout.addWidget(self.data_label)
        data_box.setLayout(data_layout)
        data_box.setStyleSheet(self.panel_style())
        data_box.setStyleSheet("color: Yellow; font-weight: bold;")
        #data_box.setStyleSheet("border: 2px solid #00ADB5; border-radius: 8px;margin-top: 8px; padding: 8px;font-weight: bold;color: white;background-color: #393E46")
        #self.data_label.setText(f"<span style='color: yellow; font-weight: bold;'>Lidar Value: {lidar_data} place</span>")
        #self.data_label.setText(f"Lidar Value: {lidar_data} place")
        # Set font size, color, and style
        return data_box

    def create_error_panel(self):
        erroe_box = QGroupBox("Error PANEL")
        error_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        
        # Error button identifiers
        error_types = ["CB", "SB", "PF", "SE", "CE", "OU", "OD", "AC", "WF", "DL", "LR", "CL", "LB", "PL", "ML", "LN", "LC", "OS", "OTA", "CN", "CO"]
        for type_index in range(len(error_types)):
            err_name = error_types[type_index]
            err_button = QPushButton(err_name)
            err_button.setStyleSheet(f"background-color: red; color: white;")
            #err_button.setStyleSheet(f"background-color: red; color: white;font-size: 12px; border-radius: 8px;padding: 8px; width:40px; height:30px")
            #err_button.setStyleSheet(self.get_button_style(0))
            #lock_button.clicked.connect(lambda _, type="ML", btn=shaft_buttons[lock_index], btn_num=lock_index, floor=lop: self.lop_data_button(type, btn, floor))

            grid_layout.addWidget(err_button, type_index // 3, type_index % 3)  # Arrange in a grid (2 columns)
            self.error_buttons[err_name] = err_button
        erroe_box.setLayout(grid_layout)
        erroe_box.setStyleSheet(self.panel_style())
        return erroe_box

    def clickHandler(self, ErrorName):
      
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{ErrorName} Error States")

        error_layout = QVBoxLayout()
        grid_layout = QGridLayout()

        er_states = ["floor G", "floor 1", "floor 2", "floor 3"]

        for i, floor in enumerate(er_states):
            error_type = QPushButton(f"{floor} - {ErrorName}")

            error_type.setStyleSheet(self.get_button_style(0))  # Green color (assuming resolved state)
            grid_layout.addWidget(error_type, i, 0)
            
        error_layout.addLayout(grid_layout)
        dialog.setLayout(error_layout)
        dialog.exec()
    
    def DerviceAvailablityPanel(self):
        toggle_box = QGroupBox("Device Availability Panel")
        toggle_layout = QGridLayout()  # Use QGridLayout for grid arrangement

        # Define the labels for each toggle switch
        self.Device_toggles = {
            "Power Available":AnimatedToggle("Power Available"),
            "Over Load":AnimatedToggle("Over Load"),
            "Emergency Shaft":AnimatedToggle("Emergency Shaft"),
            "Calibibration":AnimatedToggle("Calibibration"),
            "Lidar Device":AnimatedToggle("Lidar Device"),
            "Child Lock":AnimatedToggle("Child Lock"),
            "Emergency Cabin":AnimatedToggle("Emergency Cabin"),
            "Device OTA":AnimatedToggle("Device OTA"),
        }
        #toggle_layout.setHorizontalSpacing(150)  # Adjust this value as needed for more space between columns
        #toggle_layout.setVerticalSpacing(15)
        toggle_layout.setSpacing(10)
        row = 0
        col = 0
        for label, toggle in self.Device_toggles.items():
            label_widget = QLabel(label)
            
            # Add the label and toggle to the grid layout
            
            toggle_layout.addWidget(toggle, row, col * 2 )    # Toggle on the right side
            toggle_layout.addWidget(label_widget, row, col * 2 + 1)  # Label on the left side

            col += 1
            if col == 4:  # Move to the next row after three toggles
                col = 0
                row += 1

        toggle_box.setLayout(toggle_layout)
        toggle_box.setStyleSheet("color: White; font-weight: bold;")
        return toggle_box
    
    def set_toggle_state(self, label, state):
        if label in self.Device_toggles:
            self.Device_toggles[label].set_state(state)

    def update_toggles(self, data):
        print("Binary Data Here:", data)
        data.reverse()
        print("Binary Data Here:", data)
        # Update toggles based on the incoming data
        self.set_toggle_state("Power Available", data[0] != '1')  # Is power device is off = 1 then power is on 
        self.set_toggle_state("Over Load", data[1] == '1')
        self.set_toggle_state("Emergency Shaft", data[2] == '1')
        self.set_toggle_state("Calibibration", data[3] == '1')
        self.set_toggle_state("Lidar Device", data[4] == '1')
        self.set_toggle_state("Child Lock", data[5] == '1')
        self.set_toggle_state("Emergency Shaft", data[6] == '1')
        self.set_toggle_state("Device OTA", data[7] == '1')

    def change_data(self, data):
        # This function is called periodically to change the data and update toggles
        #print("In the change data", data)
        hex_data = data
        cleaned_hex_data = hex_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_hex_data)
        toggle_data = list(binary_data[:8])  # Convert the first 8 bits to a list of '1' and '0' strings  
        self.update_toggles(toggle_data)  # Update the toggle switches with binary data

    def DoorAvailablityPanel(self):
        toggle_box = QGroupBox("Network Availability Panel")
        toggle_layout = QGridLayout()  # Use QGridLayout for grid arrangement

        # Define the labels for each toggle switch
        self.Nework_toggles = {
            "Door G":AnimatedToggle("Door G"),
            "Door 1":AnimatedToggle("Door 1"),
            "Door 2":AnimatedToggle("Door 2"),
            "Door 3":AnimatedToggle("Door 3"),
            "Solinoid G":AnimatedToggle("Solinoid G"),
            "Solinoid 1":AnimatedToggle("Solinoid 1"),
            "Solinoid 2":AnimatedToggle("Solinoid 2"),
            "Solinoid 3":AnimatedToggle("Solinoid 3"),
        }
        #toggle_layout.setHorizontalSpacing(150)  # Adjust this value as needed for more space between columns
        #toggle_layout.setVerticalSpacing(15)
        toggle_layout.setSpacing(10)
        row = 0
        col = 0
        for label, toggle in self.Nework_toggles.items():
            label_widget = QLabel(label)
            
            # Add the label and toggle to the grid layout
            toggle_layout.addWidget(label_widget, row, col * 2+1)  # Label on the left side
            toggle_layout.addWidget(toggle, row, col * 2 )    # Toggle on the right side

            col += 1
            if col == 4:  # Move to the next row after three toggles
                col = 0
                row += 1

        toggle_box.setLayout(toggle_layout)
        toggle_box.setStyleSheet("color: White; font-weight: bold;")
        return toggle_box
    

    def lop_data_button(self, type, btn, floor):   #ml_states = ["Door Switch", "Solenoid", "ML Open", "ML Close", "ML Semi"]
        #print(" ".join(f"0x{byte:02x}" for byte in lops_shaft[floor]))
        if(floor < len(lops_shaft)) :

            if(type == "ML") :
                if(btn == "DS On") :
                    lops_shaft[floor][4] = 0
                elif(btn == "DS Off") :
                    lops_shaft[floor][4] = 1
                elif(btn == "ML Open") :
                    lops_shaft[floor][5] = 1
                elif(btn == "ML Close") :
                    lops_shaft[floor][5] = 0
                elif(btn == "ML Semi") :
                    lops_shaft[floor][5] = 2
                elif(btn == "DL On") :
                    lops_shaft[floor][6] = 1
                elif(btn == "DL Off") :
                    lops_shaft[floor][6] = 0
                print(f"Floor {floor} {btn} Button clicked!")
                #print(" ".join(f"0x{byte:02x}" for byte in lops_shaft[floor]))
        else :
            print("Floor is not available")

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
                print("CL oFF")
                cabin_to_shaft[2] = 0 
                cabin_to_tab[3] = 0
                
            elif checked == True :
                print("CL on")
                cabin_to_shaft[2] = 1
                cabin_to_tab[3] = 1
        if button_name == "Emergency" and type == "COP":  
            if  checked == False:
                print("Emg oFF")
                cabin_to_shaft[3] = 0  
                cabin_to_tab[4] = 0              
            elif checked == True :
                print("Emg on")
                cabin_to_shaft[3] = 1
                cabin_to_tab[4] = 1
        if (button_name == "Ground Floor" or  button_name == "First Floor" or button_name =="Second Floor" or button_name == "Third Floor") :
            #print("Floor booked for ", type)
            call_booking(type, button_name, checked)  
        
        print(f"{button_name} toggled {'ON' if checked else 'OFF'}")
        self.sender().setStyleSheet(f"background-color: {color}; color: white; border-radius: 8px; padding: 8px;font-weight: bold; ")

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
            border-radius: 8px;
            margin-top: 8px;
            padding: 8px;
            font-weight: bold;
            color: white;
            background-color: #393E46;
        }
        QLabel {
            color: blue;
            font-size: 10px;
        }
        """

    def toggle_button_style(self):
        return """
        QPushButton {
            background-color:#007B7F;
            font-weight: bold;
            color: white;
            border-radius: 8px;
            padding: 8px;
            font-size: 10px;
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
            font-size: 10px;
            border-radius: 8px;
            padding: 8px;
        }
        QPushButton:hover {
            background-color: #007B7F;
        }
        """
    
    def get_button_style(self, error_state):
        """Return the appropriate button style based on the error state (0 = red, 1 = green)."""
        if error_state == 1:
            return """
            QPushButton {
                background-color: green;
                color: white;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px;
            }
            """
        elif error_state == 2:
            return """
            QPushButton {
                background-color: yellow;
                color: black;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px;
            }
            """
        else:
            return """
            QPushButton {
                background-color: red;
                color: white;
                font-size: 12px;
                border-radius: 8px;
                padding: 8px;
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
        print("DATA UDP ", " ".join(f"0x{byte:02x}" for byte in data))
        if data[0] == 0xde and data[1] == 0x01 and not shaft_connectivity_flag:
            print("Connecting to shaft at ", addr[0],  data)

            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5151), "shaft")).start()
        elif data[0] == 0xde and data[1] == 0x02 and not cabin_connectivity_flag:
            print("Connecting to cabin at ", addr[0])
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5050), "cabin")).start()

def sendDataToCabin():
    global cabin_connectivity_flag,wifi_cabin
    while(cabin_connectivity_flag):
        #print("sending cabin data",RGB_android_cabin_dataC)
        if wifi_cabin != None:
            #wifi_cabin.send(LL_android_cabin_data)
            #wifi_cabin.send(RGB_android_cabin_dataC)
            #wifi_cabin.send(FanDatatoCab)
            pass
        time.sleep(0.5) 

def sendDataToShaft():
    global shaft_connectivity_flag,wifi_shaft
    print("sendDataToShaft.........", type(wifi_shaft), wifi_shaft)
    while(shaft_connectivity_flag):
        if wifi_shaft != None:
            #wifi_shaft.send(cabin_to_shaft)
            for lop in range(2):
                wifi_shaft.send(lops_shaft[lop])
            wifi_shaft.send(cabin_to_tab)    
        time.sleep(0.4)        

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

