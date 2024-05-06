"""Lepton polling testbench"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Queue
from constants import RAW_THERMAL_SHAPE
from lepton.polling import PureThermal
from lepton.utils import clip_norm
from misc import NewFrameEvent
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

    # Create array for us to copy to
    frame = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16')

    # Create image array in shared memory
    mem = shared_memory.SharedMemory(create=True, size=frame.nbytes)

    # Create numpy array backed by shared memory
    frame_src = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

    # Create array for us to copy to
    raw = np.empty_like(frame_src)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Create child event object for reader process
    new_frame_child = new_frame_parent.get_child()

    # Instantiate launcher
    pt = PureThermal()

    # Create window
    cv2.namedWindow("frame", cv2.WINDOW_NORMAL)

    # Timestamp for debug messages
    last_print = 0

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
            if pt.running() != running:
                raise ValueError(f"Expected {running}. Got {pt.running()}.")

            if running and new_frame_child.is_set():
                new_frame_child.clear()

                # Grab frame from shared memory
                mem_lock.acquire(timeout=0.5)
                np.copyto(raw, frame_src)
                mem_lock.release()

                # Show image
                color = cv2.applyColorMap(clip_norm(raw), cv2.COLORMAP_INFERNO)
                cv2.imshow("frame", color)

                # Display detection outputs
                # if (time.time()-last_print) > 1:
                #     last_print = time.time()
                #     logger.info(f"Max Temperature: {pt.max_temp.value:.1f}. Hotspot Detected: {pt.hotspot_detected.value}")
            
            # Controls
            k = cv2.waitKey(25)
            if k == ord('p'):
                logger.info("stopping worker")
                running = False
                pt.stop()
                new_frame_parent.clear()
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                pt.start(mem, mem_lock, new_frame_child, logging_queue)
            elif k == ord('q'):
                logger.info("quitting")
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("test ended")
    except:
        logger.exception("")
    finally:
        pt.stop()       
        mem.close()
        mem.unlink()
        logging_thread.stop()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
