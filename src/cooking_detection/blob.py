"""Class for blobs"""

from .theil_sen import theil_sen
from constants import *
import numpy as np
import time
import cv2

# Configure logger
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Blob:
    """Characterize and operate on thermal image blobs"""

    def __init__(self, contour, thermal_img):
        # Number of frames to retain blob for 
        # after it has not been detected
        self.lives = BLOB_LIVES

        # Saturating counter
        # +1 every time cooking is detected
        # -1 every time cooking is not detected
        self.cooking_score = 0

        # Last reult of cooking detection
        # Use this value when cooking score is 
        # between high and low thresholds
        self.__cooking = False

        # Generate unique color
        self.color = [0, 255, np.random.randint(0, 256)]
        np.random.shuffle(self.color)

        # Store contour
        self.contour = contour

        # Store mask
        self.mask = np.zeros(thermal_img.shape, dtype="uint8")
        cv2.drawContours(self.mask, [self.contour], -1, 255, thickness=cv2.FILLED)

        # Compute area. Includes contour border
        self.area = np.count_nonzero(self.mask)

        # Compute centroid
        M = cv2.moments(self.contour)
        centroid_x = int(M["m10"] / (M["m00"]+0.001))
        centroid_y = int(M["m01"] / (M["m00"]+0.001))
        self.centroid = (centroid_x, centroid_y)

        # Compute average temperature
        self.temp = cv2.mean(thermal_img, self.mask)[0]

        # Store position, area, and temperature history
        self.first_detected = time.time()
        self.history = [{
            "timestamp" : self.first_detected,
            "centroid"  : self.centroid,
            "area"      : self.area,
            "temp"      : self.temp,
        }]

        # Flag to indicate when a new point is added to history
        self.new_data_flag = False


    # Compare blobs. Return similarity score [0, 1]. 1 is a perfect match
    def compare(self, other):
        # 1. Overlap score
        # [0, 1] 1 for full overlap
        diff    = cv2.bitwise_xor(self.mask, other.mask)
        n_diff  = cv2.countNonZero(diff)
        overlap = 1.0 - n_diff / (self.area + other.area)

        # 2. Centroid distance score
        # [0, 1] 1 for idetical centroids
        distance = np.linalg.norm(np.subtract(self.centroid, other.centroid))
        distance = 1.0 - distance / RAW_THERMAL_DIAG 

        # 3. Temperature score
        # [0, 1] 1 for identical temp
        # TODO: Replace the constant
        temp = 1.0 - abs(self.temp - other.temp) / 4000 

        # 4. Area score
        # [0, 1] 1 for identical area
        size = min(self.area, other.area) / max(self.area, other.area) 

        # Compute weighted average
        scores = (overlap, distance, temp, size)
        score = np.dot(SIM_SCORE_WEIGHTS, scores) / sum(SIM_SCORE_WEIGHTS)
        
        # Coerce overall score to zero if any scores are extremely low
        if any(s < SIM_SCORE_MIN for s in scores): score = 0

        return score


    # Combine two blobs
    def merge(self, other):
        # Find oldest/youngest blob
        old, new = sorted([self, other], key=lambda b: b.first_detected)

        # Merge properties
        # New object holds the most recent contour, mask, area, temp, etc.
        new.cooking_score = old.cooking_score
        new.__cooking = old.__cooking
        new.color = old.color
        new.first_detected = old.first_detected
        new.new_data_flag = old.new_data_flag
        
        # Enforce history sample rate
        dt = new.history[-1]["timestamp"] - old.history[-1]["timestamp"]
        add_new = dt > 1/BLOB_HISTORY_RATE
        new.history = old.history + ([new.history[-1]] if add_new else [])
        new.new_data_flag |= add_new
        
        # Enforce max history depth
        new.history = new.history[-BLOB_HISTORY_DEPTH:]
        
        return new
    

    # Examine history and determine if the blob is associated with cooking
    def is_cooking(self):
        # No new data, return most recent value
        if not self.new_data_flag:
            return self.__cooking
        else: self.new_data_flag = False

        # Collect temperature history
        temp_history = [(h["timestamp"], h["temp"]) for h in self.history]
        temp_history = np.array(temp_history)

        # For debugging
        # if time.time() - self.first_detected > 10:
        #     filename = f"history_{round(self.first_detected % 1000)}.csv"
        #     np.savetxt(filename, temp_history, delimiter = ",")

        # Not enough samples to make a prediction yet
        if temp_history.shape[0] < BLOB_HISTORY_DEPTH:
            return False
        
        # Find slope using Theil-Sen estimator
        slope = theil_sen(temp_history[:,0], temp_history[:,1], 1000)

        # There's definitely a more efficent way to compute slope 
        # cinsidering the dataset barely changes between iterations.
        # TODO: Convert slope to standard units for thresholding
        # TODO: Calculate blob velocity & add scoring

        # Threshold slope
        cooking = slope > -10

        # Update score
        self.cooking_score = self.cooking_score + (1 if cooking else -1)
        self.cooking_score = np.clip(self.cooking_score, 0, COOKING_SCORE_SATURATION)

        # Update cooking state
        if self.cooking_score >= COOKING_SCORE_THRESH_HIGH:
            self.__cooking = True
        elif self.cooking_score <= COOKING_SCORE_THRESH_LOW:
            self.__cooking = False
        
        logger.debug(f"{slope} {self.cooking_score} {self.__cooking}")

        return self.__cooking


    # Draw the blob and its centroid
    def draw_blob(self, image):
        # Detected in this frame
        if self.lives == BLOB_LIVES:
            cv2.drawContours(image, [self.contour], -1, tuple(self.color), cv2.FILLED)
            if self.is_cooking():
                cv2.drawContours(image, [self.contour], -1, (0,100,255), 2)
            cv2.circle(image, self.centroid, 1, (0, 0, 255), -1)
    
        return image


    # TODO?
    def fire_detected(self):
        pass
