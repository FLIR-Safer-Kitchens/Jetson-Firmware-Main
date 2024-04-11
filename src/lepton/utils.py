"""Helper functions for manipulating lepton images"""

import numpy as np

# Temp. Conversion Helpers
def f2c(f):
	"""Farenheit to Celsius"""
	return 5/9*(f - 32)

def c2f(c):
	"""Celsius to Farenheit"""
	return 9/5*c + 32


# Radiometry Conversion Helpers (temp units = C)
# TODO: verify that these are accurate
# TODO: Read radiometry app note
def temp2raw(temp):
	"""Temperature value (celsius) to 16-bit T-Linear radiometeric value"""
	return round(100*temp)+27315

def raw2temp(raw):
	"""16-bit T-Linear radiometeric value to temperature value (celsius)"""
	return (raw-27315)/100


# Image manipulation methods
def clip_norm(img, min_val=None, max_val=None):
	"""
	Limit pixel values (usually 16-bit) to a given range and normalize to 8-bit.
	
	Parameters:
	- img (Mat): Image to be clipped/normed
	- min_val (int, None): Lower clipping limit
	- max_val (int, None): Upper clipping limit
	
	Notes: Uses min/max pixel value if min_val/max_val are not given
    """
	
	if min_val == None: min_val = int(min(img.flatten()))
	if max_val == None: max_val = int(max(img.flatten()))

	# Clip image
	img = np.clip(img.flatten(), min_val, max_val).reshape(img.shape)

	# Map limits to 8-bit
	# Surely there's a function for this
	img = np.multiply(np.subtract(img, min_val), 255/(max_val-min_val+0.001))
	return img.astype('uint8')


def hist_equalize(img, clipped=False):
	"""
	Performs histogram equalization on an 8-bit image
	Used to imporve contrast
	
	Parameters:
	- img (Mat): Image to be equalized
	- clipped (bool, None): Image has been clipped; ignore first and last bins
    """
	
	# Get histogram and CDF
	hist = np.histogram(img.flatten(), 256, [0, 255])[0]
	if clipped: hist[0] = hist[-1] = 0
	cdf = hist.cumsum()

	# Create LUT based on linear CDF
	cdf_m = np.ma.masked_equal(cdf,0)
	cdf_m = (cdf_m-cdf_m.min())*255/(cdf_m.max()-cdf_m.min())
	cdf = np.ma.filled(cdf_m,0).astype('uint8')

	return cdf[img]
