# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from constants import RAW_THERMAL_SHAPE
from ctypes import c_uint16
from constants import *
from misc.logs import *
import numpy as np
import logging
import time
import cv2

import socketserver
import threading
import http.server
import os

from streaming import Transcoder
# from stubs import Transcoder


# Starts the HTTP server
def start_http_server(directory, port=8000):
    while not os.path.isdir(directory):
        time.sleep(0.1)

    os.chdir(directory)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Serving HLS content on port {port}")
        httpd.serve_forever()



def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(40)

    # Create array for us to copy to
    frame = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16')

    # Create image array in shared memory
    mem = Array(c_uint16, frame.nbytes, lock=True)

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.get_obj())

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Create child event object for reader process
    new_frame_child = new_frame_parent.get_child()

    # Create transcoder launcher object
    tc = Transcoder()
    
    cv2.namedWindow("control", cv2.WINDOW_NORMAL)

    # Create video capture object
    vid = cv2.VideoCapture(0)

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        # Start the HTTP server in a separate thread
        server_thread = threading.Thread(target=start_http_server, args=(os.path.dirname(tc.m3u8_path),))
        server_thread.daemon = True
        server_thread.start()
        
        running = False
        while True:
            # Check log listener status
            if not logging_thread.running():
                logger.warning("Log listener died. Restarting...")
                logging_thread.start()

            # Check worker status
            if (tc.running() != running):
                ret = tc.handle_exceptions()
                assert ret, "Transcoder process not recoverable"
                logger.warning("Attempting to restart transcoder process")
                tc.start(mem, new_frame_child, logging_queue)
            
            if running:
                # Grab frame
                ret, frame = vid.read()
                if not ret: raise KeyboardInterrupt

                # Reshape frame to resemble raw thermal video
                frame = cv2.resize(frame, (160, 120))
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

                # Display the frame
                cv2.imshow('control', frame)

                # Write frame to shared memory
                mem.get_lock().acquire(timeout=0.5)
                np.copyto(frame_dst, frame.astype("uint16"))
                mem.get_lock().release()
                new_frame_parent.set()

            # Controls
            k = cv2.waitKey(25)
            if k == ord('p'):
                logger.info("stopping worker")
                running = False
                tc.stop()
                new_frame_parent.clear()
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                tc.start(mem, new_frame_child, logging_queue)
            elif k == ord('q'):
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        tc.stop()
        vid.release()
        logging_thread.stop()
        cv2.destroyAllWindows()
        logger.info("test ended")


if __name__ == '__main__':
    main()
