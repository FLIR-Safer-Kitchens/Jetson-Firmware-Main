"""Random classes and methods to assist with logging"""

from logging.handlers import QueueHandler
from threading import Thread, Event
from logging import LogRecord
from queue import Full, Empty
import logging
import time
import sys


class SizeLimitedQueueHandler(QueueHandler):
    """
    Wrapper for logging.handlers.QueueHandler\n
    Gracefully handles puts to full Queue
    """
    def emit(self, record: LogRecord) -> None:
        for _ in range(10):
            # Attempt to add item to queue
            try: super().emit(record)
            except Full:
                try:
                    # Remove item
                    popped = self.queue.get(block=True, timeout=0.1)
                    print(f"Logging queue overflowed. Deleting record: {popped}")
                except Empty: pass
            else: break

    def handleError(self, record: LogRecord) -> None:
        # Raise exceptions for full/empty queue
        if type(sys.exc_info()[0]) in {type(Full), type(Empty)}:
            raise

        # Don't raise other exceptions
        else: super().handleError(record)



def configure_subprocess(queue, loglevel=logging.DEBUG):
    """
    Called from within a subprocess to initialize logs

    Parameters:
    - queue (multiprocessing.Queue): Queue to transfer log records from a subrocess to the main process
    - loglevel (int): The root log level for the subprocess. Defaults to DEBUG
    """

    # Set root log level (for this process)
    root = logging.getLogger()
    root.setLevel(loglevel)

    # Add handler to root logger
    # Feeds all log messages to queue
    handler = SizeLimitedQueueHandler(queue)
    root.handlers = [handler]



def configure_main(to_file=True, to_term=True):
    """
    Configure the logger for the main process
    
    Parameters:
    - to_file (bool): If true, route log records to a log file
    - to_term (bool): If true, route log records to terminal (stdout)
    """
    
    # Get logger
    root = logging.getLogger()

    # Create file handler
    if to_file:
        fh = logging.FileHandler("output.log")
        fh.setLevel(logging.DEBUG)
        ff = logging.Formatter("%(asctime)s --> %(name)s (%(levelname)s):\n%(message)s\n")
        fh.setFormatter(ff)
        root.addHandler(fh)

    # Create stream handler to print output
    if to_term:
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        cf = logging.Formatter('(%(name)s  %(levelname)s) --> %(message)s')
        ch.setFormatter(cf)
        root.addHandler(ch)



class QueueListener():
    """
    Class for managing the thread that handles worker logs\n
    Notes: to not create multiple instances of this class for a particular queue
    """

    def __init__(self, queue):
        self.__queue = queue
        self.__thread = None
        self.__suspend_signal = Event()

        self.__logger = logging.getLogger(__name__)
        self.__logger.setLevel(logging.DEBUG)


    def running(self):
        """Returns (bool): True if thread is running"""
        return isinstance(self.__thread, Thread) and self.__thread.is_alive()


    def start(self):
        """
        Start the listener thread\n
        Listener will read from the shared logging queue and emit log messages in the main process
        """
        # Check running
        if self.running():
            self.__logger.warning("Listener thread is already running")
            return
        
        # Clear 'stop' flag
        self.__suspend_signal.clear()

        # Create thread
        self.__thread = Thread(
            target=QueueListener.listen, 
            args=(self.__queue, self.__suspend_signal)
        )

        # Start thread
        self.__thread.start()


    def stop(self):
        """Stop listener thread"""
        if not self.running(): return

        self.__suspend_signal.set()
        try: self.__thread.join(timeout=2)
        except TimeoutError:
            self.__logger.error("Listener thread failed to terminate")


    @staticmethod
    def listen(queue, stop):
        """Continuously read log records from queue and emit them in the main process"""
        while not stop.is_set():
            # Pull the first entry from the log queue
            try: record = queue.get_nowait()
            except Empty: time.sleep(0.1)
            else:
                # Emit log message in main process
                logger = logging.getLogger(record.name)
                logger.handle(record)
