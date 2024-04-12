"""Class for interacting with alarm board MCU"""

import serial

class AlarmBoard:
    # Initialize the serial connection
    def __init__(self):
        pass
    
    # Send a command to the alarm board
    def __send_cmd(self, cmd):
        pass
    
    # Receive data from the alarm board
    def __read_str(self):
        pass

    # === Public Methods ===
    # Activate the alarm
    def startAlarm(self):
        pass
    
    # Deactivate the alarm
    def stopAlarm(self):
        pass
