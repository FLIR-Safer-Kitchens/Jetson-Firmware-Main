"""Class for interacting with alarm board MCU"""

import logging


class AlarmBoard:
    """Class for managing serial communication with the alarm board microcontroller"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        self.logger.warning("I'M JUST A STUB!")


    def __send_cmd(self, cmd: str):
        """
        Send a command to the alarm board\n
        Parameters:
        - cmd (str): the command to send

        Returns (bool): True if the message was transmitted successfully
        """
        return True


    def __read_str(self):
        """
        Receive data from the alarm board.
        Returns (str): Decoded message or empty string on error/no data available
        """
        return ""


    def connect(self):
        """Connect to the AVR microcontroller"""
        self.logger.info("Connected to AVR")


    def disconnect(self):
        """Close the serial connection to the MCU"""
        self.logger.info("Disconnected from AVR")


    def startAlarm(self):
        """Activate the alarm"""
        self.logger.info("Starting alarm")
        return self.__send_cmd("start\n")


    def stopAlarm(self):
        """Deactivate the alarm"""
        self.logger.info("Stopping alarm")
        return self.__send_cmd("stop\n")
