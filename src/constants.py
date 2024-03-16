"""Define global constants"""

# Visible image shape
VISIBLE_SHAPE = (480, 640, 3) # (height, width, depth)

# 16-bit thermal image properties
RAW_THERMAL_SHAPE = (120, 160) # (height, width)
RAW_THERMAL_DIAG  = 200 # sqrt(120^2+160^2)

# Blob detection
BLOB_LIVES = 3 # Number of frames to retain blob for after it has not been detected
BLOB_HISTORY_RATE = 2 # number of samples to store per second. Can be float
BLOB_HISTORY_DEPTH = 30 # Maximum number of history samples to keep

# Cooking detection
COOKING_SCORE_SATURATION  = 30
COOKING_SCORE_THRESH_LOW  = 10
COOKING_SCORE_THRESH_HIGH = 20

# Blob similarity scoring
SIM_SCORE_WEIGHTS = (1, 1, 2, 0.5) # (Overlap, distance, temperature, area)
SIM_SCORE_MIN = 0.1 # Not a match if any individual score is below this threshold
SIM_SCORE_MATCH = 0.7 # Combined score threshold to declare a match

