import sys
import threading
import numpy as np
from PyQt6.QtWidgets import (
    QApplication,
)

import os

from network import udp_to_websocket
from Automation_file import run_automation
from gui import LiftControlUI

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