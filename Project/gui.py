import threading
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QDialog,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout, QBoxLayout, QCheckBox, QMessageBox, QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtProperty, QPropertyAnimation, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QPainter, QBrush, QIntValidator, QDoubleValidator,QFont
import os
from datetime import datetime

from Automation_file import run_automation
from log_file import LOGFILE
from common import shaft_broad_cast, lidar_data


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
    
        Error_panel = self.create_error_panel()
        automation_panel = self.automation_input_panel()
        self.Data_panel = self.create_data_panel(shaft_broad_cast)
     
        main_layout.addWidget(Error_panel)
        main_layout.addWidget(automation_panel)

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

    def automation_input_panel(self):
        # Create a group box for the input panel
        input_box = QGroupBox("Input Panel")
        input_layout = QVBoxLayout()

        # Form layout with labeled fields
        self.source_floor = QLineEdit()
        self.source_floor.setValidator(QIntValidator())
        self.destination_floor = QLineEdit()
        self.destination_floor.setValidator(QIntValidator()) 
        self.no_of_times = QLineEdit()
        self.no_of_times.setValidator(QIntValidator())
        self.error_through = QLineEdit()
        

        form_layout = QFormLayout()
        form_layout.addRow("source floor:", self.source_floor)
        form_layout.addRow("Destination Floor:", self.destination_floor)
        form_layout.addRow("No of Times:", self.no_of_times)
        form_layout.addRow("Error Through:", self.error_through)
        
        
        input_layout.addLayout(form_layout)
        

        # Add a button to print the inputs
        display_button = QPushButton("Start Automation")
        display_button.clicked.connect(self.print_inputs)
        display_button.setStyleSheet(self.automation_panel_style())#(f"background-color: red; color: white;")
        input_layout.addWidget(display_button)

        input_box.setLayout(input_layout)
        input_box.setStyleSheet(self.automation_panel_style())
        return input_box

    def print_inputs(self):
        source_floor = self.source_floor.text()
        destination_floor = self.destination_floor.text()
        no_of_times = self.no_of_times.text()
        error_through = self.error_through.text()
        msg = QMessageBox(self)
        if destination_floor or no_of_times or error_through :
            # Print the inputs to the console
            print("Form Inputs:")
            print(f"Destination Floor: {source_floor}")
            print(f"Destination Floor: {destination_floor}")
            print(f"No of Times: {no_of_times}")
            print(f"Error Through: {error_through}")
            #print(f"Hobbies: {hobbies}")

            # Show a styled message box with the inputs
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle("Collected Inputs")
            msg.setText("Here are your form inputs:")
            floor = destination_floor
            # if(destination_floor > "1"):
            #     floor = "call not allow invalid entry floor"
            # else :
            #     floor = destination_floor   
            #     print("call not allow invalid entry floor")
            msg.setInformativeText(
                f"Destination Floor: {floor}\n"
                f"No of Times: {no_of_times}\n"
                f"Error Through: {error_through}\n"
                #f"Hobbies: {hobbies}"
            )
            # Apply the panel style
            msg.setStyleSheet(self.automation_panel_style())
            msg.exec()
            global automation_start 
            automation_start = True

            repetitions = no_of_times  # Number of times to run the automation (can be dynamic)
            automation_thread = threading.Thread(target=run_automation, args=(source_floor, destination_floor, repetitions))
            automation_thread.daemon = True  # Ensures the thread exits when the main program exits
            automation_thread.start()
        
        '''
        else:
            # Show a warning message box if any field is empty
            
            msg.setWindowTitle("Incomplete Form")
            msg.setText("Please fill in all fields!")
            # Apply the panel style
            msg.setStyleSheet(self.automation_panel_style())
            msg.exec()

        '''

    def hide_outer_layout(self, visibility):
            self.toggle_panel_visibility(self.Data_panel, visibility)
            self.toggle_panel_visibility(self.Device_panel, visibility)
            self.toggle_panel_visibility(self.Door_panel, visibility)
            self.toggle_panel_visibility(self.Network_panel, visibility)
            self.toggle_panel_visibility(self.MechLock_panel, visibility)
        
    def toggle_panel_visibility(self, panel, visible):
        panel.setVisible(visible)
            
    def check_update_brodcast_error(self, data):
        #print("Mesagee",data)
        global prev_err_state 

        global prev_error_data
        if len(data) == 16 and data[0] == "0x60" and data[-1] == "0xff": #QPushButton { background-color: green; color: white;font-size: 12px; border-radius: 8px;padding: 8px; }"""
            
            #print(type(data[3]), " " ,data[3])
            '''
            hex_data = data[14]
            cleaned_hex_data = hex_data.replace("0x", "").replace("x", "")
            binary_data = ''.join(format(int(char, 16), '04b') for char in cleaned_hex_data)
            print(f"Hex: {hex_data}")
            print(f"Binary: {binary_data}")
            ''' 
            if prev_error_data !=  data[3] :
                prev_error_data = data[3]
                print("data ...... .. .... . . .. . . ..  ",prev_error_data, data[3])        
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
            grid_layout.addWidget(err_button, type_index // 3, type_index % 3)  # Arrange in a grid (2 columns)
            self.error_buttons[err_name] = err_button
        erroe_box.setLayout(grid_layout)
        erroe_box.setStyleSheet(self.panel_style())
        return erroe_box

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
        #print(label, state)
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
            elif(state == "01"):
                self.Mechanical_lock_toggles[label].set_state(2)
            else:
                self.Mechanical_lock_toggles[label].set_state(state)

    def Update_Device_toggles(self, data, data_type):
       
        if data_type == "Devices" :
            data.reverse()
            #print("Binary Data Here:",data_type, data)
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
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Door_G : {data[0]} Door_1 : {data[1]} Door_2 : {data[2]} Door_3 : {data[3]} \n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Door G", data[0] == '1')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("Door 1", data[1] == '1')
            self.set_toggle_state("Door 2", data[2] == '1')
            self.set_toggle_state("Door 3", data[3] == '1')
        
        elif data_type == "Door_Lock" :
            data.reverse()
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Solenoid_G : {data[0]} Solenoid_1 : {data[1]} Solenoid_2 : {data[2]} Solenoid_3 : {data[3]} \n")
            # Update toggles based on the incoming data
            self.set_toggle_state("Solenoid G", data[0] == '0')  # Is power device is off = 1 then power is on 
            self.set_toggle_state("Solenoid 1", data[1] == '0')
            self.set_toggle_state("Solenoid 2", data[2] == '1')
            self.set_toggle_state("Solenoid 3", data[3] == '1')
        
        elif data_type == "Network" :
            data.reverse()
            #print("Binary Data Here:",data_type, data)
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
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- Landing Lever : {data} \n")
            self.set_toggle_state("LL", data == '1')  # Is power device is off = 1 then power is on

        elif data_type == "EVO" :
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- EVO : {data} \n")
            self.set_toggle_state("EVO", data == '1')  # Is power device is off = 1 then power is on 
        
        elif data_type == "SOS" :
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- SOS : {data} \n")
            self.set_toggle_state("SOS", data == '1')  # Is power device is off = 1 then power is on 

        elif data_type == "ML" :
            #data = ['0', '0', '1', '1', '0', '1', '1', '1']
            #print("Binary Data HereFGDGDGDG:",data_type, data)
            data.reverse()
            #print("Binary Data Here:",data_type, data)
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
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- LOP Booked : {data} \n")
            self.set_toggle_state("LOP Booked", data != '0')

        elif data_type == "COP Booked" :
            #print("Binary Data Here:",data_type, data)
            LOGFILE.write(str(f"{datetime.now()} -- {data_type} Binary Data Here: {data} \n"))
            LOGFILE.write(f"{datetime.now()} -- COP Booked : {data} \n")
            self.set_toggle_state("COP Booked", data != '0')

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

    def automation_panel_style(self):
        return """
        QGroupBox {
            background-color: #393E46; 
            border: 2px solid #00ADB5;
            border-radius: 8px;
            margin-top: 8px;
            padding: 8px;
            font-family: Arial, sans-serif;
            font-size: 10px;
            color: #ffffff; /* Navy text color for title */
        } 
        QLabel {
            background-color: #393E46;
            color: white; /* Rich blue label text */
            font-weight: bold;
            
        }
        QLineEdit {
            background-color: #ffffff; 
            border: 2px solid blue; 
            border-radius: 6px;
            padding: 9px;
            font-family: Arial, sans-serif;
            font-size: 10px;
            
        }
        QPushButton {
            background-color: #007acc; 
            color: #ffffff; 
            border-radius: 8px;
            padding: 8px 16px;
            font-family: Arial, sans-serif;
            font-size: 14px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #005fa3; 
        }
        QPushButton:pressed {
            background-color: #004a82; 
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
