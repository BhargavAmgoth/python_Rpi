
from datetime import datetime
import time
import os


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
