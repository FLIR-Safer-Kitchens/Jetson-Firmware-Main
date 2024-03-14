"""Define global constants"""

# Visible image shape
VISIBLE_SHAPE = (480, 640, 3) # (height, width, depth)

# 16-bit thermal image properties
RAW_THERMAL_SHAPE = (120, 160) # (height, width)
RAW_THERMAL_DIAG  = 200 # sqrt(120^2+160^2)

# Blob detection score saturation value
BLOB_SCORE_MAX = 3

# Blob similarity scoring
SIM_SCORE_WEIGHTS = (1, 1, 2, 0.5) # (Overlap, distance, temperature, area)
SIM_SCORE_MIN = 0.1 # Not a match if any individual score is below this threshold
SIM_SCORE_MATCH = 0.7 # Combined score threshold to declare a match
