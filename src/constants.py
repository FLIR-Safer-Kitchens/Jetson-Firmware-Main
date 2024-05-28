"""Define global constants"""

# Worker process exception handling
EXCEPTION_HISTORY_WINDOW = 10 # Duration in seconds to track non fatal errors
ALLOWABLE_EXCEPTION_COUNT = 2 # Maximum number of nonfatal errors within the history window that will be tolerated before the program exits

# Visible image shape
VISIBLE_SHAPE = (480, 640, 3) # (height, width, depth)

# 16-bit thermal image properties
RAW_THERMAL_SHAPE = (120, 160) # (height, width)
RAW_THERMAL_DIAG  = 200 # sqrt(120^2+160^2)
RAW_THERMAL_RATE = 9 # Frames/sec

# PureThermal USB identifiers
PT_USB_VID = 0x1e4e # Vendor ID 
PT_USB_PID = 0x0100 # Product ID

# Path to libuvc dll
LIBUVC_DLL_PATH = "/usr/local/lib/libuvc.so"

# Camera timeouts
PURETHERMAL_TIMEOUT = 3.0 
"""(float) Maximum time in seconds to allow the purethermal board to not send a valid frame"""

ARDUCAM_TIMEOUT = 2.0 
"""(float) Maximum time in seconds to allow the arducam to not send a valid frame """

# Arducam calibration matrix
ARDUCAM_CALIB = [
	[398.62421431702717, 0.000000000000000, 311.42355820638990],
	[0.0000000000000000, 398.5759247050562, 243.21092881633064],
	[0.0000000000000000, 0.000000000000000, 1.0000000000000000]
]

# Arducam distortion coefficients
ARDUCAM_DIST = [
    -0.4200401425733124600,
     0.1767459404637726500,
     0.0021537820029228164,
     0.0003045840186394911,
    -0.0339511656826229840,
]

# Arducam new camera matrix
ARDUCAM_NEW_CAM = [
    [351.8592681884766, 0.000000000000000, 302.78308803853616],
	[0.000000000000000, 361.0281494140625, 239.86782248284146],
	[0.000000000000000, 0.000000000000000, 1.0000000000000000]
]

# Lepton hotspot detection
HOTSPOT_EMA_ALPHA = 0.1 # Exponential moving avg. constant (weight [0,1] to give to new value). Time constant = -(sample period) / ln(1-alpha)
HOTSPOT_TRIP_TIME = 3 # Duration in seconds that a hotspot must be visible for in order to register as a hotspot
HOTSPOT_RELEASE_TIME = 10 # Duration in seconds where no hotspots are detected after which the hotspot flag will be lowered

# Thermal image clipping limits
TEMP_THRESH_LOW  = 40.0 # degrees C
TEMP_THRESH_HIGH = 100.0 # degrees C

# Blob filtering parameters
BLOB_MIN_AREA = 16
BLOB_MIN_TEMP = 50.0 # degrees C

# Blob tracking 
BLOB_LIVES = 3 # Number of frames to retain blob for after it has not been detected
BLOB_HISTORY_RATE = 2.0 # Number of samples to store per second. Can be float
BLOB_HISTORY_DEPTH = 30 # Maximum number of history samples to keep

# Cooking detection hysteresis
COOKING_TRIP_TIME = 10 # Duration in seconds that a blob must have a constant/positve slope in order to register as cooking
COOKING_RELEASE_TIME = 10 # Duration in seconds that a cooking blob must have a nagative slope in order to deregister as cooking

# Blob similarity scoring
SIM_SCORE_WEIGHTS = (1, 4, 2, 0.1) # Score weights (Overlap, distance, temperature, area)
SIM_SCORE_MATCH = 0.7 # Combined score threshold to declare a match
SIM_SCORE_MIN = 0.1 # Not a match if any individual score is below this threshold

# Minumim slope for cooking detection
TEMP_SLOPE_THRESHOLD = -0.05

# User detection constants
USER_MIN_CONFIDENCE = 0.6 # Confidence threshold for user detection [0,1]
USER_MOVEMENT_DIST_THRESH = 20 # Pixel distance that a bounding box must move to be considered movement
USER_MOVEMENT_TIME_THRESH = 15*60 # Maximum time in seconds that a person can stay stationary before being considered invalid

# Node.js server constants
NODE_SERVER_PORT = 3000 # Local port that the node.js server uses
STATUS_REPORT_PERIOD = 2 # The time in seconds between status messages sent to server

# Live streaming constants
UDP_PORT = 12345
HLS_DIRECTORY = "C:/Users/sdhla/Documents/GitHub/Capstone/Jetson-Firmware-Main/src/streaming/hls/" # Directory where stream segments and .m3u8 will be stored. Absolute path preferred
HLS_FILENAME = "thermal.m3u8"

# Alarm board constants
AVR_BAUD_RATE = 9600 # Baud rate for serial communication
AVR_USB_VID = 9025 # USB vendor ID for MCU
AVR_USB_PID = 67 # USB product ID for MCU
AVR_TIMEOUT = 2 # Timeout in seconds for incoming and outgoing serial communication
