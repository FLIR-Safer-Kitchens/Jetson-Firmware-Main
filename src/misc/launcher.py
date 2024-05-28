"""Parent class for launching worker processes"""

from constants import EXCEPTION_HISTORY_WINDOW, ALLOWABLE_EXCEPTION_COUNT
from multiprocessing import Process, Event, get_context
import multiprocessing.queues
from queue import Full, Empty
import logging
import time


class Launcher:
    """Class for managing worker processes"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Process object of worker
        self.worker_proc = None
        
        # Queue to dump exceptions if worker dies
        self.exception_queue = ExceptionQueue(5)

        # Signal to shut down worker
        self.suspend_sig = Event()

        # Exception recovery
        self.exception_whitelist = [] # List of acceptable errors
        self.exception_history   = [] # Timestamps of recent non-fatal errors
        self.exception_history_window  = EXCEPTION_HISTORY_WINDOW  # See constants.py, provided here to allow overrides
        self.allowable_exception_count = ALLOWABLE_EXCEPTION_COUNT # See constants.py, provided here to allow overrides


    def running(self):
        """Returns (bool): True if worker process is running"""
        return isinstance(self.worker_proc, Process) and self.worker_proc.is_alive() 
    

    def handle_exceptions(self):
        """
        If the process dies unexpectedly, call this function to determine if the error is fatal\n
        Returns (bool): False for fatal error, or too many errors in a given period

        Note: Child classes of Launcher should set their own exception whitelist
        """
        # Make sure the process has stopped
        self.stop()

        # Collect exceptions,
        # will clear exception queue
        exceptions = self.exception_queue.to_list()
        
        # Process exited without errors
        if len(exceptions) == 0:
            self.logger.info("Process exited without exceptions")
            return True

        # Handle fatal errors
        fatal_errs = [err for err in exceptions if type(err) not in self.exception_whitelist]
        if len(fatal_errs):
            err_names = ", ".join([str(type(err)) for err in fatal_errs])
            self.logger.error(f"Got {len(fatal_errs)} fatal error(s): " + err_names)
            for ex in fatal_errs:
                self.logger.exception("", exc_info=ex)
            return False
        
        # Add non-fatal errors to exception history
        # (All errors must be non-fatal if we've made it this far)
        for err in exceptions:
            self.exception_history.append((err.__class__.__name__, time.time()))

        # Prune error history
        keep = lambda x: (time.time() - x[1]) <= self.exception_history_window
        self.exception_history = [h for h in self.exception_history if keep(h)]

        # Handle the case where too many exceptions are encountered within the established time window
        if len(self.exception_history) > self.allowable_exception_count:
            err_types = [h[0] for h in self.exception_history]
            err_counts = dict()
            for err in err_types:
                if err not in err_counts: err_counts[err] = 1
                else: err_counts[err] += 1 
            err_summary = "\n\t".join([f"{k}, {v}" for k, v in err_counts.items()])
            self.logger.error("Process encountered too many errors.\nError summary: (type, count)\n\t"+err_summary)
            return False
        
        return True


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
        Shut down the worker\n
        Notes: Will block for a while if process is hung
        """
        # Process not running (or never created)
        if not self.running():
            return

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
