"""Handles transcoding from raw thermal video to colorized HLS stream"""

from misc.logs import configure_subprocess
from lepton.utils import clip_norm
import subprocess as sp
from constants import *
import numpy as np
import logging
import socket
import cv2
import os


def transcoder_worker(mem, lock, new, stop, log, errs):
    """
    Accept incoming raw thermal frames, stream to ffmpeg using UDP, and output a HLS stream

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of raw16 image data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - new (multiprocessing.Event): Flag that indicates when a new frame is available
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
        configure_subprocess(log)

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Create a UDP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Start converting UDP to HLS
        logger.debug("Starting FFMPEG subprocess")
        transcode_proc = start_transcoder()
        logger.debug("FFMPEG subprocess started")

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup error:")
        stop.set() # Skip loop

    else: logger.debug("Setup complete, starting streaming loop...")

    # === Loop ===
    while not stop.is_set():
        try:
            # Check transcoder process
            assert transcode_proc.poll() == None

            # Dump subprocess stdout and stderr
            # log_output(transcode_proc, logger)

            # Check for new frame
            if not new.is_set(): continue
            else: new.clear()

            # Copy frame from shared memory
            lock.acquire(timeout=0.5)
            np.copyto(frame, frame_src)
            lock.release()

            # Normalize & colorize frame
            frame = clip_norm(frame)
            color_frame = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)

            # Convert frame to bytes
            frame_bytes = cv2.imencode('.jpg', color_frame)[1].tobytes()

            # Transmit frame via UDP socket
            sock.sendto(frame_bytes, ('127.0.0.1', UDP_PORT))

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop error:")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        # Shut down ffmpeg transcoder
        transcode_proc.terminate()
        try: transcode_proc.wait(100e-3)
        except sp.TimeoutExpired:
            logger.warning("ffmpeg process would not terminate gracefully. Killing...")
            transcode_proc.kill()

        # Emit any lingering error messages
        log_output(transcode_proc, logger)

        # Shut down UDP socket
        sock.close()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")


def start_transcoder():
    """Start the process to convert from UDP to HLS"""

    # ffmpeg command
    command = [
        'ffmpeg',
        '-f',                    'mjpeg',                       # Input format
        '-an',                                                  # No audio
        '-i',                   f'udp://127.0.0.1:{UDP_PORT}',  # Input source (e.g., UDP stream)
        '-c:v',                  'libx264',                     # Video codec
        '-preset',               'ultrafast',                   # Preset for faster encoding
        '-f',                    'hls',                         # Output format HLS
        '-hls_time',             '2',                           # Segment duration (in seconds)
        '-hls_list_size',        '6',                           # Maximum number of playlist entries
        '-hls_flags',            'delete_segments+append_list', # HLS flags
        '-hls_segment_filename', 
        os.path.join(HLS_DIRECTORY, 'segment%d.ts'), # Segment filename pattern
        os.path.join(HLS_DIRECTORY, HLS_FILENAME)    # Output URL for HLS stream
    ]

    # Launch the subprocess with output redirection
    return sp.Popen(command, stdout=sp.DEVNULL, stderr=sp.STDOUT, text=True)


def log_output(proc, logger):
    """
    Log stdout and stderr from subprocess
    
    Arguments:
    - proc (subprocess.Popen): Process to be checked
    - logger (logging.Logger): logger to log to
    """

    text = proc.stdout.readline()
    if len(text):
        logger.error(f"ffmpeg stderr: {text}")
