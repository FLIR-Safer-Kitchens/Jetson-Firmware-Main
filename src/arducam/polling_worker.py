from constants import VISIBLE_SHAPE
import numpy as np
import time
import cv2


def polling_worker(mem, lock, new, stop, errs):
    # === Setup ===
    try:
        # Create video capture object
        vidcap = cv2.VideoCapture(0)
        assert vidcap.isOpened()

        # Create numpy array backed by shared memory
        frame_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

        # Timestamp for camera watchdog timer
        last_good_frame = 0

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        return
    
    # === Loop ===
    while not stop.is_set():
        try:
            # Grab frame
            ret, frame = vidcap.read()
            if ret: last_good_frame = time.time()
            else: assert (time.time() - last_good_frame) < 1.0, "Camera connection timed out"

            # Process frame
            if frame.shape != VISIBLE_SHAPE:
                frame.resize(VISIBLE_SHAPE)

            # Copy frame to shared memory
            lock.acquire(True)
            np.copyto(frame_dst, frame)
            lock.release()

            # Set new frame flag
            new.set()

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            return

    # === Terminate ===
    try:
        new.clear() # Invalidate last data
        vidcap.release()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        return
