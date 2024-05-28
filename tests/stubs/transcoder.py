"""Transcoder launcher"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', 'tests')))

from constants import HLS_DIRECTORY, HLS_M3U8_FILENAME
from stubs import Launcher
import threading
import logging
import time
import os

SOCKET_PORT = 15696


def worker(stop, raw16_mem, frame_event, log_queue):
    getting_frames = False
    last_frame = 0

    while not stop.is_set():
        if getting_frames and (time.time() - last_frame) > 2:
            print("Transcoder no longer getting frames")
            getting_frames = False
        if not getting_frames and (time.time() - last_frame) < 1:
            print("Transcoder getting frames")
            getting_frames = True

        # Wait for new frame
        if not frame_event.wait(timeout=0.5): continue
        else: frame_event.clear()

        last_frame = time.time()


class Transcoder(Launcher):
    """Class for managing the process that generates a colorized HLS stream from raw thermal frames"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.warning("I'M JUST A STUB")

        # Compute .m3u8 directory to give to node server
        module_path = os.path.dirname(__file__)
        self.m3u8_path = os.path.join(module_path, HLS_DIRECTORY, HLS_M3U8_FILENAME)
        self.m3u8_path = os.path.normpath(self.m3u8_path)

        # Frame reading worker
        self.stop_sig1 = threading.Event()
        self.thread1 = None


    def start(self, raw16_mem, frame_event, log_queue):
        """
        Start the transcoder worker

        Parameters:
        - vis_mem (multiprocessing.Array): Shared memory location of visible camera data
        - frame_event (NewFrameConsumer): Flag that indicates when a new frame is available
        - log_queue (multiprocessing.Queue): Queue used to transfer log records from a subrocess to the main process
        """
        if self.thread1 == None:
            self.stop_sig1.clear()
            self.thread1 = threading.Thread(target=worker, args=(self.stop_sig1, raw16_mem, frame_event, log_queue), daemon=True)
            self.thread1.start()

        super().start(None, None)


    def stop(self):
        if self.thread1 != None:
            self.stop_sig1.set()
            self.thread1.join(timeout=1)
            self.thread1 = None

        super().stop()
