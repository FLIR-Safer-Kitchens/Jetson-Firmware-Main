"""Cooking detection launcher"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', "src")))
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '../..', 'tests')))


from multiprocessing import Manager
from stubs import Launcher
import threading
import logging
import socket
import time

SOCKET_PORT = 15670


def worker(stop, raw16_mem, frame_event, log_queue):
    getting_frames = False
    last_frame = 0

    while not stop.is_set():
        if getting_frames and (time.time() - last_frame) > 2:
            print("Cooking detection no longer getting frames")
            getting_frames = False
        if not getting_frames and (time.time() - last_frame) < 1:
            print("Cooking detection getting frames")
            getting_frames = True

        # Wait for new frame
        if not frame_event.wait(timeout=0.5): continue
        else: frame_event.clear()

        last_frame = time.time()



class CookingDetect(Launcher):
    """Class for managing the cooking detection worker"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        self.logger.warning("I'M JUST A STUB!")

        # Detection flags
        self.cooking_coords = Manager().list()

        # Frame reading worker
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
        Start the cooking detection worker

        Parameters:
        - raw16_mem (multiprocessing.Array): Shared memory location of raw16 frame data
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


    def handle_message(self, data):
        """
        Recieve control flags from command window
        """
        self.logger.info(f"Got data: {data}")

        # Parse data, update variables
        if "cooking_coords" in data: 
            self.cooking_coords[:] = list(data["cooking_coords"])


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
    menu += "[1] cooking_coords\n"
    menu += "[2] <Quit>\n"
    menu += "Input: "

    while True:
        # Get menu input
        x = input(menu)

        try: 
            x=int(x)
            assert x >= 1 and x <= 2
        except:
            print("Invalid input")
            continue
        
        # Change variables
        if x == 1 :
            y = input("Value: ")
            payload = {'cooking_coords' : eval(y)}
            conn.sendall(str(payload).encode())

        # Quit
        else: break
    
    # Stop server
    conn.close()
    server.close()
