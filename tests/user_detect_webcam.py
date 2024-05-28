"""User detection testbench (without arducam)"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from multiprocessing import Array, Queue
from misc.monitor import MonitorClient
from constants import VISIBLE_SHAPE
from misc import NewFrameEvent
from ctypes import c_uint8
from misc.logs import *
import numpy as np
import logging
import cv2

# from user_detection import UserDetect
from stubs import UserDetect


def main():
    # Configure logger
    configure_main(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(10)

    # Create image array in shared memory
    dummy = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8')
    mem = Array(c_uint8, dummy.nbytes, lock=True)

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.get_obj())

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Get a different child event for each process that reads frame data
    new_frame_child = new_frame_parent.get_child()

    # Instantiate launchers
    user = UserDetect()

    # User detection output
    detected = False

    # Instantiate monitor
    monitor = MonitorClient(12346)
    cv2.namedWindow("monitor", cv2.WINDOW_NORMAL)

    try:
        # Open webcam
        vid = cv2.VideoCapture(0)
        assert vid.isOpened()

        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        running = False
        while True:
            # Check log listener status
            if not logging_thread.running():
                logger.warning("Log listener died. Restarting...")
                logging_thread.start()

            # Check worker status
            if user.running() != running:
                ret = user.handle_exceptions()
                assert ret, "User detection process not recoverable"
                logger.warning("Attempting to restart user detection process")
                user.start(mem, new_frame_child, logging_queue)
            
            # Get webcam frame
            ret, frame = vid.read()
            assert ret, "Bad Frame"

            # Process frame
            if frame.shape != VISIBLE_SHAPE:
                frame.resize(VISIBLE_SHAPE)

            # Copy frame to shared memory
            mem.get_lock().acquire(timeout=0.5)
            np.copyto(frame_dst, frame)
            mem.get_lock().release()

            # Set new frame flag
            new_frame_parent.set()
            
            # Print when detection state changes
            old = detected
            detected = (time.time() - user.last_detected.value) < 5
            if detected and not old: logger.info("User Detected")
            elif old and not detected: logger.info("User No Longer Detected")

            # Display monitor output
            ret, monitor_frame = monitor.read()
            if ret: cv2.imshow("monitor", monitor_frame)

            # Handle commands
            k = cv2.waitKey(10)
            if k == ord('p'):
                logger.info("stopping workers")
                running = False
                user.stop()
            
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                user.start(mem, new_frame_child, logging_queue)
                
            elif k == ord('q'):
                raise KeyboardInterrupt

    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        user.stop()
        vid.release()
        monitor.stop()

        logging_thread.stop()
        logger.info("test ended")


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
