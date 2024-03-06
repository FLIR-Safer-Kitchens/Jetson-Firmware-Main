# User detection algorithm

from user_detection.user_detect_worker import user_detect_worker
from multiprocessing import Process, Queue, Event, Value
import logging


# Create Logger
logger = logging.getLogger(__name__)

class UserDetect:
    """Class for managing the user detection worker"""

    def __init__(self):
        self.worker_proc = None

        # Epoch time of last detection
        self.last_detected = Value('d', 0.0)


    def running(self):
        """Returns (bool): True if worker process is running"""
        return (type(self.worker_proc) == Process) and self.worker_proc.is_alive()


    def start(self, vis_mem, vis_lock):
        """
        Start the user detection worker

        Parameters:
        - vis_mem (multiprocessing.shared_memory): Shared memory location of visible camera data
        - vis_lock (multiprocessing.Lock): Lock object for shared memory location
        """
        
        # Check running process
        if self.running(): 
            logger.warning("The worker is already running")
            return

        # Create queue to dump exceptions if worker dies
        self.exception_queue = Queue()

        # Create signal to shut down worker
        self.suspend_sig = Event()

        # Create & start worker process
        self.worker_proc = Process(
            target=user_detect_worker, 
            args=(
                vis_mem, 
                vis_lock, 
                self.suspend_sig, 
                self.exception_queue,
                self.last_detected
            )
        )
        self.worker_proc.start()


    def stop(self):
        """
        Shut down the worker
        
        Returns (list): List of exception objects

        Notes: Will block for a while if process is hung
        """

        # Attempt clean shutdown
        self.suspend_sig.set()
        self.worker_proc.join(timeout=2)

        # Attempt termination
        if self.running():
            logger.warning("Worker did not respond to suspend signal. Terminating...")
            self.worker_proc.terminate()
            self.worker_proc.join(timeout=2)

            # Forcefully kill process
            if self.running():
                logger.error("Worker did not terminate. Killing...")
                self.worker_proc.kill()

        # Dump Exceptions
        if not hasattr(self, "exception_queue"): return []
        
        errs = []
        while not self.exception_queue.empty():
            errs.append(self.exception_queue.get(True))
            logger.exception("Worker raised an exception", exc_info=errs[-1])
        
        return errs
