"""Worker process for polling PureThermal"""

from misc.logs import configure_subprocess
from .uvc_stream import PureThermalUVC
from lepton.utils import raw2temp
from constants import *
import numpy as np
import logging
import time
import cv2


def polling_worker(mem, lock, new, stop, log, errs, max_temp, hotspot):
    """
    Main polling loop for PureThermal Lepton driver

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of raw thermal image data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - new (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
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

        # Create UVC streaming object
        lep = PureThermalUVC(LIBUVC_DLL_PATH)

        # Open video stream
        logger.debug("Connecting to PureThermal")
        lep.start_stream()

        # Wait for first frame
        start = time.time()
        while True: 
            assert (time.time()-start) < 5, "Lepton did not send any data"

            ret, frame = lep.read()
            if ret:
                frame = cv2.medianBlur(frame, 3)
                max_temp.value = raw2temp(np.max(frame)) # Initialize value
                break

        logger.debug("PureThermal connected")

        # Timestamp for camera watchdog timer
        last_good_frame = time.time()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup error:")
        stop.set() # Skip loop

    else: logger.debug("Setup complete, starting polling loop...")
    
    # === Loop ===
    while not stop.is_set():
        try:
            # Grab frame
            ret, frame = lep.read()
            if ret: last_good_frame = time.time()
            else: 
                assert (time.time() - last_good_frame) < PURETHERMAL_TIMEOUT, "Camera connection timed out"
                continue

            # Copy frame to shared memory
            lock.acquire(timeout=0.5)
            np.copyto(frame_dst, frame)
            lock.release()

            # Set new frame flag
            new.set()

            # Remove extreme values before computing max temp
            frame = cv2.medianBlur(frame, 3)

            # Apply exponential moving average (EMA) filter to max_temp
            max_temp.value *= 1-HOTSPOT_EMA_ALPHA
            max_temp.value +=   HOTSPOT_EMA_ALPHA * raw2temp(np.max(frame))

            # Update 'hotpot detected' flag
            hotspot.value = max_temp.value > BLOB_MIN_TEMP

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

    else: logger.debug("Termination routine completed. Exiting...")
