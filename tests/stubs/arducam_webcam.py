"""Arducam polling launcher"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))

from misc.monitor import MonitorServer
from stubs.launcher import Launcher
from constants import VISIBLE_SHAPE
import numpy as np
import threading
import logging
import time
import cv2


def worker(stop, vis_mem, frame_event, ports):

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=vis_mem.get_obj())

    # Create monitor server
    monitor = MonitorServer()

    # Open webcam
    cap = cv2.VideoCapture(0)
    assert cap.isOpened()

    while not stop.is_set():
        start = time.time()
        ret, frame = cap.read()
        if not ret: continue

        if not vis_mem.get_lock().acquire(timeout=0.5): continue
        np.copyto(frame_dst, frame)
        vis_mem.get_lock().release()

        # Set new frame flag
        frame_event.set()
        time.sleep(max(0, 1/30 - (time.time()-start)))

        # Stream to UDP
        if len(ports):
            monitor.show(frame, *ports)

    monitor.stop()
    cap.release()
    frame_event.clear()



class Arducam(Launcher):
    """Class for managing the arducam polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        self.logger.warning("I'M JUST A STUB!")

        self.thread = None
        self.stop_sig = threading.Event()


    def start(self, vis_mem, frame_event, log_queue):
        """
        Start the arducam polling worker

        Parameters:
        - vis_mem (multiprocessing.Array): Shared memory location of visible camera data
        - frame_event (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
        - log_queue (multiprocessing.Queue): Queue to handle log messages
        """
        if self.thread == None:
            self.stop_sig.clear()
            self.thread = threading.Thread(target=worker, args=(self.stop_sig, vis_mem, frame_event, self.streaming_ports), daemon=True)
            self.thread.start()

        super().start(None, None)

    def stop(self):
        if self.thread != None:
            self.stop_sig.set()
            self.thread.join(timeout=1)
            self.thread = None

        super().stop()
