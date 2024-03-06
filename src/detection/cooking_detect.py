# Cooking detection launcher

from detection.cooking_detect_worker import cooking_detect_worker
from detection.launcher import Detection
from multiprocessing import Value
import logging


class CookingDetect(Detection):
    """Class for managing the cooking detection worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # Detection flags
        self.hotspot_detected = Value('B', False)
        self.cooking_detected = Value('B', False)
        

    def start(self, raw16_mem, mem_lock):
        """
        Start the cooking detection worker

        Parameters:
        - raw16_mem (multiprocessing.shared_memory): Shared memory location of raw16 frame data
        - mem_lock (multiprocessing.Lock): Lock object for shared memory location
        """
        
        super().start(
            target=cooking_detect_worker,
            args=(
                raw16_mem,
                mem_lock,
                self.suspend_sig,
                self.exception_queue,
                self.hotspot_detected,
                self.cooking_detected
            )
        )
