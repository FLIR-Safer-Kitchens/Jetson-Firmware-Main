"""
Debug monitor for multiprocessing subprocesses.\n
Linux doesn't like when you try to open windows in child processes.\n
My workaround is to stream frames over UDP and display them in the main process
"""

import numpy as np
import socket
import select
import cv2

# Maximum UDP packet size
BUFF_SIZE = 65507

# JPEG start/end markers
START_MARKER = b'\xFF\xD8'  
END_MARKER   = b'\xFF\xD9'


class MonitorServer:
    """Transmits image data to client monitor(s) via UDP"""

    def __init__(self, udp_port):
        self.port = udp_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def show(self, frame, quality=80):
        """
        Transmit frame via UDP socket

        Parameters:
        - frame (np.ndarray): The frame to be transmitted
        - quality (int): JPEG compression quality. Must be low enough to send the entire image in one UDP transaction
        """

        # Encode and convert frame to bytes
        # TODO: bit jank having a fixed compression level
        frame_bytes = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes() 
        assert len(frame_bytes) < BUFF_SIZE, "Image too large after compression, choose a lower quality"
        
        # Transmit bytes
        n_sent = self.sock.sendto(frame_bytes, ('127.0.0.1', self.port))
        assert n_sent == len(frame_bytes), "Transmission failed"

    def stop(self):
        """Close the UDP socket"""
        self.sock.close()



class MonitorClient:
    """Receives image data from a MonitorServer via UDP"""

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
        # Get newest UDP packet
        try:
            frame_data = None
            while True:
                frame_data = self.sock.recvfrom(BUFF_SIZE)[0]
        except BlockingIOError:
            pass
        
        # Check if we got any frames
        if frame_data == None:
            return False, None

        if (START_MARKER in frame_data) and (END_MARKER in frame_data):
            # Get start and end of image
            start_idx = frame_data.index(START_MARKER)
            end_idx   = frame_data.index(END_MARKER) + len(END_MARKER)

            # Convert bytes to numpy array
            frame_bytes = np.frombuffer(frame_data[start_idx:end_idx], dtype=np.uint8)
                
            # Decode frame
            frame = cv2.imdecode(frame_bytes, flags=cv2.IMREAD_UNCHANGED)
            return type(frame) == np.ndarray, frame
            
        else: return None, False
    
    def stop(self):
        """Close the UDP socket"""
        self.sock.close()
