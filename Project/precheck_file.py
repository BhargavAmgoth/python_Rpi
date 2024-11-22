

from common import wifi_cabin, wifi_shaft, LL_android_cabin_data, RGB_android_cabin_dataC, FanDatatoCab
import time 

def start_precheck():
    global precheck 
    precheck = True
    siren()

#Pre check all device
def siren():
    global cabin_to_tab
    data = cabin_to_tab
    data[2] = 0x01
    current_time = 0
    siran_on = False
    start_time = time.time()
    timeout = 10
    while not siran_on:
        current_time = time.time()
        # Check if timeout is reached
        if current_time - start_time <= timeout:
            wifi_shaft.send(data)
        else :
            data[2] = 0x0
            wifi_shaft.send(data)
            siran_on = True 
    cabin_Landin_lever_toggle()
    

def cabin_Landin_lever_toggle():
    global LL_android_cabin_data
    data = LL_android_cabin_data
    for i in range(5):
        data[4] = 0x01
        wifi_cabin.send(data)
        time.sleep(10)
        data[4] = 0x00
        wifi_cabin.send(data)
    rgb_controll()

def rgb_controll():
    global RGB_android_cabin_dataC
    data = RGB_android_cabin_dataC
    data[2] = 0x10   # timer 
    data[3] = 50     # PWM -> Brightness
    for i in range(12):
        data[4] = i # color
        wifi_cabin.send(data)
        time.sleep(3)
    for i in range(100):
        data[4] = i     # PWM -> Brightness
        wifi_cabin.send(data)
        time.sleep(3)
    fan_conroll()

def fan_conroll():
    global FanDatatoCab, precheck
    data = FanDatatoCab
    data[2] = 0x10   # timer 
    data[3] = 50     # PWM -> speed
    for i in range(100):
        data[3] = i     # PWM -> Brightness
        wifi_cabin.send(data)
        time.sleep(3)
    precheck = False