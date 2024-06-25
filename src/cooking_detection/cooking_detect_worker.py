"""Worker that performs cooking detection"""

from misc.logs import configure_subprocess_log
from lepton.utils import clip_norm, temp2raw
from misc.monitor import MonitorServer
from constants import *
from .blob import Blob
import numpy as np
import logging
import time
import cv2



def cooking_detect_worker(mem, new, ports, stop, log, errs, cooking_coords):
    """
    Main cooking detection loop

    Parameters:
    - mem (multiprocessing.Array): Shared memory location of raw16 image data
    - new (NewFrameConsumer): Flag that indicates when a new frame is available
    - ports (list (int)): List of UDP ports to stream image data to
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    - cooking_coords (multiprocessing.Manager.list): Centroid locations (x, y) of cooking blobs
    """

    # === Setup ===
    try:
        # Create logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Set up logs for subprocess
        configure_subprocess_log(log)

        # Create a UDP server to send images to for debugging
        monitor = MonitorServer()

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.get_obj())

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Create list of blobs
        tracked_blobs = []

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup Error")
        stop.set() # Skip loop

    else: logger.debug("Setup complete, starting cooking detection loop...")

    # === Loop ===
    while not stop.is_set():
        try:
            # Wait for new frame
            if not new.wait(timeout=0.5): continue
            else: new.clear()

            # Copy frame from shared memory
            if not mem.get_lock().acquire(timeout=0.2): continue
            np.copyto(frame, frame_src)
            mem.get_lock().release()

            # Find blobs in image
            new_blobs = find_blobs(frame)

            # Filter new blobs
            good = lambda b: (b.area >= BLOB_MIN_AREA) and (b.temp >= BLOB_MIN_TEMP)
            new_blobs = [b for b in new_blobs if good(b)]

            # Compare and match blobs
            tracked_blobs = match_blobs(new_blobs, tracked_blobs)

            # Output list of cooking blob centroids
            cooking_coords[:] = [list(b.centroid) for b in tracked_blobs if b.is_cooking()]

            # Output to debug monitor
            if len(ports):
                three_chan = cv2.merge([clip_norm(frame)]*3)
                for blob in tracked_blobs:
                    if blob.lives == BLOB_LIVES:
                        blob.draw_blob(three_chan)
                monitor.show(three_chan, *ports)

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop Error")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        try: monitor.stop()
        except UnboundLocalError: pass
        
        try: cooking_coords[:] = []
        except BrokenPipeError: pass

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination Error")

    else: logger.debug("Termination routine completed. Exiting...")


def find_blobs(frame):
    """
    Find blobs in image

    Parameters:
    - frame (numpy.ndarray): The raw, 16-bit thermal image

    Returns (list (Blob)): A list of detected blob objects
    """

    # Clip extreme pixel values and convert to 8-bit.
    # OpenCV doesn't like 16-bit images
    clipped = clip_norm(
        img = frame,
        min_val = temp2raw(TEMP_THRESH_LOW),
        max_val = temp2raw(TEMP_THRESH_HIGH)
    )

    # Bilateral filter
    # Edge-preserving, smoothing filter
    clipped = cv2.bilateralFilter(
        src = clipped,
        d = 5,
        sigmaColor = 30,
        sigmaSpace = 20
    )

    # Adaptive threshold
    # Binarizes image, true for regions of hot pixels
    thresh = cv2.adaptiveThreshold(
        src = clipped,
        maxValue = 255,
        adaptiveMethod = cv2.ADAPTIVE_THRESH_MEAN_C,
        thresholdType = cv2.THRESH_BINARY,
        blockSize = 35,
        C = 0
    )

    # Morphological closing
    # Closes any holes in the blob
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    closed = cv2.morphologyEx(
        src = thresh,
        op = cv2.MORPH_CLOSE,
        kernel = kernel,
        iterations = 2
    )

    # Find contours
    # Gets blob outline
    contours, heirarchy = cv2.findContours(
        image = closed,
        mode = cv2.RETR_EXTERNAL,
        method = cv2.CHAIN_APPROX_SIMPLE
    )

    return [Blob(c, frame) for c in contours]


def match_blobs(new_blobs, old_blobs):
    """
    Compare newly extracted blobs to old blobs.\n
    Prune the list of old blobs and add new blobs to list.
    
    Parameters:
    - new_blobs (list (Blob)): The list of new blob objects to merge and/or add
    - old_blobs (list (Blob)): The list of old blobs to purge and/or merge with

    Returns (list (Blob)): The updated list of tracked blobs
    """

    # Compare new and old blobs and compute the optimal matches
    if len(new_blobs) and len(old_blobs):

        # Compare each old blob with all new blobs
        compare_all_news = lambda old: [old.compare(new) for new in new_blobs]
        similarities = np.array([compare_all_news(old) for old in old_blobs])

        running = True
        while running:
            # For each old blob, find the new blob with the highest similarity score
            best_matches = np.argmax(similarities, axis=1)

            # Mark a new blob as a match if
            # - The similarity score is large enough AND
            # - This old blob hasn't alreay selected a match
            for r, c in enumerate(best_matches):
                mark = lambda row, c: (row[c] > SIM_SCORE_MATCH) and (-1 not in row)
                if mark(similarities[r,:], c): similarities[r,c] = -1

            # Make sure each new blob has only one match
            # If there is a conflict, select the oldest old blob
            matches = np.count_nonzero(similarities == -1, axis=0)
            for c, cnt in enumerate(matches):
                if cnt <= 1: continue # No conflict

                # Compute ages of all matching old blobs
                age  = lambda i: time.time() - old_blobs[i].first_detected
                ages = [(age(r) if (s==-1) else -1) for r, s in enumerate(similarities[:,c])]

                # Mark the oldest match and zero all other scores
                # for this new blob to prevent it from being selected again
                oldest = np.argmax(ages)
                similarities[:, c] = 0
                similarities[oldest, c] = -1

                # Start over to give old blobs a chance to select a new match
                break

            # Stop iterating after all new-blob conflicts have been resolved
            else: running = False

    # Prepare new tracked blobs list
    out = []

    # Handle new blobs
    if len(new_blobs):
        # No old blobs to match with
        if len(old_blobs) == 0:
            return new_blobs

        for c, col in enumerate(similarities.T):
            # Got a match, merge blobs
            if -1 in col:
                match_idx = np.where(col == -1)[0][0]
                out.append(new_blobs[c].merge(old_blobs[match_idx]))

            # No matches, add new blob
            else: out.append(new_blobs[c])

    # Handle old blobs
    for r in range(len(old_blobs)):

        # Decrement score if there were no matches
        if (len(new_blobs) == 0) or (-1 not in similarities[r,:]):
            old_blobs[r].lives -= 1

            # Keep unmatched blobs until their scores hit 0
            if old_blobs[r].lives > 0:
                out.append(old_blobs[r])

    return out
