"""Worker process for polling Arducam"""

from constants import VISIBLE_SHAPE, ARDUCAM_TIMEOUT
from misc.logs import configure_subprocess
import numpy as np
import logging
import time
import cv2


def polling_worker(mem, lock, new, stop, log, errs):
    """
    Main polling loop for Arducam

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of visible image data
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

        # Create video capture object
        logger.debug("Connecting to Arducam")
        vidcap = cv2.VideoCapture(0)
        assert check_open(vidcap), "Arducam could not be opened"
        logger.debug("Arducam connected sucessfully")

        # Create numpy array backed by shared memory
        frame_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

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
            ret, frame = vidcap.read()
            if ret: last_good_frame = time.time()
            else: 
                assert (time.time() - last_good_frame) < ARDUCAM_TIMEOUT, "Camera connection timed out"
                continue

            # Process frame
            if frame.shape != VISIBLE_SHAPE:
                frame.resize(VISIBLE_SHAPE)

            # Copy frame to shared memory
            lock.acquire(timeout=0.5)
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
        vidcap.release()
        new.clear() # Invalidate last data

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")


def check_open(vid_cap: cv2.VideoCapture, timeout=3.0):
    """
    Check that a videoCapture object is open and sending data
    
    Parameters:
    - vid_cap (cv2.VideoCapture): VideoCapture object to be checked
    - timeout (float): Maximum time in seconds to wait for the first frame
    """

    # Check if VideoCapture is opened
    if not vid_cap.isOpened(): return False

    # Wait for first frame
    start = time.time()
    while (time.time()-start) < timeout:
        if vid_cap.read()[0]: return True
    else: return False
