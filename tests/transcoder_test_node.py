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
import cv2

# from streaming import Transcoder
from stubs import Transcoder

from misc.node_server import NodeServer
# from stubs import NodeServer


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

    # Create node server object
    node = NodeServer()

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        # Webcam
        vid = cv2.VideoCapture(0)

        # Connect to node server
        node.connect()
        
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

            # Send status
            m3u8_path = tc.m3u8_path if running else None
            node.send_status([], 69.0, 300, m3u8_path)
            
            if running:
                # Grab frame
                ret, frame = vid.read()
                if not ret: raise KeyboardInterrupt

                # Reshape frame to resemble raw thermal video
                frame = cv2.resize(frame, (160, 120))
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

                # Write frame to shared memory
                mem.get_lock().acquire(timeout=0.5)
                np.copyto(frame_dst, frame.astype("uint16"))
                mem.get_lock().release()
                new_frame_parent.set()

            # Controls
            if running and not node.livestream_on:
                logger.info("stopping worker")
                running = False
                tc.stop()
                new_frame_parent.clear()
            elif not running and node.livestream_on:
                logger.info("starting worker")
                running = True
                tc.start(mem, new_frame_child, logging_queue)
            
            running = node.livestream_on
    
    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        tc.stop()
        vid.release()
        node.disconnect()
        logging_thread.stop()
        cv2.destroyAllWindows()
        logger.info("test ended")


if __name__ == '__main__':
    main()
