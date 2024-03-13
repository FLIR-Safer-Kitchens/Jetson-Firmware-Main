import cv2
from lepton.utils import *
from lepton.vid_file import *
import time

class Blob:
    def __init__(self, contour, thermal_img):
        # Store detection time
        self.detect_ts = time.time()

        # Store contour
        self.contour = contour

        # Store mask
        self.mask = np.zeros((120, 160), dtype="uint8")
        cv2.drawContours(self.mask, [self.contour], -1, 255, thickness=cv2.FILLED)

        # Generate unique color
        self.color = [0, 255, np.random.randint(0, 256)]
        np.random.shuffle(self.color)

        # Store blob area
        self.area = cv2.contourArea(self.contour)

        # Store position & temp. history
        self.history = []

        # Compute the centroid
        M = cv2.moments(self.contour)
        centroid_x = int(M["m10"] / (M["m00"]+0.001))
        centroid_y = int(M["m01"] / (M["m00"]+0.001))
        self.centroid = (centroid_x, centroid_y)

        # Compute the average temperature
        masked = thermal_img[self.mask != 0]
        self.temp = np.mean(masked, axis=0)

        self.history.append((time.time(), self.centroid, self.temp))


    # Compare blobs
    def compare(self, other):

        # Find difference pixels
        diff = cv2.bitwise_xor(self.mask, other.mask)
        n_diff = cv2.countNonZero(diff)

        # Find max overlap
        union = cv2.bitwise_or(self.mask, other.mask)
        n_union = cv2.countNonZero(union)

        # Overlap score
        overlap = 1.0 - (n_diff/n_union)

        # Temperature score
        temp = abs(self.temp - other.temp) / 4000
        temp = 1.0 - temp

        # Size score 
        size = abs(self.area - other.area) / self.area
        size = max(0, 1.0 - size)

        return (overlap, temp, size)


    def drawBlob(self, image):
        cv2.drawContours(image, [self.contour], -1, tuple(self.color), cv2.FILLED)
        cv2.circle(image, self.centroid, 1, (0, 0, 255), -1)
        return image


    # Takes in two blobs and combines them
    def merge(self, other):
        old, new = sorted([self, other], key=lambda b: b.detect_ts)

        new.detect_ts = old.detect_ts
        new.color = old.color
        new.history = sorted(new.history + old.history, key=lambda b: b[0])

        return new


def find_blobs(frame):
    # Clip cold pixels and convert to 8-bit
    clipped = clip_norm(
        img = frame, 
        min_val = 32000, 
        max_val = 36000
    )

    # Bilateral filter
    clipped = cv2.bilateralFilter(
        src = clipped, 
        d = 5, 
        sigmaColor = 30, 
        sigmaSpace = 20
    )

    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        src = clipped, 
        maxValue = 255, 
        adaptiveMethod = cv2.ADAPTIVE_THRESH_MEAN_C, 
        thresholdType = cv2.THRESH_BINARY, 
        blockSize = 35, 
        C = 0
    )

    # Close holes
    kernel  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
    closed = cv2.morphologyEx(
        src = thresh, 
        op = cv2.MORPH_CLOSE, 
        kernel = kernel, 
        iterations = 2
    )

    # Find contours
    contours, heirarchy = cv2.findContours(
        image = closed, 
        mode = cv2.RETR_EXTERNAL, 
        method = cv2.CHAIN_APPROX_SIMPLE
    )

    return [Blob(c, frame) for c in contours]
    


vid = Raw16Video("C:/Users/sdhla/Documents/GitHub/Capstone/Jetson-Firmware-Main/src/cooking_detection/vids/Lepton_Capture_6.tiff")

# Display the segmented image
# cv2.namedWindow("OG", cv2.WINDOW_NORMAL)
cv2.namedWindow("Segmented", cv2.WINDOW_NORMAL)

# writer = SaveVideo("out.mp4", True)

old_blobs = []
while True:
    ret, frame = vid.read()
    if not ret: break

    blobs = find_blobs(frame)

    frame = clip_norm(frame)
    three_chan = cv2.merge([frame]*3)

    temp = []
    for blob in blobs:
        if blob.area < 16: continue
        if blob.temp < 32000: continue

        # Compare
        # print()
        for old in old_blobs:
            # print(old.compare(blob))
            if sum(old.compare(blob))/3 > 0.7:
                temp.append(old.merge(blob))
                break
        else:
            temp.append(blob)

    old_blobs = temp
    for blob in old_blobs:
        blob.drawBlob(three_chan)
    
    # writer.write(three_chan)
    cv2.imshow("Segmented", three_chan)
    cv2.waitKey(0)

# writer.close()
"""
three_chan = cv2.merge([frame]*3)
segmented_image = cv2.pyrMeanShiftFiltering(three_chan, 60, 60)

# Get unique labels from the segmented image
labels = np.unique(segmented_image)
print(f"Found {len(labels)} segments")

# Assign a random color to each segment
segmented_color = np.zeros((segmented_image.shape[0], segmented_image.shape[1], 3), dtype=np.uint8)
for label in labels:
    mask = segmented_image == label
    color = [0, 255, np.random.randint(0, 256)]
    np.random.shuffle(color)
    for i in range(3):
        segmented_color[mask[:,:,i], i] = color[i]

cv2.imshow("OG", frame)
cv2.imshow("Segmented", segmented_color)

cv2.waitKey(0)
cv2.destroyAllWindows()

    erode   = cv2.erode(opening, kernel, iterations = 1)

    cv2.imshow("Segmented", opening)
    cv2.waitKey(0)

    # # Find "sure" background
    sure_bg = cv2.dilate(opening, kernel, iterations=3)

    cv2.imshow("Segmented", sure_bg)
    cv2.waitKey(0)

    # # Find "sure" foreground
    dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    ret, sure_fg   = cv2.threshold(dist_transform, 0.7*dist_transform.max(), 255, 0)

    cv2.imshow("Segmented", sure_fg)
    cv2.waitKey(0)

    # # Find unknown region
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)

    # Marker labelling
    # ret, markers = cv2.connectedComponents(sure_fg)
 
    # Add one to all labels so that sure background is not 0, but 1
    # markers = markers+1
 
    # Now, mark the region of unknown with zero
    # markers[unknown==255] = 0

    markers = cv2.divide(erode, 255).astype("int32")
    markers = cv2.multiply(markers, 2)
    print(min(markers.flatten()))
    print(max(markers.flatten()))

    three_chan = cv2.merge([frame]*3)

    # Do watershed
    markers = cv2.watershed(three_chan, markers)
    three_chan[markers == -1] = [255,0,0]

    return erode
"""