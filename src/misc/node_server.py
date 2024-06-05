"""A class for communicating with the Node.js server that handles the app interface"""

from constants import NODE_SERVER_PORT, STATUS_REPORT_PERIOD, STREAM_TYPE_THERMAL, STREAM_TYPE_VISIBLE
import threading
import socketio
import logging
import time


class NodeServer:
    """A class for communicating with the Node.js server that handles app communication"""
    
    def __init__(self):
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        # Client socket
        self._sock = socketio.Client()

        # Server outputs
        self.configured      = False
        self.livestream_on   = False
        self.livestream_type = STREAM_TYPE_THERMAL
        self.alarm_on        = False

        # Define message callback
        self._sock.on("status", self.handle_message)

        # Thread for the socket.io wait loop
        self._thread = None

        # Timestamp of last status message
        self.last_status_ts = 0



    def connect(self, port=NODE_SERVER_PORT):
        """
        Connect to the node.js server

        Parameters:
        - port (int): The local port number of the node.js server
        """
        # Establish server connection
        self.logger.debug("Connecting to node.js server")
        self._sock.connect(f"http://localhost:{port}")
        assert self._sock.connected
        self.logger.debug("Successfully connected to node.js server")

        # Start the waiting loop in a new thread
        self._thread = threading.Thread(target=self._sock.wait, daemon=True)
        self._thread.start()


    def disconnect(self):
        """Disconnect from the node.js server"""
        self._sock.disconnect()

        # Stop the waiting thread
        if self._thread is not None:
            self._thread.join()
            self._thread = None


    def send_status(self, cooking_coords, max_temp, unattended_time):
        """
        Send a status packet to the node.js server

        Parameters:
        - burner_coords (multiprocessing.Array): Coordinates (x, y) of cooking blob centroids
        - max_temp (float): Maximum temperature in celsius detected in the thermal image
        - unattended_time (int): The time in seconds since the user was last seen
        """
        # Enforce status report cooldown
        if (time.time() - self.last_status_ts) < STATUS_REPORT_PERIOD: return
        else: self.last_status_ts = time.time()
        
        # Send status packet
        status = {
            'burnersOn'    : cooking_coords, 
            'maxTemp'      : max_temp, 
            'userLastSeen' : unattended_time
        }

        self.logger.debug(str(status))
        self._sock.emit('status', status)


    def handle_message(self, data):
        """
        Recieve control flags from node.js server
        
        Parameters:
        - data (dict): Dict of control flags from node server
        """
        self.logger.debug(f"Received data from server: {data}")

        # Parse data, update variables
        if "setupComplete" in data: 
            self.configured = bool(data["setupComplete"])
        if "liveStreamOn" in data: 
            self.livestream_on = bool(data["liveStreamOn"])
        if "liveStreamType" in data:
            stream_type = str(data["liveStreamType"]).strip()
            if stream_type == "thermal": self.livestream_type = STREAM_TYPE_THERMAL
            if stream_type == "visible": self.livestream_type = STREAM_TYPE_VISIBLE
        if "alarmOn" in data: 
            self.alarm_on = bool(data["alarmOn"])
