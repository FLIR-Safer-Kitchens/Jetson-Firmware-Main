"""PureThermal polling launcher"""

from .polling_worker import polling_worker
from multiprocessing import Value
from ctypes import c_double
from misc import Launcher
import logging


class PureThermal(Launcher):
    """Class for managing the PureThermal Lepton polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        
        # Maximum detected temperature
        self.max_temp = Value(c_double, 0.0)


    def start(self, raw16_mem, raw16_lock, frame_event, log_queue):
        """
        Start the PureThermal polling worker

        Parameters:
        - raw16_mem (multiprocessing.shared_memory): Shared memory location of thermal camera data
        - raw16_lock (multiprocessing.Lock): Lock object for shared memory location
        - frame_event (BroadcastEvent): Master 'new frame' event. Set all child events when a new frame is written
        - log_queue (multiprocessing.Queue): Queue to handle log messages
        """
        
        super().start(
            target=polling_worker,
            args=(
                raw16_mem,
                raw16_lock,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue,
                self.max_temp
            )
         )
