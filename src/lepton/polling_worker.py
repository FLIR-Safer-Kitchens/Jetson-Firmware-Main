"""Worker process for polling PureThermal"""

from constants import RAW_THERMAL_SHAPE, LIBUVC_DLL_PATH
from misc.logs import configure_subprocess
from uvc_stream import PureThermalUVC
import numpy as np
import logging
import time


def polling_worker(mem, lock, new, stop, log, errs):
    """
    Main polling loop for PureThermal Lepton driver

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of raw thermal image data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - new (BroadcastEvent): Master 'new frame' event. Set all child events when a new frame is written
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    """
    # === Setup ===
    try:
        # Configure subprocess logs
        configure_subprocess(log)

        # Create logger 
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Create numpy array backed by shared memory
        frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

        # Create UVC streaming object & start stream
        lep = PureThermalUVC(LIBUVC_DLL_PATH)
        lep.start_stream()

        # Timestamp for camera watchdog timer
        last_good_frame = 0

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup error:")
        stop.set() # Skip loop
    
    # === Loop ===
    while not stop.is_set():
        try:
            # Grab frame
            ret, frame = lep.read()
            if ret: last_good_frame = time.time()
            else: assert (time.time() - last_good_frame) < 1.0, "Camera connection timed out"

            # Copy frame to shared memory
            lock.acquire(True)
            np.copyto(frame_dst, frame)
            lock.release()

            # Set new frame flag
            new.set()

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop error:")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        lep.stop_stream()
        new.clear() # Invalidate last data
        
    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")
