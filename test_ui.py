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
import os
import websocket
from datetime import datetime
import time
import ctypes
import random
import atexit

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
LL_android_cabin_data =  bytearray([0x65, 0x00, 0x09, 0x02, 0x00, 0xFF, 0xFF, 0xFF])   # 4th byte 1 RGB turned On 0 RGB turned off
RGB_android_cabin_dataC = bytearray([0x65, 0x05, 0x00, 0x00, 0x09, 0x00, 0x01, 0xff]) #Header, RGB-5, Timer, Bright, Color,  stay_0, stay_1, footer
FanDatatoCab = bytearray([0x65, 0x04, 0x01, 0x32, 0x01, 0xFF, 0xFF, 0xFF]) #Header, Dev, FAN-1, Time, 0-off 15 to 100% bright, Dummey, Dummey, Footer  


shaft_broad_cast = [] ##used to store the currentrecived brodcast
prev_err_state = "" #used to store the previous error state
prev_shaft_broad_cast = [] #used to store the previous error state of the Shaft broad cst
lidar_data = "" #contain the lidar value

folder_name = "LOGFOLDER"
#FIle_Name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
FIle_Name = datetime.now().strftime("%Y-%m-%d_%H") + "_log.txt"
file_path = os.path.join(folder_name, FIle_Name)
os.makedirs(folder_name, exist_ok=True)

with open(file_path, "w") as LOGFILE:
    LOGFILE.write("Log entry example\n")
print(f"Log file created at: {file_path}")
LOGFILE = open(file_path, "w")


def close_logfile():
    LOGFILE.close()

atexit.register(close_logfile)

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
        LOGFILE.write(f"{datetime.now()} -- Invalid floor name: {floor_name} \n")
        return
    floor_number = floor_mapping[floor_name]
    print(f"{call_type} Call Booked for ............ {floor_number}")
    result = "Pressed" if checked else "Release"
    LOGFILE.write(f"{datetime.now()} -- In UI {call_type} Call Button {result} for floor {floor_number} \n")
    
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
                #wifi_shaft.send(data[floor]
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
            LOGFILE.write(str(f"{datetime.now()} -- Broadcast Cabin INT: {data_received} \n"))
            print(" ")
        elif client_name == 'shaft':
            global shaft_broad_cast, prev_shaft_broad_cast
            prev_shaft_broad_cast = [hex(bytess) for bytess in message]
            data_received = [int.from_bytes([byte], byteorder='big', signed=True) for byte in message]
            print("Broadcast shaft INT:", data_received)
            LOGFILE.write(str(f"{datetime.now()} -- Broadcast shaft INT: {data_received} \n"))
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
        LOGFILE.write(f"{datetime.now()} -- {client_name} connection opened \n")

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
    window2.update_lidar_data(shaft_broad_cast[5], shaft_broad_cast[1])
    window2.change_data(shaft_broad_cast)
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

    def semi_animation(self):
        self._animation.stop()
        self._animation.setEndValue(3)
        self._bg_color = QColor("#fc03cf")
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
        #print("The on : ", on)
        if(on == 2):
            self.semi_animation()
        else :
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
        self.Data_panel = self.create_data_panel(shaft_broad_cast)
        # Add the panels to the main layout
        
        main_layout.addWidget(lop_panel)
        main_layout.addWidget(cop_panel)
        main_layout.addWidget(shaft_panel)
        main_layout.addWidget(Error_panel)


        # Define outer_layout and add main_container
        """
        main_container = QWidget(self)
        main_container.setLayout(main_layout)
        main_container.setFixedSize(6000, 4000)  # Set your desired fixed size here
        self.outer_layout = QVBoxLayout()
        self.outer_layout.addWidget(main_container)
        self.outer_layout.addWidget(Data_panel)"""

        self.outer_layout = QVBoxLayout()            
        self.outer_layout.addLayout(main_layout)
        self.outer_layout.addWidget(self.Data_panel)

        self.toggle_button = QPushButton("Toggle Panels", self)
        self.toggle_button.setStyleSheet(self.toggle_button_style())
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(lambda checked, :  self.hide_outer_layout(checked))
        self.outer_layout.addWidget(self.toggle_button)

        self.Device_panel = self.DerviceAvailablityPanel()
        self.Door_panel = self.DoorAvailablityPanel()
        self.Network_panel = self.NetworkAvailablityPanel()
        self.MechLock_panel = self.MechLock_AvailablityPanel()
        self.outer_layout.addWidget(self.Device_panel)
        self.outer_layout.addWidget(self.Door_panel)
        self.outer_layout.addWidget(self.Network_panel)
        self.outer_layout.addWidget(self.MechLock_panel)
        self.setLayout(self.outer_layout)

    def chechched(self, checked):
        print("cheched", checked)

    def hide_outer_layout(self, visibility):
            self.toggle_panel_visibility(self.Data_panel, visibility)
            self.toggle_panel_visibility(self.Device_panel, visibility)
            self.toggle_panel_visibility(self.Door_panel, visibility)
            self.toggle_panel_visibility(self.Network_panel, visibility)
            self.toggle_panel_visibility(self.MechLock_panel, visibility)
        
    def toggle_panel_visibility(self, panel, visible):
        panel.setVisible(visible)
            
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
            LOGFILE.write(f"{datetime.now()} -- Buttons {num} clicked!")

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
            
            #print(type(data[3]), " " ,data[3])
            '''
            hex_data = data[14]
            cleaned_hex_data = hex_data.replace("0x", "").replace("x", "")
            binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_hex_data)
            print(f"Hex: {hex_data}")
            print(f"Binary: {binary_data}")
            '''           
            if data[3] == "0xaf" :
                if prev_err_state != "NF" and prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                prev_err_state = "NF"
                print("PrevErrorState  in None  ",type(prev_err_state), prev_err_state)
                print("No error")
                LOGFILE.write(str(f"{datetime.now()} -- No error \n"))
            elif data[3] == "0x0":  #Door Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Door Lock error \n"))
                print("Door Lock error")
                button = self.error_buttons["DL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "DL"
                print("PrevErrorState  in Door  ",type(prev_err_state), prev_err_state)
            elif data[3] == "0x1":  #Mech Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                
                LOGFILE.write(str(f"{datetime.now()} -- Mech Lock error \n"))
                button = self.error_buttons["ML"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "ML"
            elif data[3] == "0x2":  #Communication error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Communication error \n"))
                button = self.error_buttons["WF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "WF"
            elif data[3] == "0x3":  #Communication error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Communication error \n"))
                button = self.error_buttons["WF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "WF"
            elif data[3] == "0x4":  #Lidar error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Lidar error \n"))
                button = self.error_buttons["LR"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "LR"
            elif data[3] == "0x5":  #Over Load error from device
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Over Load error from device \n"))
                button = self.error_buttons["OD"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OD"
            elif data[3] == "0x6":  #Over Load error from user
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Over Load error from user \n"))
                button = self.error_buttons["OU"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OU"
            elif data[3] == "0x7" or data[13] == "0x1" :  #Power error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Power error \n"))
                button = self.error_buttons["PF"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "PF"            
            elif data[3] == "0x8":  #Cabin out of range
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Cabin out of range \n"))
                button = self.error_buttons["CO"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CO"
            elif data[3] == "0xA" or  data[3] == "0xa":  #Cabin Not available
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Cabin Not available \n"))
                button = self.error_buttons["CN"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CN"
            elif data[3] == "0xc" or data[3] == "0xC":  #Child Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Child Lock error \n"))
                button = self.error_buttons["CL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "CL"
            elif data[3] == "0xE" or data[3] == "0xe":  #Parental Lock error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Parental Lock error \n"))
                button = self.error_buttons["PL"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "PL"
            elif data[3] == "0xF" or data[3] == "0xf":  #Light Curtain error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Light Curtain error \n"))
                button = self.error_buttons["LC"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "LC"
            elif data[3] == "0x10":  #Over Speed error
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Over Speed error \n"))
                button = self.error_buttons["OS"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OS"
            elif data[3] == "0x11":  #Device Under Update 
                if prev_err_state in self.error_buttons:
                    button = self.error_buttons[prev_err_state]
                    button.setStyleSheet(f"background-color: red; color: white;")
                LOGFILE.write(str(f"{datetime.now()} -- Device Under Update \n"))
                button = self.error_buttons["OTA"]
                button.setStyleSheet(f"background-color: yellow; color: black;")
                prev_err_state = "OTA"
            
        #print(" ".join(f"0x{byte:02x}" for byte in data))
    
    def update_lidar_data(self, data, current_floor):
        global lidar_data
        lidar_data = int(data, 16) 
        current_floor = current_floor.replace("0x", "").replace("x", "")
        self.data_label.setText(f"Lidar Value: {lidar_data}  Lift Current Floor: {current_floor}")
        LOGFILE.write(str(f"{datetime.now()} -- Lidar Value: {lidar_data}   Lift Current Floor: {current_floor} \n"))
        return lidar_data

    def create_data_panel(self, data):
        data_box = QGroupBox("Data PANEL")
        data_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        print("Data")

        global shaft_broad_cast
        global  lidar_data #self.update_lidar_data() #100 #data[5]
        print("Lidar Val is .....................", lidar_data)
        self.data_label = QLabel((f"Lidar Value: {lidar_data}      Lift Current Floor: {lidar_data}"), self)
        data_layout.addWidget(self.data_label)
        data_box.setLayout(data_layout)
        data_box.setStyleSheet(self.panel_style())
        data_box.setStyleSheet("color: Yellow; font-weight: bold; font-size: 10px")
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
        toggle_box.setStyleSheet("color: White; font-weight: bold; font-size: 10px")
        return toggle_box
    
    def set_toggle_state(self, label, state):
        print(label, state)
        if label in self.Device_toggles:
            self.Device_toggles[label].set_state(state)
        elif label in self.Door_switch_toggles:
            self.Door_switch_toggles[label].set_state(state)
        elif label in self.Network_switch_toggles:
            self.Network_switch_toggles[label].set_state(state)
        elif label in self.Mechanical_lock_toggles:
            if(state == "00") :
                self.Mechanical_lock_toggles[label].set_state(False)
            elif(state == "10"):
                self.Mechanical_lock_toggles[label].set_state(True)
            elif(state == "11"):
                self.Mechanical_lock_toggles[label].set_state(2)
            else:
                self.Mechanical_lock_toggles[label].set_state(state)

    def Update_Device_toggles(self, data, data_type):
       
        if data_type == "Devices" :
            data.reverse()
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            power = "1" if data[0] == "0" else "1"
            LOGFILE.write(f"{datetime.now()} -- Power {power} OL {data[1]} Emg Shaft {data[2]} Calib {data[3]} Lidar {data[4]} CL {data[5]} Emg Cabin {data[6]} OTA {data[7]}\n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Power Available", data[0] != '1')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("Over Load", data[1] == '1')
            self.set_toggle_state("Emergency Shaft", data[2] == '1')
            self.set_toggle_state("Calibibration", data[3] == '1')
            self.set_toggle_state("Lidar Device", data[4] == '1')
            self.set_toggle_state("Child Lock", data[5] == '1')
            self.set_toggle_state("Emergency Cabin", data[6] == '1')
            self.set_toggle_state("Device OTA", data[7] == '1')
                        
        elif data_type == "Door_Switch" :
            data.reverse()
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Door_G : {data[0]} Door_1 : {data[1]} Door_2 : {data[2]} Door_3 : {data[3]} \n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Door G", data[0] == '1')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("Door 1", data[1] == '1')
            self.set_toggle_state("Door 2", data[2] == '1')
            self.set_toggle_state("Door 3", data[3] == '1')
        
        elif data_type == "Door_Lock" :
            data.reverse()
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Solenoid_G : {data[0]} Solenoid_1 : {data[1]} Solenoid_2 : {data[2]} Solenoid_3 : {data[3]} \n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Solenoid G", data[0] == '0')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("Solenoid 1", data[1] == '0')
            self.set_toggle_state("Solenoid 2", data[2] == '1')
            self.set_toggle_state("Solenoid 3", data[3] == '1')
        elif data_type == "Network" :
            data.reverse()
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Cabin : {data[0]} LOP_0 : {data[1]} LOP_1 : {data[2]} LOP_2 : {data[3]} \n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Cabin", data[0] == '1')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("LOP 0", data[1] == '1')
            self.set_toggle_state("LOP 1", data[2] == '1')
            self.set_toggle_state("LOP 2", data[3] == '1')
            self.set_toggle_state("LOP 3", data[4] == '1')
            #self.set_toggle_state("LOP 3", data[4] == '1') 
        
        elif data_type == "LL" :
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Landing Lever : {data} \n")
            self.set_toggle_state("LL", data == '1')  # Is power device is off = 1 then power is on

        elif data_type == "EVO" :
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- EVO : {data} \n")
            self.set_toggle_state("EVO", data == '1')  # Is power device is off = 1 then power is on 
        
        elif data_type == "SOS" :
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- SOS : {data} \n")
            self.set_toggle_state("SOS", data == '1')  # Is power device is off = 1 then power is on 

        elif data_type == "ML" :
            #data = ['0', '0', '1', '1', '0', '1', '1', '1']
            data.reverse()
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            ML_G = data[0] + data[1]
            ML_1 = data[2] + data[3]
            ML_2 = data[4] + data[5]
            ML_3 = data[6] + data[7]
            LOGFILE.write(f"{datetime.now()} -- ML_G : {ML_G}, ML_1 : {ML_1}, ML_2 : {ML_2}, ML_3 : {ML_3} \n")
            self.set_toggle_state("ML G",  ML_G)  # Is power device is off = 1 then power is on 
            self.set_toggle_state("ML 1", ML_1)  # Is power device is off = 1 then power is on 
            self.set_toggle_state("ML 2", ML_2)
            self.set_toggle_state("ML 3", ML_3)
        
        elif data_type == "LOP Booked" :
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- LOP Booked : {data} \n")
            self.set_toggle_state("LOP Booked", data == '1')

        elif data_type == "COP Booked" :
            print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- COP Booked : {data} \n")
            self.set_toggle_state("COP Booked", data == '1')

    def change_data(self, data):
        # This function is called periodically to change the data and update toggles
        #print("In the change data", data)
        Device_data = data[13]
        Door_switch_data = data[9]
        Door_Lock_data = data[8]
        Network_data = data[14]
        LL_data = data[6]
        Evo_data = data[12]
        SOS_data = data[11]
        ML_data = data[10]
        LOP_Booked_data = data[2]
        COP_Booked_data = data[7]

        toggle_data = COP_Booked_data.replace("0x", "").replace("x", "")
        self.Update_Device_toggles(str(toggle_data), "COP Booked")

        cleaned_Device_hex_data = Device_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_Device_hex_data)
        toggle_data = list(binary_data[:8])  # Convert the first 8 bits to a list of '1' and '0' strings  
        self.Update_Device_toggles(toggle_data, "Devices")  # Update the toggle switches with binary data
        
        cleaned_DS_hex_data = Door_switch_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_DS_hex_data)
        toggle_data = list(binary_data[:8])  # Convert the first 8 bits to a list of '1' and '0' strings
        self.Update_Device_toggles(toggle_data, "Door_Switch")
        
        cleaned_DL_hex_data = Door_Lock_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_DL_hex_data)
        toggle_data = list(binary_data[:8])  # Convert the first 8 bits to a list of '1' and '0' strings
        self.Update_Device_toggles(toggle_data, "Door_Lock")

        cleaned_Network_hex_data = Network_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '05b') for char in cleaned_Network_hex_data)
        toggle_data = list(binary_data[:8])  # Convert the first 8 bits to a list of '1' and '0' strings  
        self.Update_Device_toggles(toggle_data, "Network")  # Update the toggle switches with binary data

        toggle_data = LL_data.replace("0x", "").replace("x", "")
        self.Update_Device_toggles(str(toggle_data), "LL")

        toggle_data = Evo_data.replace("0x", "").replace("x", "")
        self.Update_Device_toggles(str(toggle_data), "EVO")

        toggle_data = SOS_data.replace("0x", "").replace("x", "")
        self.Update_Device_toggles(str(toggle_data), "SOS")

        cleaned_ML_hex_data = ML_data.replace("0x", "").replace("x", "")
        binary_data = ''.join(format(int(char, 16), '08b') for char in cleaned_ML_hex_data)
        toggle_data = list(binary_data)
        self.Update_Device_toggles(toggle_data, "ML")

        toggle_data = LOP_Booked_data.replace("0x", "").replace("x", "")
        self.Update_Device_toggles(str(toggle_data), "LOP Booked")

        


    def DoorAvailablityPanel(self):
        toggle_box = QGroupBox("Door Availability Panel")
        toggle_layout = QGridLayout()  # Use QGridLayout for grid arrangement

        # Define the labels for each toggle switch
        self.Door_switch_toggles = {
            "Door G":AnimatedToggle("Door G"),
            "Door 1":AnimatedToggle("Door 1"),
            "Door 2":AnimatedToggle("Door 2"),
            "Door 3":AnimatedToggle("Door 3"),
            "Solenoid G":AnimatedToggle("Solenoid G"),
            "Solenoid 1":AnimatedToggle("Solenoid 1"),
            "Solenoid 2":AnimatedToggle("Solenoid 2"),
            "Solenoid 3":AnimatedToggle("Solenoid 3"),
        }
        #toggle_layout.setHorizontalSpacing(150)  # Adjust this value as needed for more space between columns
        #toggle_layout.setVerticalSpacing(15)
        toggle_layout.setSpacing(10)
        row = 0
        col = 0
        for label, toggle in self.Door_switch_toggles.items():
            label_widget = QLabel(label)
            
            # Add the label and toggle to the grid layout
            toggle_layout.addWidget(label_widget, row, col * 2+1)  # Label on the left side
            toggle_layout.addWidget(toggle, row, col * 2 )    # Toggle on the right side

            col += 1
            if col == 4:  # Move to the next row after three toggles
                col = 0
                row += 1

        toggle_box.setLayout(toggle_layout)
        toggle_box.setStyleSheet("color: White; font-weight: bold; font-size: 10px")
        return toggle_box  
     
    def NetworkAvailablityPanel(self):
        toggle_box = QGroupBox("Network Availability Panel")
        toggle_layout = QGridLayout()  # Use QGridLayout for grid arrangement

        # Define the labels for each toggle switch
        self.Network_switch_toggles = {
            "Cabin":AnimatedToggle("Cabin"),
            "LOP 0":AnimatedToggle("LOP 0"),
            "LOP 1":AnimatedToggle("LOP 1"),
            "LOP 2":AnimatedToggle("LOP 2"),
            "LOP 3":AnimatedToggle("LOP 3"),          
            "LL":AnimatedToggle("LL"),
            "EVO":AnimatedToggle("EVO"),
            "SOS":AnimatedToggle("SOS"),
            #"Solenoid 3":AnimatedToggle("Solenoid 3"),
        }
        #toggle_layout.setHorizontalSpacing(150)  # Adjust this value as needed for more space between columns
        #toggle_layout.setVerticalSpacing(15)
        toggle_layout.setSpacing(10)
        row = 0
        col = 0
        for label, toggle in self.Network_switch_toggles.items():
            label_widget = QLabel(label)
            
            # Add the label and toggle to the grid layout
            toggle_layout.addWidget(label_widget, row, col * 2+1)  # Label on the left side
            toggle_layout.addWidget(toggle, row, col * 2 )    # Toggle on the right side

            col += 1
            if col == 4:  # Move to the next row after three toggles
                col = 0
                row += 1

        toggle_box.setLayout(toggle_layout)
        toggle_box.setStyleSheet("color: White; font-weight: bold; font-size: 10px")
        return toggle_box
    
    def MechLock_AvailablityPanel(self):
        toggle_box = QGroupBox("Mechanical Availability Panel")
        toggle_layout = QGridLayout()  # Use QGridLayout for grid arrangement

        # Define the labels for each toggle switch
        self.Mechanical_lock_toggles = {
            "ML G":AnimatedToggle("ML G"),
            "ML 1":AnimatedToggle("ML 1"),
            "ML 2":AnimatedToggle("ML 2"),
            "ML 3":AnimatedToggle("ML 3"),   
            "LOP Booked":AnimatedToggle("LOP Booked"),
            "COP Booked":AnimatedToggle("COP Booked"),
            #"SOS":AnimatedToggle("SOS"),
            #"Solenoid 3":AnimatedToggle("Solenoid 3"),
        }
        toggle_layout.setSpacing(10)
        row = 0
        col = 0
        for label, toggle in self.Mechanical_lock_toggles.items():
            label_widget = QLabel(label)
            
            # Add the label and toggle to the grid layout
            toggle_layout.addWidget(label_widget, row, col * 2+1)  # Label on the left side
            toggle_layout.addWidget(toggle, row, col * 2 )    # Toggle on the right side

            col += 1
            if col == 4:  # Move to the next row after three toggles
                col = 0
                row += 1

        toggle_box.setLayout(toggle_layout)
        toggle_box.setStyleSheet("color: White; font-weight: bold; font-size: 10px")
        return toggle_box
    
    def lop_data_button(self, type, btn, floor):  
        #ml_states = ["Door Switch", "Solenoid", "ML Open", "ML Close", "ML Semi"]
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
                LOGFILE.write(f"{datetime.now()} -- Floor {floor} {btn} Button clicked! \n")
                #print(" ".join(f"0x{byte:02x}" for byte in lops_shaft[floor]))
        else :
            print("Floor is not available")
            LOGFILE.write(f"{datetime.now()} -- Floor is not available \n")

    def on_button_click(self, button_number):
        RGB_android_cabin_dataC[4] = button_number
        print(f"Button {button_number} clicked!")
        LOGFILE.write(f"{datetime.now()} -- Button {button_number} clicked! \n")

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

        print(f"{button_name} toggled {'ON' if checked else 'OFF'} ")
        LOGFILE.write(f"{datetime.now()} -- {button_name} toggled {'ON' if checked else 'OFF'} \n")
        self.sender().setStyleSheet(f"background-color: {color}; color: white; border-radius: 8px; padding: 8px;font-weight: bold; ")

    def on_slider_change(self, slider_name, value):
        
        print(f"{slider_name} slider set to {value}")
        LOGFILE.write(f"{datetime.now()} -- {slider_name} slider set to {value} \n")

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
            LOGFILE.write(str(f"{datetime.now()} -- Connecting to shaft at {addr[0]}  \n"))
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5151), "shaft")).start()
        elif data[0] == 0xde and data[1] == 0x02 and not cabin_connectivity_flag:
            print("Connecting to cabin at ", addr[0])
           # LOGFILE.write(f"Buttons {num} clicked!")
            LOGFILE.write(str(f"{datetime.now()} -- Connecting to cabin at {addr[0]}  \n"))
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5050), "cabin")).start()

def sendDataToCabin():
    global cabin_connectivity_flag,wifi_cabin
    while(cabin_connectivity_flag):
        #print("sending cabin data",RGB_android_cabin_dataC)
        if wifi_cabin != None:
            wifi_cabin.send(LL_android_cabin_data)
            wifi_cabin.send(RGB_android_cabin_dataC)
            wifi_cabin.send(FanDatatoCab)
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
window2 = LiftControlUI()
window2.setStyleSheet("background-color: #222831;")
window2.show()
sys.exit(app.exec())


        