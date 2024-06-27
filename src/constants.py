"""Define global constants"""

# Worker process exception handling
EXCEPTION_HISTORY_WINDOW = 10
"""(float) Duration in seconds to track non fatal errors"""

ALLOWABLE_EXCEPTION_COUNT = 2
"""(int) Maximum number of nonfatal errors within the history window that will be tolerated before the program exits"""



# Node.js server constants
NODE_SERVER_PORT = 3000 
"""(int) Local port that the node.js server uses"""

STATUS_REPORT_PERIOD = 2 
"""(float) The time in seconds between status messages sent to server"""


# Live streaming constants
STREAM_TYPE_THERMAL = "thermal"
"""(str) Keyword used by the Node.js server to indicate a thermal stream"""

STREAM_TYPE_VISIBLE = "visible"
"""(str) Keyword used by the Node.js server to indicate a visible stream"""

STREAM_UDP_PORT = 12345
"""The UDP port used by the docker container to receive livestream frames"""



# Alarm board constants
AVR_CONNECTION_RETRIES = 15
"""(int) Number of attempts that the firmware will make to connect to the MCU"""

AVR_RETRY_COOLDOWN = 2.0
"""(float) Time in seconds between connection attempts"""

AVR_BAUD_RATE = 9600 
"""(int) Baud rate for serial communication"""

AVR_USB_VID = 9025
"""(int) USB vendor ID for MCU"""

AVR_USB_PID = 32822
"""(int) USB product ID for MCU"""

AVR_TIMEOUT = 2
"""(float) Timeout in seconds for incoming and outgoing serial communication"""



# 16-bit thermal image properties
RAW_THERMAL_SHAPE = (120, 160)
"""(tuple (int)) Height, width of thermal (lepton) image"""

RAW_THERMAL_DIAG  = 200
"""(float) Diagonal length in pixels of thermal image"""

RAW_THERMAL_RATE = 9
"""(float) Lepton frame rate in frames per second"""


# PureThermal USB identifiers
PT_USB_VID = 0x1e4e 
"""(int) PureThermal USB vendor ID"""

PT_USB_PID = 0x0100
"""(int) PureThermal USB product ID"""


# Path to libuvc dll
LIBUVC_DLL_PATH = "/usr/local/lib/libuvc.so"
"""(str) PureThermal USB vendor ID"""


# Purethermal timeout
PURETHERMAL_TIMEOUT = 3.0 
"""(float) Maximum time in seconds to allow the purethermal board to not send a valid frame"""


# Lepton hotspot detection
HOTSPOT_EMA_ALPHA = 0.1
"""(float) Exponential moving avg. constant (weight [0,1] to give to new value). Time constant = -(sample period) / ln(1-alpha)"""

HOTSPOT_TRIP_TIME = 3
"""(float) Duration in seconds that a hotspot must be visible for in order to register as a hotspot"""

HOTSPOT_RELEASE_TIME = 10
"""(float) Duration in seconds where no hotspots are detected after which the hotspot flag will be lowered"""


# Thermal image clipping limits
TEMP_THRESH_LOW  = 40.0
"""(float) Lowest temperature in degrees C to record"""

TEMP_THRESH_HIGH = 100.0
"""(float) Highest temperature in degrees C to record"""


# Blob filtering parameters
BLOB_MIN_AREA = 16
"""(int) Minimum number of pixels that a blob must contain to be considered valid"""

BLOB_MIN_TEMP = 50.0
"""(float) Minimum average temperature that a blob must have to be considered valid"""


# Blob tracking parameters
BLOB_LIVES = 3 
"""(int) Number of frames to retain blob for after it has not been detected"""

BLOB_HISTORY_RATE = 2.0 
"""(float) Number of data points to store per second. Can be < 1"""

BLOB_HISTORY_DEPTH = 30 
"""(int) Maximum number of history samples to keep"""

SLOPE_EST_MAX_POINTS = 900
"""(int) Maximum number of pairwise slopes to consider for the Theil-Sen estimator.\n\n Should be >= BLOB_HISTORY_DEPTH*(BLOB_HISTORY_DEPTH-1) if you don't want random sampling"""


# Cooking detection hysteresis
COOKING_TRIP_TIME = 10 
"""(float) Duration in seconds that a blob must have a constant/positve slope in order to register as cooking"""

COOKING_RELEASE_TIME = 10 
"""(float) Duration in seconds that a cooking blob must have a negative slope in order to deregister as cooking"""


# Blob similarity scoring
SIM_SCORE_WEIGHTS = (1, 4, 2, 0.1)
"""(tuple (float)) Sub-score weights (overlap, distance, temperature, area)"""

SIM_SCORE_MATCH = 0.7
"""(float) Total similarity score threshold (0, 1] to declare a match"""

SIM_SCORE_MIN = 0.1 
"""(float) Two blobs cannot be a match if any sub-score is below this threshold (0, 1]"""

# Minumim slope for a blob to be associated with cooking
TEMP_SLOPE_THRESHOLD = -0.05
"""(float) Minumim slope for a blob to be associated with cooking"""



# Visible image shape
VISIBLE_SHAPE = (480, 640, 3)
"""(tuple (int)) Height, width, depth of visible (Arducam) image"""


# Arducam timeout
ARDUCAM_TIMEOUT = 2.0 
"""(float) Maximum time in seconds to allow the arducam to not send a valid frame """


# Arducam calibration matrix
ARDUCAM_CALIB = [
	[398.62421431702717, 0.000000000000000, 311.42355820638990],
	[0.0000000000000000, 398.5759247050562, 243.21092881633064],
	[0.0000000000000000, 0.000000000000000, 1.0000000000000000]
]
"""(list (list (float))) Arducam calibration matrix"""


# Arducam distortion coefficients
ARDUCAM_DIST = [
    -0.4200401425733124600,
     0.1767459404637726500,
     0.0021537820029228164,
     0.0003045840186394911,
    -0.0339511656826229840,
]
"""(list (float)) Arducam distortion coefficients"""


# Arducam new camera matrix
# Rotates frame 180 degrees
ARDUCAM_NEW_CAM = [
    [-351.8592681884766,  0.000000000000000, 302.78308803853616],
	[ 0.000000000000000, -361.0281494140625, 239.86782248284146],
	[ 0.000000000000000,  0.000000000000000, 1.0000000000000000]
]
"""(list (list (float))) Arducam new camera matrix"""


# User detection constants
USER_TRIP_TIME = 2 
"""(float) Duration in seconds that a person must be detected to set the detection flag"""

USER_RELEASE_TIME = 4 
"""(float) Duration in seconds that a person must be absent to lower the detection flag"""

USER_MIN_CONFIDENCE = 0.6 
"""(float) Confidence threshold for user detection [0,1]"""

USER_MOVEMENT_DIST_THRESH = 20
"""(int) Pixel distance that a bounding box must move to be considered movement"""

USER_MOVEMENT_TIME_THRESH = 15*60
"""(float) Maximum time in seconds that a person can stay stationary before being considered invalid"""
