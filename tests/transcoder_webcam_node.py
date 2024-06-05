# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from ctypes import c_uint8, c_uint16
from constants import *
from misc.logs import *
import numpy as np
import logging
import cv2

from streaming import Transcoder
# from stubs import Transcoder

# from misc.node_server import NodeServer
# from stubs.node_server_basic import NodeServer
from stubs.node_server_full import NodeServer


def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(40)

    # Create image array in shared memory
    thermal_byes = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16').nbytes
    raw16_mem = Array(c_uint16, thermal_byes, lock=True)

    # Create numpy array backed by shared memory
    thermal_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=raw16_mem.get_obj())

    # Create image array in shared memory
    visible_byes = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8').nbytes
    vis_mem = Array(c_uint8, visible_byes, lock=True)

    # Create numpy array backed by shared memory
    visible_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=vis_mem.get_obj())

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
        
        running = node.livestream_on
        stream_type = node.livestream_type
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
                if stream_type == STREAM_TYPE_THERMAL:
                    tc.start(STREAM_TYPE_THERMAL, raw16_mem, new_frame_child, logging_queue)
                elif stream_type == STREAM_TYPE_VISIBLE:
                    tc.start(STREAM_TYPE_VISIBLE, vis_mem, new_frame_child, logging_queue)

            # Send status
            node.send_status([], 69.0, 300)

            if running:
                # Grab frame
                ret, frame = vid.read()
                if not ret: raise KeyboardInterrupt

                if stream_type == "visible":
                    # Reshape frame to resemble raw thermal video
                    frame = cv2.resize(frame, (640, 480))

                    # Write frame to shared memory
                    vis_mem.get_lock().acquire(timeout=0.5)
                    np.copyto(visible_dst, frame.astype("uint8"))
                    vis_mem.get_lock().release()
                    new_frame_parent.set()
                
                elif stream_type == "thermal":
                    # Reshape frame to resemble raw thermal video
                    frame = cv2.resize(frame, (160, 120))
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

                    # Write frame to shared memory
                    raw16_mem.get_lock().acquire(timeout=0.5)
                    np.copyto(thermal_dst, frame.astype("uint16"))
                    raw16_mem.get_lock().release()
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
                
                stream_type = node.livestream_type
                print(stream_type)
                if stream_type == STREAM_TYPE_THERMAL:
                    tc.start(STREAM_TYPE_THERMAL, raw16_mem, new_frame_child, logging_queue)
                elif stream_type == STREAM_TYPE_VISIBLE:
                    tc.start(STREAM_TYPE_VISIBLE, vis_mem, new_frame_child, logging_queue)
            
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
