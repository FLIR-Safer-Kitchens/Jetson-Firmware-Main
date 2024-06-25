# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from misc.monitor import MonitorClient
from ctypes import c_uint8, c_uint16
from constants import *
from misc.logs import *
import numpy as np
import logging
import cv2

# from misc.node_server import NodeServer
# from stubs.node_server_basic import NodeServer
from stubs.node_server_full import NodeServer

# from arducam import Arducam
from stubs.arducam_random import Arducam
# from stubs.arducam_webcam import Arducam

# from lepton.polling import PureThermal
from stubs.lepton import PureThermal


def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(40)

    # Create image array in shared memory
    thermal_bytes = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16').nbytes
    raw16_mem = Array(c_uint16, thermal_bytes, lock=True)

    # Create image array in shared memory
    visible_bytes = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8').nbytes
    vis_mem = Array(c_uint8, visible_bytes, lock=True)

    # Create master event object for new frames
    vis_frame_parent = NewFrameEvent()
    lep_frame_parent = NewFrameEvent()

    # Create node server object
    node = NodeServer()

    # Create camera objects
    vis = Arducam()
    lep = PureThermal()

    # Streaming
    STREAM_UDP_PORT = 12444
    monitor = MonitorClient(STREAM_UDP_PORT)
    cv2.namedWindow("stream", cv2.WINDOW_NORMAL)

    # State variables
    running = False
    stream_type = "thermal"

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        # Connect to node server
        node.connect()
        
        while True:
            # Check log listener status
            if not logging_thread.running():
                logger.warning("Log listener died. Restarting...")
                logging_thread.start()

            # Send status
            node.send_status([], lep.max_temp.value, 300)

            if running:
                # Check camera polling processes
                if stream_type == "visible" and not vis.running():
                    ret = vis.handle_exceptions()
                    assert ret, "Arducam polling process not recoverable"
                    logger.warning("Attempting to restart arducam polling process")
                    vis.start(vis_mem, vis_frame_parent, logging_queue)
                    
                elif stream_type == "thermal" and not lep.running():
                    ret = lep.handle_exceptions()
                    assert ret, "Lepton polling process not recoverable"
                    logger.warning("Attempting to restart lepton polling process")
                    lep.start(raw16_mem, lep_frame_parent, logging_queue)

                # Read from monitor
                ret, frame = monitor.read()
                if not ret: continue
                cv2.imshow("stream", frame)

            # Stop livestream
            if running and not node.livestream_on:
                logger.info("stopping worker")
                running = False

                if stream_type == "visible":
                    vis.stop()
                    idx = vis.streaming_ports.index(STREAM_UDP_PORT)
                    vis.streaming_ports.pop(idx)
                elif stream_type == "thermal":
                    lep.stop()
                    idx = lep.streaming_ports.index(STREAM_UDP_PORT)
                    lep.streaming_ports.pop(idx)
            
            # Start livestream
            elif not running and node.livestream_on:
                logger.info("starting worker")
                running = True
                
                stream_type = node.livestream_type
                print(stream_type)
                if stream_type == STREAM_TYPE_THERMAL:
                    lep.start(raw16_mem, lep_frame_parent, logging_queue)
                    lep.streaming_ports.append(STREAM_UDP_PORT)
                elif stream_type == STREAM_TYPE_VISIBLE:
                    vis.start(vis_mem, vis_frame_parent, logging_queue)
                    vis.streaming_ports.append(STREAM_UDP_PORT)
            
            # Update the running flag or exit
            if cv2.waitKey(10) & 0xFF == ord('q'):
                raise KeyboardInterrupt
    
    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    finally:
        vis.stop()
        lep.stop()
        node.disconnect()
        monitor.stop()
        logging_thread.stop()
        cv2.destroyAllWindows()
        logger.info("test ended")


if __name__ == '__main__':
    main()
