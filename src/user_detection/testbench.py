"""User detection testbench. Move to src/ when testing"""

from multiprocessing import shared_memory, Lock
from constants import VISIBLE_SHAPE
from user_detection import UserDetect
import numpy as np
import logging
import time
import cv2


def main():
    # Configure logger
    logging.basicConfig(level=logging.DEBUG)

    # Create array for us to copy to
    frame = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8')

    # Create image array in shared memory
    mem = shared_memory.SharedMemory(create=True, size=frame.nbytes)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

    # Instantiate worker launcher
    ud = UserDetect()

    # Create video capture object
    vidcap = cv2.VideoCapture(0)
    assert vidcap.isOpened()

    # Create window
    cv2.namedWindow("main", cv2.WINDOW_NORMAL)
    
    try:
        running = False
        while True:
            if ud.running() != running:
                raise ValueError(f"Expected {running}. Got {ud.running()}.")

            # Grab frame
            ret, frame = vidcap.read()
            if not ret: 
                print("Bad frame")
                continue

            # Process frame
            frame.resize(VISIBLE_SHAPE)

            # Write frame to shared memory
            mem_lock.acquire(block=True)
            np.copyto(frame_dst, frame)
            mem_lock.release()
            
            # Show reference
            cv2.imshow("main", frame)
            k = cv2.waitKey(10)
            if k == ord('p'):
                print("stopping worker")
                running = False
                ud.stop()
            elif k == ord('s'):
                print("starting worker")
                print(ud.last_detected, time.time())
                running = True
                ud.start(mem, mem_lock)
            elif k == ord('q'):
                print("quitting")
                raise KeyboardInterrupt

    except:
        ud.stop()       
        mem.close()
        mem.unlink()
        raise


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
    