"""Worker that performs user detection"""

from misc.hysteresis import HysteresisBool
from misc.logs import configure_subprocess
from misc.monitor import MonitorServer
from ultralytics import YOLO
from constants import *
import numpy as np
import logging
import time
import cv2
import os


def user_detect_worker(mem, lock, new, stop, log, errs, detect_ts):
    """
    Main user detection loop

    Parameters:
    - mem (multiprocessing.shared_memory): Shared memory location of visible camera data
    - lock (multiprocessing.Lock): Lock object for shared memory location
    - new (NewFrameConsumer): Flag that indicates when a new frame is available
    - stop (multiprocessing.Event): Flag that indicates when to suspend process
    - log (multiprocessing.Queue): Queue to handle log messages
    - errs (multiprocessing.Queue): Queue to dump errors raised by worker
    - detect_ts (multiprocessing.Value (double)): Epoch timestamp of last detection
    """

    # === Setup ===
    try:
        # Set up logs for subprocess
        configure_subprocess(log)

        # Create logger 
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Create a UDP server to send images to for debugging
        monitor = MonitorServer(12346)

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Create a dictionary to track users
        tracked_people = dict()

        # Load model
        logger.debug("Loading model file")
        model_dir = os.path.dirname(__file__)
        model = YOLO(os.path.join(model_dir, 'yolov8n.pt'))
        logger.debug("Model loaded successfully")

        # Detection state
        user_detected = HysteresisBool(2, 4)

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup Error")
        stop.set() # Skip loop

    else: logger.debug("Setup complete, starting user detection loop...")

    # === Loop ===
    while not stop.is_set():
        try:
            # Wait for new frame
            if not new.wait(timeout=0.5): continue
            else: new.clear()

            # Copy frame from shared memory
            lock.acquire(timeout=0.2)
            np.copyto(frame, frame_src)
            lock.release()

            # Run YOLOv8 tracking on the frame
            results = model.track(
                frame,
                persist=True,             # Track objects between frames
                conf=USER_MIN_CONFIDENCE, # Confidence threshold
                classes=0,                # Filter class 0 (person)
                verbose=False             # Do not print to console
            )

            # Extract confidence ratings, bounding boxes, and IDs
            boxes = results[0].boxes.xyxy.tolist()
            ids   = results[0].boxes.id
            ids   = ids.int().tolist() if hasattr(ids, "tolist") else []

            found = set()
            for i in range(len(boxes)):
                # Check ids length. New objects are not given an ID at first
                if i >= len(ids): continue
                else: found.add(ids[i])

                # Matched with existing person
                if ids[i] in tracked_people:
                    tracked_people[ids[i]].update(boxes[i])

                # Got new person
                else: tracked_people[ids[i]] = TrackedPerson(boxes[i])

            # Purge unmatched people
            for k in list(tracked_people.keys()):
                if k not in found: del tracked_people[k]

            # Detect user
            user_detected.value = any([v.valid for v in tracked_people.values()])
            if user_detected.value: detect_ts.value = time.time()

            # Show debug output on monitor
            for k, v in tracked_people.items():
                color = (0, 255, 0) if user_detected.value else (0, 186, 255)
                if not v.valid: color = (0, 0, 255)
                center = (int(v.center[0]), int(v.center[1]))
                cv2.circle(frame, center, 10, color, cv2.FILLED)
            
            monitor.show(frame)

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop Error")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        monitor.stop()

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination Error")

    else: logger.debug("Termination routine completed. Exiting...")


class TrackedPerson:
    """Class for organizing variables related to a detected person"""

    def __init__(self, bbox): #xyxy
        # Save bounding box center
        # bbox: (tl_x, tl_y, br_x, br_y). center: (x,y)
        self.center = ( 
            np.mean((bbox[0], bbox[2])), 
            np.mean((bbox[1], bbox[3]))
        )

        # First detection timestamp
        self.first_detected = time.time()
        
        # Last movement timestamp
        self.last_move = self.first_detected
        
        # True if the person is considered valid (not stationary)
        self.valid = True

    def update(self, bbox):
        """
        Updates the current object with a new bounding box\n
        Detects any movement between the last bounding box and the new one.\n
        Sets valid flag
        """
        # Compute new bbox center
        # bbox: (tl_x, tl_y, br_x, br_y). center: (x,y)
        new_center = ( 
            np.mean((bbox[0], bbox[2])), 
            np.mean((bbox[1], bbox[3]))
        )

        # Detect movement
        dist = np.linalg.norm(np.subtract(self.center, new_center))
        if  dist > USER_MOVEMENT_DIST_THRESH:
            self.center = new_center
            self.last_move = time.time()
        
        # Check time since last movement
        self.valid = (time.time() - self.last_move) < USER_MOVEMENT_TIME_THRESH
