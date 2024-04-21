"""Define global constants"""

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

# Cooking detection hysteresis thresholds
COOKING_SCORE_SATURATION  = 30
COOKING_SCORE_THRESH_LOW  = 10
COOKING_SCORE_THRESH_HIGH = 20

# Blob similarity scoring
SIM_SCORE_WEIGHTS = (1, 1, 2, 0.5) # Score weights (Overlap, distance, temperature, area)
SIM_SCORE_MATCH = 0.7 # Combined score threshold to declare a match
SIM_SCORE_MIN = 0.1 # Not a match if any individual score is below this threshold

# Minumim slope for cooking detection
TEMP_SLOPE_THRESHOLD = -10

# User detection constants
USER_MIN_CONFIDENCE = 0.5 # Confidence threshold for user detection [0,1]
USER_TRACKING_TIME_THRESH = 2  # Time in seconds after first detection to consider a person valid
USER_MOVEMENT_DIST_THRESH = 20 # Pixel distance that a bounding box must move to be considered movement
USER_MOVEMENT_TIME_THRESH = 15*60 # Maximum time in seconds that a person can stay stationary before being considered invalid

# Live streaming constants
UDP_PORT = 12345
HLS_DIRECTORY = "C:/Users/sdhla/Documents/GitHub/Capstone/Jetson-Firmware-Main/src/streaming/hls/" # Directory where stream segments and .m3u8 will be stored. Absolute path preferred
HLS_FILENAME = "thermal.m3u8"
