"""Handles transcoding from raw thermal video to colorized HLS stream"""

from misc.logs import configure_subprocess
from lepton.utils import clip_norm
import subprocess as sp
from constants import *
import numpy as np
import logging
import secrets
import socket
import cv2
import os

# Maximum UDP packet size
BUFF_SIZE = 65507


def transcoder_worker(mem, new, stop, log, errs):
    """
    Accept incoming raw thermal frames, stream to ffmpeg using UDP, and output a HLS stream

    Parameters:
    - mem (multiprocessing.Array): Shared memory location of raw16 image data
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
        configure_subprocess(log)

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.get_obj())

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

            # Wait for new frame
            if not new.wait(timeout=0.5): continue
            else: new.clear()

            # Copy frame from shared memory
            mem.get_lock().acquire(timeout=0.2)
            np.copyto(frame, frame_src)
            mem.get_lock().release()

            # Normalize & colorize frame
            frame = clip_norm(frame)
            color_frame = cv2.applyColorMap(frame, cv2.COLORMAP_INFERNO)

            # Convert frame to bytes
            frame_bytes = cv2.imencode('.jpg', color_frame, [cv2.IMWRITE_JPEG_QUALITY, 100])[1].tobytes()
            if len(frame_bytes) > BUFF_SIZE:
                logger.warning(f"Packet too large. ({len(frame_bytes)}>{BUFF_SIZE})")
                continue

            # Transmit frame via UDP socket
            sock.sendto(frame_bytes, ('127.0.0.1', FFMPEG_UDP_PORT))

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop error:")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        # Shut down UDP socket
        sock.close()

        # Shut down ffmpeg transcoder
        transcode_proc.terminate()
        try: transcode_proc.wait(100e-3)
        except sp.TimeoutExpired:
            logger.warning("ffmpeg process would not terminate gracefully. Killing...")
            transcode_proc.kill()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination error:")

    else: logger.debug("Termination routine completed. Exiting...")


def start_transcoder():
    """Start the process to convert from UDP to HLS"""
    udp_stream_url =f'udp://127.0.0.1:{FFMPEG_UDP_PORT}'

    module_dir       = os.path.dirname(__file__)
    hls_dir          = os.path.join(module_dir, HLS_DIRECTORY)
    hls_seg_name     = os.path.join(hls_dir,    'segment%d.ts')
    hls_m3u8_name    = os.path.join(hls_dir,    HLS_M3U8_FILENAME)
    hls_keyinfo_name = os.path.join(hls_dir,    HLS_KEYINFO_FILENAME)
    hls_key_name     = os.path.join(hls_dir,    HLS_KEY_FILENAME)

    # Generate key and keyinfo file
    gen_keyinfo(hls_key_name, hls_keyinfo_name)

    # ffmpeg command
    command = [
        'ffmpeg',
        '-f',                    'mjpeg',                       # Input format
        '-an',                                                  # No audio
        '-i',                    udp_stream_url,                # Input source (e.g., UDP stream)
        '-r',                    '24',                          # Frame rate
        '-c:v',                  'libx264',                     # Video codec
        '-preset',               'ultrafast',                   # Preset for faster encoding
        '-force_key_frames',     'expr:gte(t,n_forced*1)',      # Force keyframes every 1 seconds
        '-f',                    'hls',                         # Output format HLS
        '-hls_time',             '2',                           # Segment duration (in seconds)
        '-hls_list_size',        '10',                           # Maximum number of playlist entries
        '-hls_flags',            'delete_segments+append_list+split_by_time', # HLS flags
        # '-hls_key_info_file',     hls_keyinfo_name,            # HLS key info filepath
        '-hls_segment_filename',  hls_seg_name,                 # Segment filename pattern
        hls_m3u8_name                                           # Output URL for HLS stream
    ]

    # Launch the subprocess with output redirection
    log_file_path = os.path.join(os.path.dirname(__file__), 'ffmpeg.log')
    with open(log_file_path, "w") as log_file:
        return sp.Popen(command, stdout=log_file, stderr=log_file)


def gen_keyinfo(key_file, keyinfo_file):
    # Generate key file
    with open(key_file, 'w') as f:
        key = secrets.token_bytes(16)
        f.write(f"{key.hex()}\n")

    # Generate keyinfo file
    with open(keyinfo_file, 'w') as f:
        f.write(f"{HLS_KEY_URI}\n")
        f.write(f"{key_file}\n")

        iv = secrets.token_bytes(16)
        f.write(f"{iv.hex()}\n")
