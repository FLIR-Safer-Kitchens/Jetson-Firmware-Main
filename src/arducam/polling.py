"""Arducam polling launcher"""

from .polling_worker import polling_worker
from misc.launcher import Launcher
import logging


class Arducam(Launcher):
    """Class for managing the arducam polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)


    def start(self, vis_mem, frame_event, log_queue):
        """
        Start the arducam polling worker

        Parameters:
        - vis_mem (multiprocessing.Array): Shared memory location of visible camera data
        - frame_event (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
        - log_queue (multiprocessing.Queue): Queue to handle log messages
        """

        super().start(
            target=polling_worker,
            args=(
                vis_mem,
                frame_event,
                self.suspend_sig,
                log_queue,
                self.exception_queue
            )
         )
