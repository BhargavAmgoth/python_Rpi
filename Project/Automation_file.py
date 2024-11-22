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

from common import (wifi_cabin, wifi_shaft, shaft_broad_cast, automation_start)
#from network import call_booking
from network import call_booking

def run_automation(source_floor, destination_floor, no_of_times):
    global automation_start
    #print("run_automation thereads :",threading.active_count())
    while(automation_start):
        if(wifi_cabin and wifi_shaft):
            check_current_floor_and_input_floor(source_floor, destination_floor,no_of_times )
        else :
            print("Wait for communication stop automation")
            automation_start = False
        time.sleep(10)

def check_current_floor_and_input_floor(source_floor, destination_floor, no_of_times):
    current_floor = shaft_broad_cast[1]
    current_floor = current_floor.replace("0x", "").replace("x", "")
    call_allowed = check_call_is_allowed(source_floor, destination_floor, no_of_times)  
    if call_allowed:
        print("current floor : " + current_floor +  " Destination Floor : " + destination_floor + " Source Floor : " + source_floor)
        if(current_floor == (source_floor)):
            print("source_floor floor automation Continue \n")          
            #got_to_destinaton_floor(destination_floor) 
            goto_the_floor(destination_floor)
            cal_state = wait_for_call_confirm(source_floor, destination_floor, no_of_times)
            print("floor cal state ",cal_state)
            if cal_state: 
                print("cal state in check",cal_state)
                wait_to_clear_call(source_floor, destination_floor, no_of_times)
            else : 
                print("source_floor cal state in check",cal_state)
        else:
            print("destination floor automation continue \n")
            #got_to_source_floor_first(source_floor)  
            goto_the_floor(source_floor)
            cal_state = wait_for_call_confirm(source_floor, destination_floor, no_of_times)
            print("floor cal state destination",cal_state)
            if cal_state: 
                wait_to_clear_call(source_floor, destination_floor, no_of_times)
            else : 
                print("destination cal state in check", cal_state)

def check_call_is_allowed(source_floor, destination_floor, no_of_times):       
        #print("Active thereads :",threading.active_count())    
        call_allowed = None
        #print(shaft_broad_cast)
        if shaft_broad_cast[3] == "0xaf" and shaft_broad_cast[2] == "0x0" and shaft_broad_cast[7] == "0x0":
            print("Allow to book call ")      
            call_allowed = True
        elif shaft_broad_cast[3] != "0xaf" or shaft_broad_cast[2] != "0x0" or shaft_broad_cast[7] != "0x0": 
            print("Lift Under Error Not allow to book call ")
            call_allowed = False
        return call_allowed

def goto_the_floor(floor):
    if shaft_broad_cast[3] == "0xaf" and shaft_broad_cast[2] == "0x0" and shaft_broad_cast[7] == "0x0":
        print("Book for the floor", floor)
        call_booking("LOP", int(floor))

def got_to_source_floor_first(source_floor):
    
    if shaft_broad_cast[3] == "0xaf" and shaft_broad_cast[2] == "0x0" and shaft_broad_cast[7] == "0x0":
        print("Firstbook source floor")
        call_booking("LOP", int(source_floor))

def got_to_destinaton_floor(destination_floor):
    
    if shaft_broad_cast[3] == "0xaf" and shaft_broad_cast[2] == "0x0" and shaft_broad_cast[7] == "0x0":
        print("Call Booking to the destination Floor")
        call_booking("LOP", int(destination_floor))


def wait_for_call_confirm(source_floor, destination_floor, no_of_times):
    start_time = time.time()  # Record the start time
    timeout = 5  # Wait for 5 seconds
    call_confirm = False
    while not call_confirm:
        current_time = time.time()
        current_floor = shaft_broad_cast[1]
        msg = ""
        current_floor = current_floor.replace("0x", "").replace("x", "")
        # Check if timeout is reached
        #if current_time - start_time <= timeout:
        if shaft_broad_cast[2] == "0x0" or shaft_broad_cast[6] == "0x0":
            msg = "Waiting for call confirm"
            call_confirm = False
        elif shaft_broad_cast[2] != "0x0" or shaft_broad_cast[6] != "0x0":
            msg = "Call confirm wait to clear"
            call_confirm = True
            break  # Exit loop after handling the condition
        # else :
        #     msg = "Waiting Time out for call confirm" 
        #     break
    print(msg)
    return call_confirm     

def wait_to_clear_call(source_floor, destination_floor, no_of_times):
    print("wait_to_clear_call function")
    start_time = time.time()  # Record the start time
    timeout = 30  # Wait for 30 seconds
    msg = ""
    cal_cleared = False
    while not cal_cleared:
        if (shaft_broad_cast[2] == "0x1" or shaft_broad_cast[6] == "0x1" ):
            pass
        if(shaft_broad_cast[2] != "0x1" or shaft_broad_cast[6] != "0x1"):
                cal_cleared = True
                msg = "Call Cleared"
                break
    print(msg)
    current_floor = shaft_broad_cast[1]
    current_floor = current_floor.replace("0x", "").replace("x", "")
    print("current floor ", current_floor, " ", type(current_floor) )
    print("current floor ", current_floor, " ", type(current_floor) )     
    if current_floor == destination_floor:
        print("Reached to the destination floor : ", current_floor)
    elif current_floor == source_floor:
        print("Reached to the source floor : ", current_floor)
    else:
        print("Reached to the somother floor : ", current_floor)

def wait_for_next_call():
    time.sleep(10)