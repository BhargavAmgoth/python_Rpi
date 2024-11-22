import sys
import threading
import socket
import struct
import numpy as np
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,QDialog,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout, QBoxLayout, QCheckBox, QMessageBox, QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtProperty, QPropertyAnimation, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QColor, QPainter, QBrush, QIntValidator, QDoubleValidator,QFont
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
automation_start = None 
MAX_Floor = 2


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
prev_error_data = ""
prev_shaft_broad_cast = [] #used to store the previous error state of the Shaft broad cst
lidar_data = "" #contain the lidar value


cabi_ip_add = None
shaft_ip_add = None