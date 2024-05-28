"""User detection launcher"""

from .user_detect_worker import user_detect_worker
from  misc.launcher import Launcher
from  multiprocessing import Value
from ctypes import c_double
import logging


class UserDetect(Launcher):
    """Class for managing the user detection worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Epoch time of last detection
        self.last_detected = Value(c_double, 0.0)


    def start(self, vis_mem, frame_event, log_queue):
        """
        Start the user detection worker

        Parameters:
        - vis_mem (multiprocessing.Array): Shared memory location of visible camera data
        - frame_event (NewFrameConsumer): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        
        super().start(
            target=user_detect_worker,
            args=(
                vis_mem,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue,
                self.last_detected
            )
         )
