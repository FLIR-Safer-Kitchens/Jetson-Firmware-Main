"""
Note: Run this .py file before attempting to use the stub

Basic version just allows you to change variables
"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))

from constants import STATUS_REPORT_PERIOD
import threading
import logging
import socket
import time

SOCKET_PORT = 15575


class NodeServer:
    """A class for communicating with the Node.js server that handles app communication"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.warning("I'M JUST A STUB")

        # Server outputs
        self.configured    = False
        self.livestream_on = False
        self.alarm_on      = False
        
        # Start thread to read commands
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self.read_commands, daemon=True)
        self._thread.start()

        # Timestamp of last status message
        self.last_status_ts = 0


    def __del__(self):
        # Stop thread that listens to the command console
        if self._thread.is_alive():
            self._stop.set()
            self._thread.join(timeout=1)


    def connect(self, port=58008):
        """
        Connect to the node.js server

        Parameters:
        - port (int): The local port number of the node.js server
        """
        self.logger.info("Connected to Node.js Server")


    def disconnect(self):
        """Disconnect from the node.js server"""
        self.logger.info("Disconnected from Node.js Server")


    def send_status(self, cooking_coords, max_temp, unattended_time, m3u8_path=None):
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
        if m3u8_path:
            status["thermalStreamPath"] = m3u8_path
        self.logger.debug(str(status))


    def handle_message(self, data):
        """
        Recieve control flags from node.js server
        
        Parameters:
        - data (dict): Dict of control flags from node server
        """
        self.logger.info(f"Got data: {data}")

        # Parse data, update variables
        if "setupComplete" in data: 
            self.configured = bool(data["setupComplete"])
        if "liveStreamOn" in data: 
            self.livestream_on = bool(data["liveStreamOn"])
        if "alarmOn" in data: 
            self.alarm_on = bool(data["alarmOn"])


    def read_commands(self):
        """Continuously reads from the command console"""

        # TCP socket client to talk to the command console
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect(("127.0.0.1", SOCKET_PORT))
        except ConnectionRefusedError:
            self.logger.error("Could not connect to command console, have you started it?")
            return

        # Read commands
        while not self._stop.is_set():
            data = self.client.recv(1024)
            try:
                if len(data):
                    msg = eval(data.decode())
                    self.handle_message(msg)
            except:
                pass

        # Disconnect from the command console
        self.client.close()
                

# Command console 
if __name__ == "__main__":
    # Create TCP socket server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", SOCKET_PORT))
    server.listen()
    conn, addr = server.accept()
    print(f"Connected by {addr}")

    # Command menu
    menu  = "\nCommand menu:\n"
    menu += "[1] setupComplete\n"
    menu += "[2] liveStreamOn\n"
    menu += "[3] alarmOn\n"
    menu += "[4] <Quit>\n"
    menu += "Input: "

    while True:
        # Get menu input
        x = input(menu)

        try: 
            x=int(x)
            assert x >= 1 and x <= 4
        except:
            print("Invalid input")
            continue
        
        # Change variables
        if x == 1 or x==2 or x==3:
            y = input("Value: ")

            param = [None, "setupComplete", "liveStreamOn", "alarmOn"]
            payload = {param[x] : eval(y)}
            conn.sendall(str(payload).encode())

        # Quit
        else: break
    
    # Stop server
    conn.close()
    server.close()
