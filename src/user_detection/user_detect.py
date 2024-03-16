"""User detection launcher"""

from .user_detect_worker import user_detect_worker
from  multiprocessing import Value
from  launcher import Launcher
import logging


class UserDetect(Launcher):
    """Class for managing the user detection worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Epoch time of last detection
        self.last_detected = Value('d', 0.0)


    def start(self, vis_mem, vis_lock, frame_event):
        """
        Start the user detection worker

        Parameters:
        - vis_mem (multiprocessing.shared_memory): Shared memory location of visible camera data
        - vis_lock (multiprocessing.Lock): Lock object for shared memory location
        """
        
        super().start(
            target=user_detect_worker,
            args=(
                vis_mem,
                vis_lock, 
                frame_event,
                self.suspend_sig,
                self.exception_queue,
                self.last_detected
            )
         )
