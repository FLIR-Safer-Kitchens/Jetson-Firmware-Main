"""Worker that performs user detection"""

from constants import VISIBLE_SHAPE
import numpy as np
import time
import cv2


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

    # === Setup ===
    try:
        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        cv2.namedWindow("test", cv2.WINDOW_NORMAL) # For debugging. delete me

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        return

    # === Loop ===
    while not stop.is_set():
        try:
            # Copy frame from shared memory
            lock.acquire(True)
            frame = frame_src.copy()
            lock.release()

            # TODO: Do user detection here

            # -- For debugging. delete me --
            cv2.imshow("test", frame)
            cv2.waitKey(1)
            time.sleep(10e-3)
            detect_ts.value = time.time()

            # if round(time.time())%10 == 3: 1/0
            # -------------------------------

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            return

    # === Terminate ===
    try:
        cv2.destroyWindow("test") # For debugging. delete me

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        return
