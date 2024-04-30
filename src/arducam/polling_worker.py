"""Worker process for polling Arducam"""

from constants import VISIBLE_SHAPE, ARDUCAM_TIMEOUT
from misc.logs import configure_subprocess
import numpy as np
import subprocess
import platform
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

        # Find Arducam
        logger.debug("Searching for Arducam")
        arducam_index = get_arducam_index()
        assert arducam_index != None, "Failed to find Arducam"

        # Open Arducam
        logger.debug(f"Attemping to open VideoCapture({arducam_index})")
        vidcap = cv2.VideoCapture(arducam_index)
        assert vidcap.isOpened(), "VideoCapture failed to open"

        # Set resolution
        if int(vidcap.get(cv2.CAP_PROP_FRAME_WIDTH)) != int(VISIBLE_SHAPE[1]):
            assert vidcap.set(cv2.CAP_PROP_FRAME_WIDTH, VISIBLE_SHAPE[1]), "Failed to set image width"
        if int(vidcap.get(cv2.CAP_PROP_FRAME_HEIGHT)) != int(VISIBLE_SHAPE[0]):
            assert vidcap.set(cv2.CAP_PROP_FRAME_HEIGHT, VISIBLE_SHAPE[0]), "Failed to set image height"
        
        # Wait for first frame
        start = time.time()
        while True:
            # Enforce timeout
            assert (time.time()-start) < 5, "Arducam did not send any data"
            
            # Read frame & double check resolution
            ret, frame = vidcap.read()
            if ret:
                assert frame.shape == VISIBLE_SHAPE, "Arducam resolution incorrect"
                break
        
        logger.debug("Arducam opened sucessfully")

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
        try: vidcap.release()
        except UnboundLocalError: pass # vidcap not yet created

        new.clear() # Invalidate last data

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")


def get_arducam_index():
    """Cross-platform method to find the index of the Arducam camera module"""

    if platform.system() == 'Windows':
        # List AV input devices
        cmd = "ffmpeg -f dshow -list_devices true -hide_banner -i dummy"
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
        output = proc.stderr.decode('utf-8')

        # Find arducam index
        lines = output.splitlines()
        for idx in range(0, len(lines), 2):
            if "USB Camera" in lines[idx]:
                return int(idx/2)

    elif platform.system() == 'Linux':
        # List video input devices
        cmd = "v4l2-ctl --list-devices"
        proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL)
        output = proc.stderr.decode('utf-8')

        # Find arducam index
        lines = output.splitlines()
        for idx, line in enumerate(lines): 
            if "Arducam_8mp" in line:
                return lines[idx+1].strip()
            
    return None
