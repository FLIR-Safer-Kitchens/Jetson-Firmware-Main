"""User detection testbench (with arducam worker)"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from misc.monitor import MonitorClient
from constants import VISIBLE_SHAPE
from ctypes import c_uint8
from misc.logs import *
import numpy as np
import logging
import cv2

from user_detection import UserDetect
# from stubs import UserDetect

from arducam import Arducam
# from stubs.arducam_random import Arducam
# from stubs.arducam_webcam import Arducam


def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(10)

    # Create image array in shared memory
    dummy = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8')
    mem = Array(c_uint8, dummy.nbytes, lock=True)

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Get a different child event for each process that reads frame data
    new_frame_child = new_frame_parent.get_child()

    # Instantiate launchers
    user = UserDetect()
    cam  = Arducam()

    # User detection output
    detected = False

    # Instantiate monitor
    monitor = MonitorClient(12346)
    user.streaming_ports.append(12346)
    cv2.namedWindow("monitor", cv2.WINDOW_NORMAL)

    try:
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
            
            if cam.running() != running:
                ret = cam.handle_exceptions()
                assert ret, "Arducam polling process not recoverable"
                logger.warning("Attempting to restart arducam polling process")
                cam.start(mem, new_frame_parent, logging_queue)
            
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
                cam.stop()
            
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                cam.start(mem, new_frame_parent, logging_queue)
                user.start(mem, new_frame_child, logging_queue)
                
            elif k == ord('q'):
                raise KeyboardInterrupt

    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        user.stop()
        cam.stop()
        monitor.stop()

        logging_thread.stop()
        logger.info("test ended")


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
