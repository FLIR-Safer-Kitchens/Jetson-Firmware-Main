"""PureThermal polling launcher"""

from .polling_worker import polling_worker
from ctypes import c_bool, c_double
from misc.launcher import Launcher
from multiprocessing import Value
import logging


class PureThermal(Launcher):
    """Class for managing the PureThermal Lepton polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Maximum detected temperature
        self.max_temp = Value(c_double, 0.0)

        # Flag to indicate when hotspots have been detected
        self.hotspot_detected = Value(c_bool, False) 


    def start(self, raw16_mem, frame_event, log_queue):
        """
        Start the PureThermal polling worker

        Parameters:
        - raw16_mem (multiprocessing.Array): Shared memory location of thermal camera data
        - frame_event (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
        - log_queue (multiprocessing.Queue): Queue to handle log messages
        """
        
        super().start(
            target=polling_worker,
            args=(
                raw16_mem,
                frame_event,
                self.streaming_ports,
                self.suspend_sig,
                log_queue,
                self.exception_queue,
                self.max_temp,
                self.hotspot_detected
            )
         )
