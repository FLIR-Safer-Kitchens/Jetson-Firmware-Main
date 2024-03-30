"""Parent class for launching worker processes"""

from multiprocessing import Process, Event, get_context
import multiprocessing.queues
from queue import Full, Empty
import threading
import logging


class Launcher:
    """Class for managing worker processes"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Process object of worker
        self.worker_proc = None
        
        # Queue to dump exceptions if worker dies
        self.exception_queue = ExceptionQueue(5)

        # Signal to shut down worker
        self.suspend_sig = Event()


    def running(self):
        """Returns (bool): True if worker process is running"""
        return isinstance(self.worker_proc, Process) and self.worker_proc.is_alive() 


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
        # Process not running (or never created)
        if not self.running():
            return self.exception_queue.to_list()

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
        return self.exception_queue.to_list()


class ExceptionQueue(multiprocessing.queues.Queue):
    """
    Wrapper for multiprocessing Queue\n
    Gracefully handles puts to full Queue
    """
    def __init__(self, maxsize: int = 0) -> None:
        super().__init__(maxsize, ctx=get_context())

    def put(self, obj, block = True, timeout = None):
        # Attempt put
        try: super().put(obj, block, timeout)
        except Full:
            try:
                err = super().get_nowait() # Remove an item
                print(f"Exception queue overflowed. Removed item: {err}")
            except Empty: pass
            
            # Retry put
            # Do not raise exceptions
            try: super().put(obj, block, timeout)
            except: print("Failed to add item to exception queue")
    
    def to_list(self):
        """
        Pop all queue items and return them as a list\n
        Notes: This method is dumb; don't let other processes modify the queue while this is running
        """
        out = []
        while not super().empty():
            out.append(super().get_nowait())

        return out
