"""
Debug monitor for multiprocessing subprocesses.\n
Linux doesn't like when you try to open windows in child processes.\n
My workaround is to stream frames over UDP and display them in the main process
"""

import numpy as np
import threading
import socket
import cv2

# Maximum UDP packet size
MAX_UDP_PACKET_SIZE = 65507

# JPEG start/end markers
START_MARKER = b'\xFF\xD8'
END_MARKER   = b'\xFF\xD9'


class MonitorServer:
    """Transmits image data via UDP"""

    def __init__(self, quality=100, packet_sz=MAX_UDP_PACKET_SIZE):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # UDP packet size
        self._packet_sz = packet_sz

        # Target and actual JPEG quality
        self._target_quality = quality
        self._quality = self._target_quality
        
        # Try to increase quality when frame count hits thresh
        self._quality_increase_frame_thresh = 20 
        self._quality_increase_frame_count = 0


    def show(self, frame, *ports):
        """
        Transmit frame via UDP socket

        Parameters:
        - frame (np.ndarray): The frame to be transmitted
        - ports (int): Ports to send frame data to

        Returns (int):
        -  0: transmission successful
        - -1: OpenCV couldn't encode the image to JPEG
        - -2: Image could not be comressed small enough
        - -3: Socket raised an error when transmitting
        """
        while self._quality > 0:
            # Encode and convert frame to bytes
            ret, frame_bytes = cv2.imencode(
                ext = '.jpg', 
                img = frame, 
                params = [cv2.IMWRITE_JPEG_QUALITY, self._quality])
            
            if not ret: return -1
            else: frame_bytes = frame_bytes.tobytes()

            # Reduce quality if needed
            if len(frame_bytes) > self._packet_sz:
                self._quality -= 5
                continue
            
            # Attempt to re-increase quality over time
            elif self._quality < self._target_quality:
                self._quality_increase_frame_count += 1

                if self._quality_increase_frame_count >= self._quality_increase_frame_thresh:
                    self._quality_increase_frame_count = 0
                    self._quality += 5
            
            break
        
        # Could not compress image enough
        else: return -2

        # Transmit bytes
        for port in ports:
            try: 
                n_sent = self.sock.sendto(frame_bytes, ('127.0.0.1', port))
                assert n_sent == len(frame_bytes)
            except (OSError, AssertionError):
                return -3
        
        return 0


    def stop(self):
        """Close the UDP socket"""
        self.sock.close()



class MonitorClient:
    """Receives image data via UDP"""

    def __init__(self, udp_port):
        # Create socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)

        # Bind socket to host/port
        self.sock.bind(('127.0.0.1', udp_port))

    def read(self):
        """
        Attempt to read a frame from the UDP socket\n
        Returns (tuple (bool, np.ndarray)): Similar interface to VideoCapture.read(); boolean indicates whether data is valid, followed by frame data (if valid)
        """
        return read_udp_jpeg(self.sock)

    def stop(self):
        """Close the UDP socket"""
        self.sock.close()



class RecordingClient:
    """Receives image data via UDP and writes to a video"""

    def __init__(self, udp_port, filename, fourcc="mp4v", fps=15, frame_size=(640, 480), color=True):
        # Create socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setblocking(False)

        # Bind socket to host/port
        self.sock.bind(('127.0.0.1', udp_port))

        # Create VideoWriter object
        self.writer = cv2.VideoWriter(
			filename=filename,
			apiPreference=cv2.CAP_FFMPEG,
			fourcc=cv2.VideoWriter_fourcc(*fourcc),
			fps=fps,
			frameSize=frame_size,
			params=[cv2.VIDEOWRITER_PROP_IS_COLOR, int(color)],
		)
        assert self.writer.isOpened()

        # Recording thread
        self._thread = None
        self.suspend_sig = threading.Event()


    def start(self):
        """Starts the recording thread"""
        if self._thread == None:
            self.suspend_sig.clear()
            self._thread = threading.Thread(target=self._record, daemon=True)
            self._thread.start()


    def _record(self):
        """Continuously reads frames from the UDP socket and writes to video file"""
        while not self.suspend_sig.is_set():
            ret, frame = read_udp_jpeg(self.sock)
            if ret:
                self.writer.write(frame)


    def stop(self):
        """Stop the recording thread. Close the UDP socket and video writer"""

        # Stop the recording thread
        if hasattr(self._thread, "is_alive") and self._thread.is_alive():
            self.suspend_sig.set()
            self._thread.join(1)
            self._thread = None

        # Close socket and video writer
        self.sock.close()
        self.writer.release()



def read_udp_jpeg(sock, packet_sz=MAX_UDP_PACKET_SIZE):
    """
    Reads a JPEG-encoded image from UDP.\n
    Supports reading at a lower rate than incoming data.

    Parameters:
    - sock (socket.socket): The UDP socket to read from. Must be non-blocking
    - packet_sz (int): Maximum number of bytes to read from socket at a time
    
    Returns (tuple (bool, np.ndarray)): Similar interface to VideoCapture.read(); boolean indicates whether data is valid, followed by frame data (if valid)
    """
    try:
        frame_data = None
        while True:
            # Get newest UDP packet
            frame_data = sock.recvfrom(packet_sz)[0]
    except BlockingIOError:
        if type(frame_data) != bytes:
            return False, None

    try:
        # Get start and end of image
        start_idx = frame_data.rindex(START_MARKER)
        end_idx   = frame_data.index(END_MARKER, start_idx) + len(END_MARKER)
    except ValueError:
        return False, None

    # Convert bytes to numpy array
    frame_bytes = np.frombuffer(frame_data[start_idx:end_idx], dtype=np.uint8)

    try:
        # Decode frame
        frame = cv2.imdecode(frame_bytes, flags=cv2.IMREAD_UNCHANGED)
        return type(frame) == np.ndarray, frame
    except cv2.error:
        return False, None
