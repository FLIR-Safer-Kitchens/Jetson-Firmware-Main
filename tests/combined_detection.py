"""Combined test of user and cooking detection"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

# Muliprocessing stuff
from constants import VISIBLE_SHAPE, RAW_THERMAL_SHAPE, STREAM_TYPE_VISIBLE, STREAM_TYPE_THERMAL
from state_machine import StateMachine, WorkerProcess
from misc.frame_event import NewFrameEvent
from multiprocessing import Array, Queue
from ctypes import c_uint8, c_uint16
import numpy as np

# Debugging stuff
from misc.monitor import MonitorClient
from misc.logs import *
import logging
import cv2

# Switch between stubs and real modules
from misc.alarm import AlarmBoard
# from stubs import AlarmBoard

from misc.node_server import NodeServer
# from stubs.node_server_basic import NodeServer
# from stubs.node_server_full import NodeServer

from arducam import Arducam
# from stubs import Arducam

from lepton.polling import PureThermal
# from stubs import PureThermal

from user_detection import UserDetect
# from stubs import UserDetect

from cooking_detection import CookingDetect
# from stubs import CookingDetect

from streaming import Transcoder
# from stubs import Transcoder



def main():
    # Configure logger
    configure_main_log(False, True)

    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create queue for workers to log to
    logging_queue = Queue(10)

    # Create visible image array in shared memory
    vis_bytes = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8').nbytes
    vis_mem = Array(c_uint8, vis_bytes, lock=True)
    
    # Create thermal image array in shared memory
    raw16_bytes = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16').nbytes
    raw16_mem = Array(c_uint16, raw16_bytes, lock=True)

    # Create master event object for new frames
    vis_frame_parent   = NewFrameEvent()
    raw16_frame_parent = NewFrameEvent()

    # Get a different child event for each process that reads frame data
    user_det_frame_event    = vis_frame_parent.get_child()
    cooking_det_frame_event = raw16_frame_parent.get_child()
    thermal_stream_frame_event = raw16_frame_parent.get_child()
    visible_stream_frame_event = vis_frame_parent.get_child()

    # Instantiate alarm board
    alarm = AlarmBoard()

    # Instantiate node.js server
    node = NodeServer()

    # Instantiate launchers
    arducam_proc        = Arducam()
    purethermal_proc    = PureThermal()
    user_detect_proc    = UserDetect()
    cooking_detect_proc = CookingDetect()
    livestream_proc     = Transcoder()

    # Pass launchers and their arguments to the main state machine
    state_machine = StateMachine(
        node_server=node,
        alarm_board=alarm,
        arducam=WorkerProcess(
            name="Arducam",
            launcher=arducam_proc,
            start_args=(
                vis_mem,
                vis_frame_parent,
                logging_queue
            )
        ),
        purethermal=WorkerProcess(
            name="PureThermal",
            launcher=purethermal_proc,
            start_args=(
                raw16_mem,
                raw16_frame_parent,
                logging_queue
            )
        ),
        user_detect=WorkerProcess(
            name="User Detection",
            launcher=user_detect_proc,
            start_args=(
                vis_mem,
                user_det_frame_event,
                logging_queue
            )
        ),
        cooking_detect=WorkerProcess(
            name="Cooking Detection",
            launcher=cooking_detect_proc,
            start_args=(
                raw16_mem,
                cooking_det_frame_event,
                logging_queue
            )
        ),
        thermal_stream=WorkerProcess(
            name="Thermal Livestream",
            launcher=livestream_proc,
            start_args=(
                STREAM_TYPE_THERMAL,
                raw16_mem,
                thermal_stream_frame_event,
                logging_queue
            )
        ),
        visible_stream=WorkerProcess(
            name="Visible Livestream",
            launcher=livestream_proc,
            start_args=(
                STREAM_TYPE_VISIBLE,
                vis_mem,
                visible_stream_frame_event,
                logging_queue
            )
        )
    )

    # Instantiate debug monitors
    user_monitor = MonitorClient(12346)
    user_detect_proc.streaming_ports.append(12346)
    cv2.namedWindow("User Detection", cv2.WINDOW_NORMAL)

    cooking_monitor = MonitorClient(12347)
    cooking_detect_proc.streaming_ports.append(12347)
    cv2.namedWindow("Cooking Detection", cv2.WINDOW_NORMAL)

    lepton_monitor = MonitorClient(12348)
    purethermal_proc.streaming_ports.append(12348)
    cv2.namedWindow("Lepton View", cv2.WINDOW_NORMAL)

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        # Establish alarm board connection
        alarm.connect()

        # Establish node.js server connection
        node.connect()

        # Initialize the state machine
        running = state_machine.update()
        assert running, "Initialization failed"

        while running:
            # Check log listener status
            if not logging_thread.running():
                logger.warning("Log listener died. Restarting...")
                logging_thread.start()

            # Update the system state
            running = state_machine.update()

            # Display debug monitor outputs
            ret, monitor_frame = user_monitor.read()
            if ret: cv2.imshow("User Detection", monitor_frame)

            ret, monitor_frame = cooking_monitor.read()
            if ret: cv2.imshow("Cooking Detection", monitor_frame)

            ret, monitor_frame = lepton_monitor.read()
            if ret: cv2.imshow("Lepton View", monitor_frame)

            # Delay
            if cv2.waitKey(50) ^ 0xff == ord('q'):
                raise KeyboardInterrupt

    except KeyboardInterrupt:
        logger.info("quitting")
    except:
        logger.exception("")
    
    # Shutdown procedure
    finally:
        # Stop all workers
        arducam_proc.stop()
        purethermal_proc.stop()
        user_detect_proc.stop()
        cooking_detect_proc.stop()
        livestream_proc.stop()

        # Shut down node server connection
        node.disconnect()

        # Close alarm board connection
        alarm.stopAlarm()
        alarm.disconnect()

        # Shut down monitor windows
        user_monitor.stop()
        cooking_monitor.stop()
        lepton_monitor.stop()
        cv2.destroyAllWindows()

        # Shut down loggers
        logging_thread.stop()
        logger.info("test ended")


# Start main program
if __name__ == '__main__':
    main()
