"""Tests communication with the node.js server"""

# Add parent directory to the Python path
import os.path as path
import sys
sys.path.append(path.normpath(path.join(path.dirname(path.abspath(__file__)), '..', "src")))

# from stubs.node_server import NodeServer
from misc.node_server import NodeServer
import threading
import time


# Create server object
node = NodeServer()

# Connect to node.js server
node.connect()

# Print when a server output changes
def show_changes(stop):
    old_configured = node.configured
    old_livestream = node.livestream_on
    old_alarm_on   = node.alarm_on


    while not stop.is_set():
        if old_configured != node.configured:
            print(f"\nconfigured changed to {node.configured}")
            old_configured = node.configured
        
        if old_livestream != node.livestream_on:
            print(f"\nlivestream_on changed to {node.livestream_on}")
            old_livestream = node.livestream_on

        if old_alarm_on != node.alarm_on:
            print(f"\nalarm_on changed to {node.alarm_on}")
            old_alarm_on = node.alarm_on
        
        time.sleep(0.1)

# Start a thread to print server outputs
stop = threading.Event()
thread = threading.Thread(target=show_changes, args=(stop,), daemon=True)
thread.start()

try:
    while True:
        print("\nSend Status:")
        coords   = input("  Cooking coords: ")
        temp     = input("  Max Temp: ")
        t_absent = input("  Unattended time: ")

        node.send_status(eval(coords), eval(temp), eval(t_absent))

except:
    stop.set()
    thread.join(1)

    node.disconnect()
    raise
