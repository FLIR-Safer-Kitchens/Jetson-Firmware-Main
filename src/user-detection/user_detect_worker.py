
from ..constants import VISIBLE_SHAPE
import numpy as np


def user_detect_worker(mem, lock, stop, errs, detect_ts):
    """
    Main user detection loop

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of visible camera data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    - detect_ts (multiprocessing.Value (double)): Epoch timestamp of last detection
    """

    try:
        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

        # Create array for us to copy to
        frame = np.empty_like(frame_src)
    
    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        raise

    while not stop.is_set():
        try:
            # Copy frame from shared memory
            lock.acquire(True)
            frame = frame_src.copy()
            lock.release()
            
            # TODO: Do stuff with image
            
        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            raise
