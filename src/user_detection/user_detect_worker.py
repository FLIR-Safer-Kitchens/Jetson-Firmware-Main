"""Worker that performs user detection"""

from misc.hysteresis import HysteresisBool
from misc.logs import configure_subprocess
from misc.monitor import MonitorServer
from constants import *
import numpy as np
import platform
import logging
import random
import time
import cv2
import os

import csv # FOR TESTING

# System-dependent imports
if platform.system() == 'Windows':
    from ultralytics import YOLO

elif platform.system() == 'Linux':
    from .trt_engine import YoloEngine



def user_detect_worker(mem, new, stop, log, errs, detect_ts):
    """
    Main user detection loop

    Parameters:
    - mem (multiprocessing.Array): Shared memory location of visible camera data
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
        monitor = MonitorServer(12346, 12350)

        # Choose detector based on system
        logger.debug("Intializing detector")
        if platform.system() == 'Windows':
            detector = WindowsDetect()

        elif platform.system() == 'Linux':
            detector = JetsonDetect()
        logger.debug("Detector ready")

        # Create numpy array backed by shared memory
        frame_src = np.ndarray(shape=VISIBLE_SHAPE, dtype='uint8', buffer=mem.get_obj())

        # Create array for us to copy to
        frame = np.empty_like(frame_src)

        # Detection state
        user_detected = HysteresisBool(2, 4)

        # ========== For testing ===========
        # Initialize csv
        frame_index = 0
        csv_filename = f'user_det_log_{round(time.time())}.csv'
        with open(csv_filename, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(['Timestamp', "Index", "Inference Time", "BBox", "Conf"])
        # ==================================

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
            mem.get_lock().acquire(timeout=0.2)
            np.copyto(frame, frame_src)
            mem.get_lock().release()

            # Detect user
            boxes, confs, tm = detector.detect(frame)
            user_detected.value = len(boxes) > 0
            if user_detected.value: detect_ts.value = time.time()

            # Log detection time
            logger.debug(f"Inference time: {tm*1000:5.2f}ms")

            # ========== For testing ===========
            with open(csv_filename, 'a', newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                frame_index += 1

                det_info = []
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = box
                    det_info.append(f"{x1:d} {y1:d} {x2:d} {y2:d}")
                    det_info.append(confs[i])

                csv_writer.writerow([time.time(), frame_index, tm] + det_info)
                csvfile.flush()

            # Add index to frame
            tl = 3
            tf = 2
            cv2.putText(frame, str(frame_index), (5, 480-5), 0, tl/2, [0, 0, 255], thickness=tf, lineType=cv2.LINE_AA,)
            # ==================================

            # Show debug output on monitor
            for i, box in enumerate(boxes):
                color = (0, 255, 0) if user_detected.value else (0, 186, 255)
                plot_box(box, frame, color, f"{confs[i]:0.2f}")
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



class JetsonDetect:
    """High-level wrapper for YOLOv7 on Jetson Nano"""

    def __init__(self):
        # Get directory containing dll and engine
        dir = os.path.join(os.path.dirname(__file__), "build_engine/yolov7/build/")

        # Initialize engine
        self.engine = YoloEngine(
            library = os.path.join(dir, "libmyplugins.so"),
            engine  = os.path.join(dir, "yolov7-tiny.engine"),
            conf_thresh=USER_MIN_CONFIDENCE,
            classes={0} # Only people
        )


    def detect(self, img):
        """
        Performs YOLOv7 inference on an image

        Parameters:
        - img (numpy.ndarray): The image to be analyzed

        Returns (tuple):
        - list (list (int)): The xyxy bounding boxes of detected people
        - list (float): The confidence score of each detection result
        - float: The inference time in seconds
        """

        # Resize image
        # img = cv2.resize(img, (450, 600))

        # Perform inference
        result, tm = self.engine.inference(img)

        # Extract boxes
        box  = [res["box"]  for res in result]
        conf = [res["conf"] for res in result]
        return box, conf, tm



class WindowsDetect:
    """High-level wrapper for YOLOv8 inference on an image"""

    def __init__(self):
        # Load model file
        model_dir = os.path.dirname(__file__)
        self.model = YOLO(os.path.join(model_dir, 'yolov8n.pt'))


    def detect(self, img):
        """
        Perform sYOLOv8 inference on an image

        Parameters:
        - img (numpy.ndarray): The image to be analyzed

        Returns (tuple):
        - list (list (int)): The xyxy bounding boxes of detected people
        - list (float): The confidence score of each detection result
        - float: The inference time in seconds
        """

        # Run YOLOv7 detection on the frame
        t1 = time.time()
        results = self.model.predict(
            img,
            conf=USER_MIN_CONFIDENCE, # Confidence threshold
            classes=0,                # Filter class 0 (person)
            verbose=False             # Do not print to console
        )
        t2 = time.time()

        # Extract bounding boxes
        boxes = results[0].boxes.xyxy.tolist()
        confs = results[0].boxes.conf.float().tolist()
        return boxes, confs, t2-t1



def plot_box(bbox, img, color=None, label=None, line_thickness=None):
    """
    Draws a bounding box and label on an image

    Parameters:
    - bbox (list): Bounding box in xyxy format
    - img (numpy.ndarray): Image to annotate
    - color (tuple): Color tuple in BGR format
    - label (str): Label to show above the bounding box
    - line_thickness (int): Thickness of bounding box lines

    Returns (numpy.ndarray): The annotated image
    """

    # Get line thickness and color
    tl = (line_thickness or round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1)  # line/font thickness
    color = color or [random.randint(0, 255) for _ in range(3)]

    # Draw box
    c1, c2 = (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)

    # Add label
    if label:
        tf = max(tl - 1, 1)  # font thickness
        t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] + t_size[1] + 2*tl
        cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
        cv2.putText(img, label, (c1[0], c1[1] + t_size[1] + tl), 0, tl / 3, [0, 0, 0], thickness=tf, lineType=cv2.LINE_AA,)
