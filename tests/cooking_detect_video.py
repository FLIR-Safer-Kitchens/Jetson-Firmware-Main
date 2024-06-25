"""Cooking detection testbench (.tiff input)"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from lepton.file_utils import Raw16Video
from constants import RAW_THERMAL_SHAPE
from misc.monitor import MonitorClient
from ctypes import c_uint16
from misc.logs import *
import numpy as np
import logging
import cv2

from cooking_detection import CookingDetect
# from stubs import CookingDetect

def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(10)

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

    # Instantiate launcher
    cd = CookingDetect()

    # Cooking state 
    detected = False

    # Instantiate monitor
    monitor = MonitorClient(12347)
    cd.streaming_ports.append(12347)
    cv2.namedWindow("monitor", cv2.WINDOW_NORMAL)

    # Load lepton video
    vid = Raw16Video(path.normpath(path.join(path.dirname(path.abspath(__file__)), 'vids', "demo.tiff")))

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
            if (cd.running() != running):
                ret = cd.handle_exceptions()
                assert ret, "Cooking detection process not recoverable"
                logger.warning("Attempting to restart cooking detection process")
                cd.start(mem, new_frame_child, logging_queue)

            if running:
                # Grab frame
                ret, frame = vid.read()
                if not ret: raise KeyboardInterrupt

                # Write frame to shared memory
                if not mem.get_lock().acquire(timeout=0.5): continue
                np.copyto(frame_dst, frame)
                mem.get_lock().release()
                new_frame_parent.set()

                # Print when detection state changes
                old = detected
                detected = len(cd.cooking_coords) > 0
                if detected and not old: logger.info(f"Cooking Detected at {cd.cooking_coords}")
                elif old and not detected: logger.info("Cooking No Longer Detected")

                # Display monitor output
                ret, monitor_frame = monitor.read()
                if ret: cv2.imshow("monitor", monitor_frame)
            
            # Controls
            k = cv2.waitKey(round(1000/9))
            if k == ord('p'):
                logger.info("stopping worker")
                running = False
                cd.stop()
                new_frame_parent.clear()
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                cd.start(mem, new_frame_child, logging_queue)
            elif k == ord('q'):
                logger.info("quitting")
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("test ended")
    except:
        logger.exception("")
    finally:
        cd.stop()      
        monitor.stop()
        logging_thread.stop()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
