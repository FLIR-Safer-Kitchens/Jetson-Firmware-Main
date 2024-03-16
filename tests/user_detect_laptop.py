"""User detection testbench"""

# Add parent directory to the Python path
import os, sys
sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Event
from user_detection import UserDetect
from constants import VISIBLE_SHAPE
from arducam import Arducam
import numpy as np
import logging
import cv2


def main():
    # Configure logger
    logging.basicConfig(level=logging.DEBUG)

    # Create image array in shared memory
    dummy = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8')
    mem = shared_memory.SharedMemory(create=True, size=dummy.nbytes)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create event object for new frames
    new_frame = Event()

    # Instantiate launchers
    user = UserDetect()
    cam  = Arducam()

    # User detection output
    detected = False

    # Create dummy window
    cv2.namedWindow("control", cv2.WINDOW_NORMAL)

    try:
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

            # Show reference
            k = cv2.waitKey(10)
            if k == ord('p'):
                print("stopping workers")
                running = False
                user.stop()
                cam.stop()
            
            elif k == ord('s'):
                print("starting worker")
                running = True
                cam.start(mem, mem_lock, new_frame)
                user.start(mem, mem_lock, new_frame)
                
            elif k == ord('q'):
                print("quitting")
                raise KeyboardInterrupt

    except:
        user.stop()
        cam.stop()
        
        mem.close()
        mem.unlink()
        raise


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
