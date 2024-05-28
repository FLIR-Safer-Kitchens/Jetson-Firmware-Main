"""Cooking detection launcher"""

from .cooking_detect_worker import cooking_detect_worker
from multiprocessing import Manager
from misc.launcher import Launcher
import logging


class CookingDetect(Launcher):
    """Class for managing the cooking detection worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Detection flags
        self.cooking_coords = Manager().list()


    def start(self, raw16_mem, frame_event, log_queue):
        """
        Start the cooking detection worker

        Parameters:
        - raw16_mem (multiprocessing.Array): Shared memory location of raw16 frame data
        - frame_event (NewFrameConsumer): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        
        super().start(
            target=cooking_detect_worker,
            args=(
                raw16_mem,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue,
                self.cooking_coords
            )
        )
