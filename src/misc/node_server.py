"""A class for communicating with the Node.js server that handles the app interface"""

from constants import NODE_SERVER_PORT
import threading
import socketio


class NodeServer:
    """A class for communicating with the Node.js server that handles app communication"""
    
    def __init__(self):
        # Client socket
        self._sock = socketio.Client()

        # Server outputs
        self.configured    = False
        self.livestream_on = False
        self.alarm_on      = False

        # Define message callback
        self._sock.on("status", self.handle_message)

        # Thread for the socket.io wait loop
        self._thread = None


    def connect(self, port=NODE_SERVER_PORT):
        """
        Connect to the node.js server

        Parameters:
        - port (int): The local port number of the node.js server
        """
        # Establish server connection
        self._sock.connect(f"http://localhost:{port}")
        assert self._sock.connected

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
        status = {
            'burnersOn'    : cooking_coords, 
            'maxTemp'      : max_temp, 
            'userLastSeen' : unattended_time
        }
        self._sock.emit('status', status)


    def handle_message(self, data):
        """
        Recieve control flags from node.js server
        
        Parameters:
        - data (dict): Dict of control flags from node server
        """
        # Parse data, update variables
        if "setupComplete" in data: 
            self.configured = bool(data["setupComplete"])
        if "liveStreamOn" in data: 
            self.livestream_on = bool(data["liveStreamOn"])
        if "alarmOn" in data: 
            self.alarm_on = bool(data["alarmOn"])
