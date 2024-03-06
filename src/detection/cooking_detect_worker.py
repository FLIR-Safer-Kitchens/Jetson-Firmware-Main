# Worker that performs cooking detection

from detection import RAW_THERMAL_SHAPE
import numpy as np
import time
import cv2


def cooking_detect_worker(mem, lock, stop, errs, hotspot_det, cooking_det):
    """
    Main cooking detection loop

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of raw16 image data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    - hotspot_det (multiprocessing.Value (uchar)): True if a hotspot is detected
    - cooking_det (multiprocessing.Value (uchar)): True if cooking is detected
    """

    # === Setup ===
    try:
        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

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

            # TODO: Do cooking detection here

            # -- For debugging. delete me --
            cv2.imshow("test", frame)
            cv2.waitKey(1)
            time.sleep(10e-3)

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
