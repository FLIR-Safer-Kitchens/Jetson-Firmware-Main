# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Queue
from constants import RAW_THERMAL_SHAPE
from streaming import Transcoder
from misc import BroadcastEvent
from constants import *
from misc.logs import *
import numpy as np
import logging
import socket
import cv2


def main():
    # Configure logger
    configure_main(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(40)

    # Create array for us to copy to
    frame = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16')

    # Create image array in shared memory
    mem = shared_memory.SharedMemory(create=True, size=frame.nbytes)

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create master event object for new frames
    new_frame_parent = BroadcastEvent()

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
        
        running = False
        while True:
            # Check log listener status
            if not logging_thread.running():
                logger.warning("Log listener died. Restarting...")
                logging_thread.start()

            # Check worker status
            if tc.running() != running:
                raise ValueError(f"Expected {running}. Got {tc.running()}.")

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
                mem_lock.acquire(block=True)
                np.copyto(frame_dst, frame.astype("uint16"))
                mem_lock.release()
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
                tc.start(mem, mem_lock, new_frame_child, logging_queue)
            elif k == ord('q'):
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        tc.stop()       
        mem.close()
        mem.unlink()
        vid.release()
        logging_thread.stop()
        cv2.destroyAllWindows()
        logger.info("test ended")


if __name__ == '__main__':
    main()
