"""Handles transcoding from raw thermal video to colorized HLS stream"""

from misc.logs import configure_subprocess_log
# from misc.monitor import MonitorServer
from lepton.utils import clip_norm
from constants import *
import numpy as np
import logging
import socket
import cv2

# Maximum UDP packet size
BUFF_SIZE = 65507


def transcoder_worker(stream_type, mem, new, stop, log, errs):
    """
    Accept incoming image frames, stream to a separate process using UDP

    Parameters:
    - stream_type (str): The type of stream, either "thermal" or "visible" (check constants.py)
    - mem (multiprocessing.Array): Shared memory location of the image data
    - new (NewFrameConsumer): Flag that indicates when a new frame is available
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    """

    # === Setup ===
    try:
        # Create logger 
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Set up logs for subprocess
        configure_subprocess_log(log)

        # Create numpy array backed by shared memory
        # and choose compression level
        if stream_type == STREAM_TYPE_THERMAL:
            frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.get_obj())
            comp_level = 100
        elif stream_type == STREAM_TYPE_VISIBLE:
            frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.get_obj())
            comp_level = 80

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Create monitor
        # monitor = MonitorServer()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup error:")
        stop.set() # Skip loop

    else: logger.debug("Setup complete, starting streaming loop...")

    # === Loop ===
    while not stop.is_set():
        try:
            # Wait for new frame
            if not new.wait(timeout=0.5): continue
            else: new.clear()

            # Copy frame from shared memory
            mem.get_lock().acquire(timeout=0.2)
            np.copyto(frame, frame_src)
            mem.get_lock().release()

            # Pre-process frame
            if stream_type == STREAM_TYPE_THERMAL:
                clipped_frame = clip_norm(frame)
                color_frame = cv2.applyColorMap(clipped_frame, cv2.COLORMAP_INFERNO)
            else:
                color_frame = frame.copy()

            # Send frame to monitor
            # monitor.show(color_frame, 13023)

            # Convert frame to bytes
            frame_bytes = cv2.imencode('.jpg', color_frame, [cv2.IMWRITE_JPEG_QUALITY, comp_level])[1].tobytes()
            if len(frame_bytes) > BUFF_SIZE:
                logger.warning(f"Packet too large. ({len(frame_bytes)}>{BUFF_SIZE})")
                comp_level -= 5
                continue

            # Transmit frame via UDP socket
            sock.sendto(frame_bytes, ('127.0.0.1', STREAM_UDP_PORT))

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop error:")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        # Shut down UDP socket
        sock.close()

        # Close monitor
        # monitor.stop()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")
