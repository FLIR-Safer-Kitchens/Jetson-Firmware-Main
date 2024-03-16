"""Cooking detection testbench (.tiff input)"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

from multiprocessing import shared_memory, Lock, Event
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

    # Create event object for new frames
    new_frame = Event()

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=mem.buf)

    # Instantiate launcher
    cd = CookingDetect()

    # Cooking state 
    detected = False

    cv2.namedWindow("dummy",cv2.WINDOW_NORMAL)

    # Load lepton video
    vid = Raw16Video(path.normpath(path.join(path.dirname(path.abspath(__file__)), 'vids', "Lepton_Capture_6.tiff")))

    try:
        running = False
        while True:
            if cd.running() != running:
                raise ValueError(f"Expected {running}. Got {cd.running()}.")

            if running:
                # Grab frame
                ret, frame = vid.read()
                if not ret: 
                    raise ValueError("Bad frame")

                # Write frame to shared memory
                mem_lock.acquire(block=True)
                np.copyto(frame_dst, frame)
                mem_lock.release()
                new_frame.set()

                # Print when detection state changes
                old = detected
                detected = cd.cooking_detected.value
                if detected and not old: print("Cooking Detected")
                elif old and not detected: print("Cooking No Longer Detected")
            
            # Controls
            k = cv2.waitKey(50)
            if k == ord('p'):
                print("stopping worker")
                running = False
                cd.stop()
                new_frame.clear()
            elif k == ord('s'):
                print("starting worker")
                running = True
                cd.start(mem, mem_lock, new_frame)
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
