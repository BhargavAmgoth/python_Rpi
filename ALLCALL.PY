import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

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

        # Create buttons for LOP Panel
        lop_buttons = [
            "Ground Floor Button", "First Floor Button", "Second Floor Button",
            "Third Floor Button", "Solenoid Button",
            "Door Switch Button", "Mechanical Lock", "Mechanical Semi"
        ]
        
        for btn_text in lop_buttons:
            button = QPushButton(btn_text)
            button.setStyleSheet(self.toggle_button_style())
            button.setCheckable(True)
            button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(btn, checked))
            lop_layout.addWidget(button)

        lop_box.setLayout(lop_layout)
        lop_box.setStyleSheet(self.panel_style())
        return lop_box

    def create_cop_panel(self):
        # Create a group box for the COP Panel
        cop_box = QGroupBox("COP PANEL")
        cop_layout = QVBoxLayout()

        # Create buttons for COP Panel
        cop_buttons = [
            "Ground Floor Button", "First Floor Button", "Second Floor Button",
            "Third Floor Button", "Landing Lever ", 
            "Child Lock ", "Emergency ", "Light ", "Fan " 
        ]

        for btn_text in cop_buttons:
            button = QPushButton(btn_text)
            button.setStyleSheet(self.toggle_button_style())
            button.setCheckable(True)
            button.toggled.connect(lambda checked, btn=btn_text: self.on_toggle_button(btn, checked))
            cop_layout.addWidget(button)

        # Add sliders for light and fan control with labels
        light_label = QLabel("Light Control")
        light_slider = QSlider(Qt.Orientation.Horizontal)
        light_slider.setRange(0, 100)
        light_slider.setValue(50)
        light_slider.valueChanged.connect(lambda value: self.on_slider_change("Light", value))

        fan_label = QLabel("Fan Control")
        fan_slider = QSlider(Qt.Orientation.Horizontal)
        fan_slider.setRange(0, 100)
        fan_slider.setValue(50)
        fan_slider.valueChanged.connect(lambda value: self.on_slider_change("Fan", value))

        cop_layout.addWidget(light_label)
        cop_layout.addWidget(light_slider)
        cop_layout.addWidget(fan_label)
        cop_layout.addWidget(fan_slider)

        cop_box.setLayout(cop_layout)
        cop_box.setStyleSheet(self.panel_style())
        return cop_box

    def on_toggle_button(self, button_name, checked):
        color = "green" if checked else "red"
        if button_name == "Mechanical Lock" :
            print(checked)
            
        print(f"{button_name} toggled {'ON' if checked else 'OFF'}")
        self.sender().setStyleSheet(f"background-color: {color}; color: white; border-radius: 10px; padding: 10px;")

    def on_slider_change(self, slider_name, value):
        print(f"{slider_name} slider set to {value}")

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LiftControlUI()
    window.setStyleSheet("background-color: #222831;")
    window.show()
    sys.exit(app.exec())
