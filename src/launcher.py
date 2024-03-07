# Parent class for launching detection workers

from multiprocessing import Process, Queue, Event
import logging


class Launcher:
    """Class for managing detection workers"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Process object of worker
        self.worker_proc = None
        
        # Queue to dump exceptions if worker dies
        self.exception_queue = Queue()

        # Signal to shut down worker
        self.suspend_sig = Event()


    def running(self):
        """Returns (bool): True if worker process is running"""
        return (type(self.worker_proc) == Process) and self.worker_proc.is_alive()


    def start(self, target, args):
        """
        Start the  worker

        Parameters:
        - target (method): Worker process function
        - args (tuple): Arguments to pass to target

        Notes: Suspend signal and exception queue are not passed automatically
        """
        
        # Check running process
        if self.running(): 
            self.logger.warning("The worker is already running")
            return
        
        # Reset suspend signal
        self.suspend_sig.clear()

        # Create & start worker process
        self.worker_proc = Process(target=target, args=args)
        self.worker_proc.start()


    def stop(self):
        """
        Shut down the worker
        
        Returns (list): List of exception objects

        Notes: Will block for a while if process is hung
        """
        # Process never started
        if self.worker_proc == None: return []

        # Attempt clean shutdown
        self.suspend_sig.set()
        self.worker_proc.join(timeout=2)

        # Attempt termination
        if self.running():
            self.logger.warning("Worker did not respond to suspend signal. Terminating...")
            self.worker_proc.terminate()
            self.worker_proc.join(timeout=2)

            # Forcefully kill process
            if self.running():
                self.logger.error("Worker did not terminate. Killing...")
                self.worker_proc.kill()

        # Dump Exceptions
        errs = []
        while not self.exception_queue.empty():
            errs.append(self.exception_queue.get(True))
            self.logger.exception("Worker raised an exception", exc_info=errs[-1])
        
        return errs
