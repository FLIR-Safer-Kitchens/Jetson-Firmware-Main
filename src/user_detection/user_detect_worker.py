"""Worker that performs user detection"""

from misc.logs import configure_subprocess
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
    - new (multiprocessing.Event): Flag that indicates when a new frame is available
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

        # Add handler to ultralytics module
        root = logging.getLogger()
        ul_logs = logging.getLogger('ultralytics')
        ul_logs.handlers = root.handlers

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.buf)

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Create a dictionary to track users
        tracked_people = dict()

        # Load model
        model_dir = os.path.dirname(__file__)
        model = YOLO(os.path.join(model_dir, 'yolov8n.pt'))

        cv2.namedWindow("test", cv2.WINDOW_NORMAL) # For debugging. delete me

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Setup Error")
        stop.set() # Skip loop

    # === Loop ===
    while not stop.is_set():
        try:
            # Check for new frame
            if not new.is_set(): continue
            else: new.clear()

            # Copy frame from shared memory
            lock.acquire(timeout=0.5)
            np.copyto(frame, frame_src)
            lock.release()

            # Run YOLOv8 tracking on the frame, persisting tracks between frames
            # Classes argument filters class 0 (person)
            results = model.track(frame, persist=True, classes=0, verbose=False)

            # Extract confidence ratings, bounding boxes, and IDs
            confs = results[0].boxes.conf.double().tolist()
            boxes = results[0].boxes.xyxy.tolist()
            ids   = results[0].boxes.id
            ids   = ids.int().tolist() if hasattr(ids, "tolist") else []

            found = set()
            for i, conf in enumerate(confs):
                # Threshold confidence
                # Check ids length. New objects are not given an ID at first
                if (conf < 0.5) or (i >= len(ids)): continue
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
            if any([v.valid for v in tracked_people.values()]):
                detect_ts.value = time.time()

            # -- For debugging. delete me --
            for k, v in tracked_people.items():
                color = (0, 255, 0) if v.valid else (0, 0, 255)
                center = (int(v.center[0]), int(v.center[1]))
                cv2.circle(frame, center, 10, color, cv2.FILLED)
           
            cv2.imshow("test", frame)
            cv2.waitKey(1)
            time.sleep(10e-3)
            # -------------------------------

        # Add errors to queue
        except BaseException as err:
            errs.put(err, False)
            logger.exception("Loop Error")
            stop.set() # Exit loop

    # === Terminate ===
    try:
        cv2.destroyWindow("test") # For debugging. delete me

    # Add errors to queue
    except BaseException as err:
        errs.put(err, False)
        logger.exception("Termination Error")



class TrackedPerson:
    def __init__(self, bbox):
        # Save bounding box center
        self.center = ( 
            np.mean((bbox[0], bbox[2])), 
            np.mean((bbox[1], bbox[3]))
        ) # (x, y)

        # First detection timestamp
        self.first_detected = time.time()
        
        # Last movement timestamp
        self.last_move = self.first_detected
        
        # True if the person is considered valid:
        # - Has existed for a suffiecently long time
        # - Is not stationary
        self.valid = False

    # Update valid flag
    def update(self, bbox):
        # Compute new bbox center
        new_center = ( 
            np.mean((bbox[0], bbox[2])), 
            np.mean((bbox[1], bbox[3]))
        ) # (x, y)

        # Detect movement
        dist = np.linalg.norm(np.subtract(self.center, new_center))
        if  dist > USER_MOVEMENT_DIST_THRESH:
            self.center = new_center
            self.last_move = time.time()

        # Check tracking duration
        self.valid = True
        if (time.time() - self.first_detected) < USER_TRACKING_TIME_THRESH:
            self.valid = False
        
        # Check time since last movement
        elif (time.time() - self.last_move) > USER_MOVEMENT_TIME_THRESH:
            self.valid = False
