"""Arducam polling testbench"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from constants import VISIBLE_SHAPE
from ctypes import c_uint8
from misc.logs import *
import numpy as np
import logging
import cv2

from arducam import Arducam
# from stubs import Arducam


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

    # Create numpy array backed by shared memory
    frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.get_obj())

    # Create array for us to copy to
    frame = np.empty_like(frame_src)

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Get a different child event for each process that reads frame data
    new_frame_child = new_frame_parent.get_child()

    # Instantiate launchers
    cam  = Arducam()

    # Create window to display frame
    cv2.namedWindow("frame", cv2.WINDOW_NORMAL)

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
            if (cam.running() != running):
                ret = cam.handle_exceptions()
                assert ret, "Arducam polling process not recoverable"
                logger.warning("Attempting to restart Arducam process")
                cam.start(mem, new_frame_parent, logging_queue)

            # Check for new frame
            if new_frame_child.is_set():
                new_frame_child.clear()

                # Copy frame from shared memory
                mem.get_lock().acquire(timeout=0.5)
                np.copyto(frame, frame_src)
                mem.get_lock().release()

                # Show frame
                cv2.imshow("frame", frame)

            # Handle commands
            k = cv2.waitKey(10)
            if k == ord('p'):
                logger.info("stopping workers")
                running = False
                cam.stop()
                assert cam.handle_exceptions(), "Arducam shutdown failed"
            
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                cam.start(mem, new_frame_parent, logging_queue)
                
            elif k == ord('q'):
                raise KeyboardInterrupt

    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        cam.stop()

        logging_thread.stop()
        logger.info("test ended")


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
