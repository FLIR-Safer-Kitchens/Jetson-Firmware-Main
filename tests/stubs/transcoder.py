"""Transcoder launcher"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', 'tests')))

from constants import FFMPEG_RTSP_PORT, FFMPEG_RTSP_URL
from stubs import Launcher
import threading
import logging
import time

SOCKET_PORT = 15696


def worker(stop, stream_type, mem, frame_event, log_queue):
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

        # Compute RTSP directory to give to node server
        self.rtsp_url = f'rtsp://127.0.0.1:{FFMPEG_RTSP_PORT}/{FFMPEG_RTSP_URL}'

        # Frame reading worker
        self.stop_sig1 = threading.Event()
        self.thread1 = None


    def start(self, stream_type, mem, frame_event, log_queue):
        """
        Start the transcoder worker
        """
        if self.thread1 == None:
            self.stop_sig1.clear()
            self.thread1 = threading.Thread(target=worker, args=(self.stop_sig1, stream_type, mem, frame_event, log_queue), daemon=True)
            self.thread1.start()

        super().start(None, None)


    def stop(self):
        if self.thread1 != None:
            self.stop_sig1.set()
            self.thread1.join(timeout=1)
            self.thread1 = None

        super().stop()
