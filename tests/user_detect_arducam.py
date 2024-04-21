"""User detection testbench (with arducam worker)"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Queue
from misc.monitor import MonitorClient
from user_detection import UserDetect
from constants import VISIBLE_SHAPE
from misc import BroadcastEvent
from arducam import Arducam
from misc.logs import *
import numpy as np
import logging
import cv2


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
    mem = shared_memory.SharedMemory(create=True, size=dummy.nbytes)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create master event object for new frames
    new_frame_parent = BroadcastEvent()

    # Get a different child event for each process that reads frame data
    new_frame_child = new_frame_parent.get_child()

    # Instantiate launchers
    user = UserDetect()
    cam  = Arducam()

    # User detection output
    detected = False

    # Instantiate monitor
    monitor = MonitorClient(12346)
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
            if (user.running() != running) or (cam.running() != running):
                raise ValueError(f"Expected {running}, {running}. Got {user.running()}, {cam.running()}.")
            
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
                cam.start(mem, mem_lock, new_frame_parent, logging_queue)
                user.start(mem, mem_lock, new_frame_child, logging_queue)
                
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
        
        mem.close()
        mem.unlink()

        logging_thread.stop()
        logger.info("test ended")


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
