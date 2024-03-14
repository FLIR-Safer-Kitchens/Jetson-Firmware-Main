"""Cooking detection testbench. Move to src/ when testing"""

from multiprocessing import shared_memory, Lock
from constants import RAW_THERMAL_SHAPE
from cooking_detection import CookingDetect
import numpy as np
from lepton.vid_file import Raw16Video
import logging
import time
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
    ud = CookingDetect()

    cv2.namedWindow("dummy",cv2.WINDOW_NORMAL)

    # Load lepton video
    vid = Raw16Video("C:/Users/sdhla/Documents/GitHub/Capstone/Jetson-Firmware-Main/src/cooking_detection/vids/Lepton_Capture_6.tiff")

    try:
        running = False
        while True:
            if ud.running() != running:
                raise ValueError(f"Expected {running}. Got {ud.running()}.")

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
                ud.stop()
            elif k == ord('s'):
                print("starting worker")
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
    