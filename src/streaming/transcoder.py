"""Transcoder launcher"""

from .transcoder_worker import transcoder_worker
from  misc.launcher import Launcher
import logging


class Transcoder(Launcher):
    """Class for managing the process that generates a colorized HLS stream from raw thermal frames"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)


    def start(self, raw16_mem, raw16_lock, frame_event, log_queue):
        """
        Start the transcoder worker

        Parameters:
        - vis_mem (multiprocessing.shared_memory): Shared memory location of visible camera data
        - vis_lock (multiprocessing.Lock): Lock object for shared memory location
        - frame_event (multiprocessing.Event): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        
        super().start(
            target=transcoder_worker,
            args=(
                raw16_mem,
                raw16_lock, 
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue
            )
         )
