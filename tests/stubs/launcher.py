"""Parent class for launching worker processes"""

from multiprocessing import Manager
import logging


class Launcher:
    """Class for managing worker processes"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # UDP ports to stream image data to
        # Used for debugging and livestreaming
        self.streaming_ports = Manager().list()

        # Fake variables
        self.running_val = False


    def running(self):
        """Returns (bool): True if worker process is running"""
        return self.running_val
    

    def handle_exceptions(self):
        """
        If the process dies unexpectedly, call this function to determine if the error is fatal\n
        Returns (bool): False for fatal error, or too many errors in a given period

        Note: Child classes of Launcher should set their own exception whitelist
        """
        self.stop()
        self.logger.info("Handled exceptions")
        return True


    def start(self, target, args):
        """
        Start the  worker

        Parameters:
        - target (method): Worker process function
        - args (tuple): Arguments to pass to target

        Notes: Suspend signal and exception queue are not passed automatically
        """
        self.logger.info("Started worker")
        self.running_val = True


    def stop(self):
        """
        Shut down the worker\n
        Notes: Will block for a while if process is hung
        """
        self.logger.info("Stopped worker")
        self.running_val = False
