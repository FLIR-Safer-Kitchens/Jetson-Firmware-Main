"""User detection testbench"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Queue
from user_detection import UserDetect
from constants import VISIBLE_SHAPE
from misc import BroadcastEvent
from arducam import Arducam
from misc.logs import *
import numpy as np
import cv2


def main():
    # Configure logger
    configure_main(False, True)

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

    # Create dummy window
    cv2.namedWindow("control", cv2.WINDOW_NORMAL)

    try:
        # Start thread to emit worker log messages
        logging_thread = QueueListener(logging_queue)
        logging_thread.start()

        running = False
        while True:
            # Check worker status
            if (user.running() != running) or (cam.running() != running):
                raise ValueError(f"Expected {running}, {running}. Got {user.running()}, {cam.running()}.")
            
            # Print when detection state changes
            old = detected
            detected = user.last_detected.value
            if detected and not old: print("User Detected")
            elif old and not detected: print("User No Longer Detected")

            # Handle commands
            k = cv2.waitKey(10)
            if k == ord('p'):
                print("stopping workers")
                running = False
                user.stop()
                cam.stop()
            
            elif k == ord('s'):
                print("starting worker")
                running = True
                cam.start(mem, mem_lock, new_frame_parent, logging_queue)
                user.start(mem, mem_lock, new_frame_child, logging_queue)
                
            elif k == ord('q'):
                print("quitting")
                raise KeyboardInterrupt

    except:
        user.stop()
        cam.stop()
        
        mem.close()
        mem.unlink()

        logging_thread.stop()
        raise


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
