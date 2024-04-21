"""Worker that performs cooking detection"""

from lepton.utils import clip_norm, temp2raw
from misc.logs import configure_subprocess
from misc.monitor import MonitorServer
from constants import *
from .blob import Blob
import numpy as np
import logging
import cv2


def cooking_detect_worker(mem, lock, new, stop, log, errs, hotspot_det, cooking_det):
    """
    Main cooking detection loop

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of raw16 image data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - new (multiprocessing.Event): Flag that indicates when a new frame is available
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    - hotspot_det (multiprocessing.Value (uchar)): True if a hotspot is detected
    - cooking_det (multiprocessing.Value (uchar)): True if cooking is detected
    """

    # === Setup ===
    try:
        # Create logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Set up logs for subprocess
        configure_subprocess(log)

        # Create a UDP server to send images to for debugging
        monitor = MonitorServer(12347)

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

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
            # Check for new frame
            if not new.is_set(): continue
            else: new.clear()

            # Copy frame from shared memory
            lock.acquire(timeout=0.5)
            np.copyto(frame, frame_src)
            lock.release()

            # Find blobs in image
            new_blobs = find_blobs(frame)

            # Filter new blobs
            good = lambda b: (b.area >= BLOB_MIN_AREA) and (b.temp >= BLOB_MIN_TEMP)
            new_blobs = [b for b in new_blobs if good(b)]

            # Compare and match blobs
            tracked_blobs = match_blobs(new_blobs, tracked_blobs)

            # Check for hot spots
            # TODO? Better conditions for hotspots
            hotspot_det.value = len(tracked_blobs) > 0

            # Check for cooking
            cooking_det.value = any(b.is_cooking() for b in tracked_blobs)

            # Output to debug monitor
            three_chan = cv2.merge([clip_norm(frame)]*3)
            for blob in tracked_blobs:
                blob.draw_blob(three_chan)
            monitor.show(three_chan)

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop Error")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        monitor.stop()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination Error")

    else: logger.debug("Termination routine completed. Exiting...")


# Find blobs in image
# Return a list of blobs
def find_blobs(frame):
    # Clip cold pixels and convert to 8-bit
    clipped = clip_norm(
        img = frame,
        min_val = temp2raw(TEMP_THRESH_LOW),
        max_val = temp2raw(TEMP_THRESH_HIGH)
    )

    # Bilateral filter
    clipped = cv2.bilateralFilter(
        src = clipped,
        d = 5,
        sigmaColor = 30,
        sigmaSpace = 20
    )

    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        src = clipped,
        maxValue = 255,
        adaptiveMethod = cv2.ADAPTIVE_THRESH_MEAN_C,
        thresholdType = cv2.THRESH_BINARY,
        blockSize = 35,
        C = 0
    )

    # Close holes
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    closed = cv2.morphologyEx(
        src = thresh,
        op = cv2.MORPH_CLOSE,
        kernel = kernel,
        iterations = 2
    )

    # Find contours
    contours, heirarchy = cv2.findContours(
        image = closed,
        mode = cv2.RETR_EXTERNAL,
        method = cv2.CHAIN_APPROX_SIMPLE
    )

    return [Blob(c, frame) for c in contours]


# Compare newly extracted blobs to old blobs
# Decimate the list of new blobs
# Prune the list of old blobs
# Add new blobs to list
def match_blobs(new_blobs, old_blobs):
    # Compare each new blob with all old blobs
    compare_all_olds = lambda new: [new.compare(old) for old in old_blobs]
    similarities = [compare_all_olds(new) for new in new_blobs]

    out = []
    for i, row in enumerate(similarities):
        # Find best match among old blobs
        if len(row) == 0:
            match_idx = None
        else:
            match_idx = np.argmax(row)

            # Apply score threshold
            if row[match_idx] < SIM_SCORE_MATCH:
                match_idx = None

        # Got good match, merge blobs
        if match_idx != None:
            out.append(new_blobs[i].merge(old_blobs[match_idx]))
            similarities[i][match_idx] = -1 # Mark match

        # No good matches, add new blob
        else: out.append(new_blobs[i])

    # Handle unmatched old blobs
    for c in range(len(old_blobs)):
        if (len(similarities) > c) and (-1 in [row[c] for row in similarities]):
            continue

        # Decrement score
        old_blobs[c].lives -= 1

        # Keep unmatched blobs until their scores hit 0
        if old_blobs[c].lives > 0:
            out.append(old_blobs[c])

    return out
