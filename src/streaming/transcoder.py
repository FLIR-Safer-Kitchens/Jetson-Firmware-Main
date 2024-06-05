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


    def start(self, stream_type, mem, frame_event, log_queue):
        """
        Start the transcoder worker

        Parameters:
        - stream_type (str): The type of stream, either "thermal" or "visible" (check constants.py)
        - mem (multiprocessing.Array): Shared memory location of image data
        - frame_event (NewFrameConsumer): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        
        super().start(
            target=transcoder_worker,
            args=(
                stream_type,
                mem,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue
            )
         )
