"""Class for blobs"""

from constants import *
import numpy as np
import time
import cv2


class Blob:
    """Characterize and operate on thermal image blobs"""

    def __init__(self, contour, thermal_img):
        # Detection score
        # Saturating counter
        # +1 every time object is detected
        # -1 every time object is not detected
        self.score = 1

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
        self.history = [{
            "timestamp" : time.time(),
            "centroid"  : self.centroid,
            "area"      : self.area,
            "temp"      : self.temp,
        }]


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
        old, new = sorted([self, other], key=lambda b: b.history[0]["timestamp"])

        # Merge variables
        # New object holds the most recent contour, mask, area, temp, etc.
        new.score = min(old.score + 1, BLOB_SCORE_MAX)
        new.color = old.color
        new.history = old.history + [new.history[-1]]

        return new
    

    # Examine history and determine if the blob is associated with cooking
    def is_cooking(self):
        # TODO
        return False


    # Draw the blob and its centroid
    def draw_blob(self, image):
        cv2.drawContours(image, [self.contour], -1, tuple(self.color), cv2.FILLED)
        cv2.circle(image, self.centroid, 1, (0, 0, 255), -1)
        return image


    # TODO?
    def fire_detected(self):
        pass
