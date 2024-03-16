"""User detection launcher"""

from .polling_worker import polling_worker
from launcher import Launcher
import logging


class Arducam(Launcher):
    """Class for managing the arducam polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)


    def start(self, vis_mem, vis_lock, frame_event):
        """
        Start the arducam polling worker

        Parameters:
        - vis_mem (multiprocessing.shared_memory): Shared memory location of visible camera data
        - vis_lock (multiprocessing.Lock): Lock object for shared memory location
        """
        
        super().start(
            target=polling_worker,
            args=(
                vis_mem,
                vis_lock,
                frame_event,
                self.suspend_sig,
                self.exception_queue
            )
         )
