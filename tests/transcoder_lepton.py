# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from misc.monitor import MonitorClient
from ctypes import c_uint16
from constants import *
from misc.logs import *
import numpy as np
import logging
import cv2

from streaming import Transcoder
# from stubs import Transcoder

from lepton.polling import PureThermal
# from stubs import PureThermal


def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(40)

    # Create image array in shared memory
    frame_bytes = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16').nbytes
    mem = Array(c_uint16, frame_bytes, lock=True)

    # Create master event object for new frames
    new_frame_parent = NewFrameEvent()

    # Create child event object for reader process
    new_frame_child = new_frame_parent.get_child()

    # Create transcoder launcher object
    tc = Transcoder()

    # Create purethermal process
    pt = PureThermal()

    # Create monitor
    monitor = MonitorClient(13023)
    pt.streaming_ports.append(13023)
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
            if (tc.running() != running):
                ret = tc.handle_exceptions()
                assert ret, "Transcoder process not recoverable"
                logger.warning("Attempting to restart transcoder process")
                tc.start(STREAM_TYPE_THERMAL, mem, new_frame_child, logging_queue)

            # Check worker status
            if (pt.running() != running):
                ret = pt.handle_exceptions()
                assert ret, "Lepton polling process not recoverable"
                logger.warning("Attempting to restart lepton polling process")
                pt.start(mem, new_frame_parent, logging_queue)
            
            if running:
                # Grab frame
                ret, frame = monitor.read()
                if not ret: continue

                # Display the frame
                cv2.imshow('monitor', frame)

            # Controls
            k = cv2.waitKey(25)
            if k == ord('p'):
                logger.info("stopping worker")
                running = False
                tc.stop()
                pt.stop()
            elif k == ord('s'):
                logger.info("starting worker")
                running = True
                tc.start(STREAM_TYPE_THERMAL, mem, new_frame_child, logging_queue)
                pt.start(mem, new_frame_parent, logging_queue)
            elif k == ord('q'):
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        tc.stop()
        pt.stop()
        monitor.stop()
        logging_thread.stop()
        cv2.destroyAllWindows()
        logger.info("test ended")


if __name__ == '__main__':
    main()
