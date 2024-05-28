"""PureThermal polling launcher"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', 'tests')))


from constants import RAW_THERMAL_SHAPE, RAW_THERMAL_RATE
from misc.monitor import MonitorServer
from ctypes import c_bool, c_double
from multiprocessing import Value
from stubs import Launcher
import numpy as np
import threading
import logging
import socket
import time

SOCKET_PORT = 15666


def worker(stop, raw16_mem, frame_event, log_queue):

    # Create numpy array backed by shared memory
    frame_dst = np.ndarray(shape=RAW_THERMAL_SHAPE, dtype='uint16', buffer=raw16_mem.get_obj())

    monitor = MonitorServer(12348)

    while not stop.is_set():
        start = time.time()
        frame = np.random.randint(0, 2**16-1, RAW_THERMAL_SHAPE, dtype='uint16')

        raw16_mem.get_lock().acquire(timeout=0.5)
        np.copyto(frame_dst, frame)
        raw16_mem.get_lock().release()

        monitor.show(frame >> 8, 100)

        # Set new frame flag
        frame_event.set()
        time.sleep(max(0, 1/RAW_THERMAL_RATE - (time.time()-start)))

    frame_event.clear()



class PureThermal(Launcher):
    """Class for managing the PureThermal Lepton polling worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        self.logger.warning("I'M JUST A STUB!")
        
        # Maximum detected temperature
        self.max_temp = Value(c_double, 0.0)

        # Flag to indicate when hotspots have been detected
        self.hotspot_detected = Value(c_bool, False)

        # Frame writing worker
        self.stop_sig1 = threading.Event()
        self.thread1 = None
        
        # Command reading worker
        self.stop_sig2 = threading.Event()
        self.thread2 = threading.Thread(target=self.read_commands, daemon=True)
        self.thread2.start()


    def __del__(self):
        if self.thread2.is_alive():
            self.stop_sig2.set()
            self.thread2.join(timeout=1)


    def start(self, raw16_mem, frame_event, log_queue):
        """
        Start the PureThermal polling worker

        Parameters:
        - raw16_mem (multiprocessing.Array): Shared memory location of thermal camera data
        - frame_event (NewFrameEvent): Master 'new frame' event. Set all child events when a new frame is written
        - log_queue (multiprocessing.Queue): Queue to handle log messages
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


    def handle_message(self, data):
        """
        Recieve control flags from command window
        """
        self.logger.info(f"Got data: {data}")
        
        # Parse data, update variables
        if "max_temp" in data: 
            self.max_temp.value = float(data["max_temp"])
        if "hotspot_detected" in data: 
            self.hotspot_detected.value = bool(data["hotspot_detected"])


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
        while not self.stop_sig2.is_set():
            data = self.client.recv(1024)
            try:
                if len(data):
                    msg = eval(data.decode())
                    # print(msg)
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
    menu += "[1] max_temp\n"
    menu += "[2] hotspot_detected\n"
    menu += "[3] <Quit>\n"
    menu += "Input: "

    while True:
        # Get menu input
        x = input(menu)

        try: 
            x=int(x)
            assert x >= 1 and x <= 3
        except:
            print("Invalid input")
            continue
        
        # Change variables
        if x == 1 or x==2:
            y = input("Value: ")

            param = [None, "max_temp", "hotspot_detected"]
            payload = {param[x] : eval(y)}
            conn.sendall(str(payload).encode())

        # Quit
        else: break
    
    # Stop server
    conn.close()
    server.close()
