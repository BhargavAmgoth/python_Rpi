import sys
import threading
import socket
import struct

from PyQt6.QtCore import pyqtSignal

import websocket
from datetime import datetime
import time


from gui import LiftControlUI 



from common import (wifi_cabin, wifi_shaft, shaft_broad_cast, LL_android_cabin_data, cabin_to_shaft,wifi_cabin, wifi_shaft, automation_start, MAX_Floor,
                    RGB_android_cabin_dataC, FanDatatoCab, shaft_broad_cast, cabin_to_tab, prev_err_state, prev_error_data, prev_shaft_broad_cast, lidar_data, 
                    lops_shaft, MCAST_PORT, MCAST_GRP, cabi_ip_add, shaft_ip_add, shaft_connectivity_flag, cabin_connectivity_flag
)

from log_file import LOGFILE




# Function to format WebSocket URL
def get_ip(ip, port):
    global cabi_ip_add, shaft_ip_add
    if(port == 5151):
        shaft_ip_add = f"ws://{ip}:{port}/ws"
    elif(port == 505):
        cabi_ip_add = f"ws://{ip}:{port}/ws"
        
    return f"ws://{ip}:{port}/ws"

# Call booking logic
def call_booking(call_type, floor_number):
    
    LOGFILE.write(f"{datetime.now()} -- In UI {call_type} Call for floor {floor_number} \n")
    
    if call_type == "LOP":
        data = lops_shaft
        for floor in range(len(data)):
            if floor == floor_number :
                data[floor][2] = 0x01  # Set the specific floor call active
                #data[floor][6] = 0x01  # Set the specific floor ml enguage
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
             
        if 0 <= floor_number <= len(lops_shaft)+1 :
            data2 = cabin_to_tab
            data2[1] = 2 ** floor_number
            print("Updated cabin data: ", " ".join(f"0x{byte:02x}" for byte in data2))
            if(wifi_cabin != None):
                wifi_cabin.send(data2)
                
        else:
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
            #print("Broadcast Cabin INT:", data_received)
            LOGFILE.write(str(f"{datetime.now()} -- Broadcast Cabin INT: {data_received} \n"))
            #print(" ")
        elif client_name == 'shaft':
            global shaft_broad_cast, prev_shaft_broad_cast
            prev_shaft_broad_cast = [hex(bytess) for bytess in message]
            data_received = [int.from_bytes([byte], byteorder='big', signed=True) for byte in message]
            print("Broadcast shaft INT:", shaft_broad_cast)
            LOGFILE.write(str(f"{datetime.now()} -- Broadcast shaft INT: {data_received} \n"))
            if(prev_shaft_broad_cast != shaft_broad_cast):
                shaft_broad_cast = [hex(bytess) for bytess in message]
                #print("In shafrt broadcast updater ", shaft_broad_cast)
                # threading.Thread(target=shaft_brodcast_updater, daemon=True).start()
                shaft_brodcast_updater()
                #shaft_brodcast_updater()
 
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
            threading.Thread(target=sendDataToShaft).start()
            wifi_shaft = ws
        elif client_name == "cabin":
            print("cabin open")
            cabin_connectivity_flag = True
            wifi_cabin = ws
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
    print("The updater  ....................................................",shaft_broad_cast)
    LiftControlUI.check_update_brodcast_error(shaft_broad_cast)
    LiftControlUI.update_lidar_data(shaft_broad_cast[5], shaft_broad_cast[1])
    LiftControlUI.change_data(shaft_broad_cast)
    #return shaft_broad_cast

# Start UDP listener and WebSocket in separate threads
def udp_to_websocket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', MCAST_PORT))

    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        data, addr = sock.recvfrom(1024)  # Buffer size of 1024 bytes
        #print("DATA UDP ", " ".join(f"0x{byte:02x}" for byte in data))
        if data[0] == 0xde and data[1] == 0x01 and not shaft_connectivity_flag:
            print("Connecting to shaft at ", addr[0],  data)
            LOGFILE.write(str(f"{datetime.now()} -- Connecting to shaft at {addr[0]}  \n"))
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5151), "shaft"), daemon=True).start()
        elif data[0] == 0xde and data[1] == 0x02 and not cabin_connectivity_flag:
            print("Connecting to cabin at ", addr[0])
           # LOGFILE.write(f"Buttons {num} clicked!")
            # LOGFILE.write(str(f"{datetime.now()} -- Connecting to cabin at {addr[0]}  \n"))
            threading.Thread(target=run_websocket_client, args=(get_ip(addr[0], 5050), "cabin"), daemon=True).start()

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
                #wifi_shaft.send(lops_shaft[lop])
            #wifi_shaft.send(cabin_to_tab) 
                pass   
        time.sleep(0.4)        
