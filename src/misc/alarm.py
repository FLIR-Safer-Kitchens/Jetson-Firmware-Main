"""Class for interacting with alarm board MCU"""

from serial import Serial, SerialException, SerialTimeoutException
import serial.tools.list_ports
from constants import *
import logging
import time


class AlarmBoard:
    """Class for managing serial communication with the alarm board microcontroller"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)


    def __send_cmd(self, cmd: str):
        """
        Send a command to the alarm board.

        Parameters:
        - cmd (str): the command to send

        Returns (bool): True if the message was transmitted successfully
        """
        try:
            # Encode message string to bytes
            cmd_bytes = cmd.encode('utf-8')
            self.logger.debug(f"Transmitting: {cmd_bytes}")
            
            # Transmit message
            ret = self.ser.write(cmd_bytes)
            assert ret == len(cmd_bytes)
            return True

        # Return False if transmission failed
        except (UnicodeEncodeError, SerialException, SerialTimeoutException, AssertionError):
            self.logger.exception("Failed to send command:")
            return False


    def __read_str(self):
        """
        Receive data from the alarm board.

        Returns (str): Decoded message or empty string on error/no data available
        """
        try: 
            # Get raw bytes and return decoded string
            recv = self.ser.readline()
            self.logger.debug(f"Received: {recv}")
            return recv.decode().strip() if recv != None else ""
        
        # Return empty string on error
        except (SerialException, SerialTimeoutException, UnicodeDecodeError):
            self.logger.exception("Serial read failed:")
            return ""


    def connect(self):
        """Connect to the AVR microcontroller"""
        # Close any existing connections
        self.disconnect()

        for retry in range(AVR_CONNECTION_RETRIES):
            # Find the first device matching the
            # USB vendor/product ID
            com_ports = serial.tools.list_ports.comports()
            for device in com_ports:
                if (device.vid == AVR_USB_VID) and (device.pid == AVR_USB_PID):
                    port = device.device
                    break
            
            # Re-attempt connection
            else: 
                self.logger.warning(
                    f"Failed to find microcontroller. \
                    Retry: ({retry+1}/{AVR_CONNECTION_RETRIES})"
                )
                time.sleep(AVR_RETRY_COOLDOWN)
                continue
            
            # Microcontroller found
            self.logger.info("Found microcontroller")
            break

        # Microcontroller could not be found
        else: assert False, "Microcontroller not found"

        # Establish the serial connection
        self.ser = Serial(
            port=port,
            baudrate=AVR_BAUD_RATE,
            timeout=AVR_TIMEOUT,
            write_timeout=AVR_TIMEOUT
        )


    def disconnect(self):
        """Close the serial connection to the MCU"""
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()


    def startAlarm(self):
        """Activate the alarm"""
        return self.__send_cmd("start\n")


    def stopAlarm(self):
        """Deactivate the alarm"""
        return self.__send_cmd("alarmoff\n")
