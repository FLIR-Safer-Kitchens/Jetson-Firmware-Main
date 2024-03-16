"""Cooking detection testbench (.tiff input)"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock
from cooking_detection import CookingDetect
from constants import RAW_THERMAL_SHAPE
from lepton.vid_file import Raw16Video
import numpy as np
import logging
import cv2


def main():
    # Configure logger
    logging.basicConfig(level=logging.DEBUG)

    # Create array for us to copy to
    frame = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16')

    # Create image array in shared memory
    mem = shared_memory.SharedMemory(create=True, size=frame.nbytes)

    # Create lock object for shared memory
    mem_lock = Lock()

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

    # Instantiate launcher
    cd = CookingDetect()

    cv2.namedWindow("dummy",cv2.WINDOW_NORMAL)

    # Load lepton video
    vid = Raw16Video(path.normpath(path.join(path.dirname(path.abspath(__file__)), 'vids', "Lepton_Capture_5.tiff")))

    try:
        running = False
        while True:
            if cd.running() != running:
                raise ValueError(f"Expected {running}. Got {cd.running()}.")

            # Grab frame
            ret, frame = vid.read()
            if not ret: 
                raise ValueError("Bad frame")

            # Write frame to shared memory
            mem_lock.acquire(block=True)
            np.copyto(frame_dst, frame)

            k = cv2.waitKey(50)
            mem_lock.release()
            
            if k == ord('p'):
                print("stopping worker")
                running = False
                cd.stop()
            elif k == ord('s'):
                print("starting worker")
                running = True
                cd.start(mem, mem_lock)
            elif k == ord('q'):
                print("quitting")
                raise KeyboardInterrupt

    except:
        cd.stop()       
        mem.close()
        mem.unlink()
        raise


if __name__ == '__main__':
    main()
    cv2.destroyAllWindows()
    