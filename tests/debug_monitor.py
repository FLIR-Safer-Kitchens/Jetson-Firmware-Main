"""Tests the debug monitor module"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

import multiprocessing as mp
from misc.monitor import *
import time
import cv2


def stream_frames(monitor_server, stop):
    # Open the camera
    cap = cv2.VideoCapture(0)
    assert cap.isOpened()
    
    try:
        while not stop.is_set():
            ret, frame = cap.read()
            assert ret, "Bad frame"
            
            # Show the frame using MonitorServer
            monitor_server.show(frame)
            
            # Simulate processing time
            time.sleep(10e-3)
        else: 
            raise KeyboardInterrupt
    
    except BaseException as err:
        cap.release()
        if type(err) != type(KeyboardInterrupt): raise



def main():
    try:
        # Create a MonitorServer
        monitor_server = MonitorServer(12347)  # Choose your port
        
        # Create a MonitorClient
        monitor_client = MonitorClient(12347)  # Same port as MonitorServer

        # Suspend event
        stop = mp.Event()

        # Create a multiprocessing process
        process = mp.Process(target=stream_frames, args=(monitor_server, stop,))
        
        # Start the process
        process.start()
        time.sleep(10)

        # Create window
        cv2.namedWindow("monitor", cv2.WINDOW_NORMAL)
        
        # Read frames from MonitorClient
        while True:
            success, frame = monitor_client.read()  # 1 second timeout
            if not success:
                print("READ FAIL")
                continue
            
            # Display the received frame
            cv2.imshow("monitor", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                raise KeyboardInterrupt
    
    except:
        # Stop the client/server sockets
        monitor_client.stop()
        monitor_server.stop()
        
        # Stop the process
        stop.set()
        try: process.join(timeout=3)
        except TimeoutError:
            print("Process did not terminate gracefully")
            process.terminate()

        # Close OpenCV windows
        cv2.destroyAllWindows()
        raise

if __name__ == "__main__":
    main()
