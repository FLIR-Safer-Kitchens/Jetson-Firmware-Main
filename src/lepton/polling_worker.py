"""Worker process for polling PureThermal"""

from constants import HOTSPOT_TRIP_TIME, HOTSPOT_RELEASE_TIME
from misc.logs import configure_subprocess_log
from lepton.utils import raw2temp, clip_norm
from .uvc_windows import PureThermalWindows
from misc.hysteresis import HysteresisBool
from .uvc_stream import PureThermalUVC
from misc.monitor import MonitorServer
from constants import *
import numpy as np
import platform
import logging
import time
import cv2


def polling_worker(mem, new, stop, log, errs, max_temp, hotspot):
    """
    Main polling loop for PureThermal Lepton driver

    Parameters:
    - mem (multiprocessing.Array): Shared memory location of raw thermal image data
    - new (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    """
    # === Setup ===
    try:
        # Configure subprocess logs
        configure_subprocess_log(log)

        # Create logger 
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Create numpy array backed by shared memory
        frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.get_obj())

        # Create UVC streaming object
        # TODO: In theory, libuvc should work for windows as well.
        # I just have not had much luck trying to install it
        if platform.system() == "Linux":
            lep = PureThermalUVC(LIBUVC_DLL_PATH)
        elif platform.system() == "Windows":
            lep = PureThermalWindows()

        # Open video stream
        logger.debug("Connecting to PureThermal")
        lep.start_stream()

        # Wait for first frame
        start = time.time()
        while True: 
            assert (time.time()-start) < 5, "Lepton did not send any data"

            ret, frame = lep.read()
            if ret:
                max_temp.value = get_max_temp(frame)[0] # Initialize value
                break

        logger.debug("PureThermal connected")

        # Create monitor
        monitor = MonitorServer(12348)

        # Timestamp for camera watchdog timer
        last_good_frame = time.time()

        # Applies time-based hysteresis to the hotspot detection flag
        hotspot_detected = HysteresisBool(HOTSPOT_TRIP_TIME, HOTSPOT_RELEASE_TIME)

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

            # Flip frame
            frame = np.flipud(frame)

            # Copy frame to shared memory
            mem.get_lock().acquire(timeout=0.5)
            np.copyto(frame_dst, frame)
            mem.get_lock().release()

            # Set new frame flag
            new.set()

            # Apply exponential moving average (EMA) filter to max_temp
            t_max, t_max_loc = get_max_temp(frame)
            max_temp.value *= 1-HOTSPOT_EMA_ALPHA
            max_temp.value +=   HOTSPOT_EMA_ALPHA*t_max

            # Update 'hotpot detected' flag
            hotspot_detected.value = max_temp.value > BLOB_MIN_TEMP
            hotspot.value = hotspot_detected.value

            # Show monitor output
            frame = cv2.applyColorMap(clip_norm(frame), cv2.COLORMAP_INFERNO)
            cv2.circle(frame, t_max_loc, 3, (0, 255, 0), -1)
            monitor.show(frame, 100)

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop error:")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        monitor.stop()
        lep.stop_stream()
        new.clear() # Invalidate last data
        
    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")


def get_max_temp(frame):
    """
    Gets the hottest temperature in the image and its coordinates
    
    Parameters:
    - frame (numpy.ndarray): Raw-16 image array
    
    Returns (tuple):
    - (float) Maximum temperature in celsius
    - (tuple (int, int)): The image coordinates (x, y) of the hottest pixel
    
    Note: I had to truncate the 16-bit array to 8-bit so the temperature accuracy is +/- 2.56 C
    """
    frame = cv2.medianBlur((frame >> 8).astype("uint8"), 7) # Filter outliers
    _, t_max, _, loc = cv2.minMaxLoc(frame)
    return raw2temp(int(t_max) << 8), loc
