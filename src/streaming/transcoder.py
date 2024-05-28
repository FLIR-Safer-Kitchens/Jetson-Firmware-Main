"""Transcoder launcher"""

from constants import HLS_DIRECTORY, HLS_M3U8_FILENAME
from .transcoder_worker import transcoder_worker
from  misc.launcher import Launcher
import logging
import os


class Transcoder(Launcher):
    """Class for managing the process that generates a colorized HLS stream from raw thermal frames"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Compute .m3u8 directory to give to node server
        module_path = os.path.dirname(__file__)
        self.m3u8_path = os.path.join(module_path, HLS_DIRECTORY, HLS_M3U8_FILENAME)
        self.m3u8_path = os.path.normpath(self.m3u8_path)


    def start(self, raw16_mem, frame_event, log_queue):
        """
        Start the transcoder worker

        Parameters:
        - vis_mem (multiprocessing.Array): Shared memory location of visible camera data
        - frame_event (NewFrameConsumer): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        
        super().start(
            target=transcoder_worker,
            args=(
                raw16_mem,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue
            )
         )
