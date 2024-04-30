"""Combined test of user and cooking detection (without node.js, no livestreaming, no HW alarm)"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

# Muliprocessing stuff
from constants import VISIBLE_SHAPE, RAW_THERMAL_SHAPE
from multiprocessing import shared_memory, Lock, Queue
from cooking_detection import CookingDetect
from lepton.polling import PureThermal
from state_machine import StateMachine
from user_detection import UserDetect
from misc import NewFrameEvent
from arducam import Arducam
import numpy as np

# Debugging stuff
from misc.monitor import MonitorClient
from misc.logs import *
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

    # Create image arrays in shared memory
    vis_bytes = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8').nbytes
    vis_mem = shared_memory.SharedMemory(create=True, size=vis_bytes)

    # Create image array in shared memory
    raw16_bytes = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16').nbytes
    raw16_mem = shared_memory.SharedMemory(create=True, size=raw16_bytes)

    # Create lock objects for shared memory
    vis_mem_lock   = Lock()
    raw16_mem_lock = Lock()

    # Create master event object for new frames
    vis_frame_parent   = NewFrameEvent()
    raw16_frame_parent = NewFrameEvent()

    # Get a different child event for each process that reads frame data
    vis_frame_child   = vis_frame_parent.get_child()
    raw16_frame_child = raw16_frame_parent.get_child()

    # Instantiate launchers
    arducam_proc        = Arducam()
    purethermal_proc    = PureThermal()
    user_detect_proc    = UserDetect()
    cooking_detect_proc = CookingDetect()

    # Pass launchers and their arguments to the main state machine
    state_machine = StateMachine(
        arducam=arducam_proc,
        arducam_args=(
            vis_mem, 
            vis_mem_lock,
            vis_frame_parent,
            logging_queue
        ),

        purethermal=purethermal_proc,
        purethermal_args=(
            raw16_mem,
            raw16_mem_lock,
            raw16_frame_parent,
            logging_queue
        ),

        user_detect=user_detect_proc,
        user_detect_args=(
            vis_mem,
            vis_mem_lock,
            vis_frame_child,
            logging_queue
        ),

        cooking_detect=cooking_detect_proc,
        cooking_detect_args=(
            raw16_mem,
            raw16_mem_lock,
            raw16_frame_child,
            logging_queue
        )
    )

    # Instantiate debug monitors
    user_monitor = MonitorClient(12346)
    cv2.namedWindow("User Detection", cv2.WINDOW_NORMAL)

    cooking_monitor = MonitorClient(12347)
    cv2.namedWindow("Cooking Detection", cv2.WINDOW_NORMAL)

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

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
        
        # Deallocate memory
        vis_mem.close()
        vis_mem.unlink()

        raw16_mem.close()
        raw16_mem.unlink()

        # Shut down monitor windows
        user_monitor.stop()
        cooking_monitor.stop()
        cv2.destroyAllWindows()

        # Shut down loggers
        logging_thread.stop()
        logger.info("test ended")



# Start main program
if __name__ == '__main__':
    main()
